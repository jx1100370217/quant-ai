"""
周度选股顾问核心模块 - WeeklyAdvisor
纯反转策略：两阶段流程：反转扫描 → 反转评分+LLM报告生成
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from data.eastmoney import eastmoney_api
from llm.client import acall_llm
from utils.telegram import send_telegram

from .models import (
    LLMStockAnalysis,
    LLMWeeklyOutput,
    StockCandidate,
    StockRecommendation,
    WeeklyReport,
)
from .portfolio_monitor import save_active_positions
from .report_store import save_weekly_report
from .screener import (
    BOUNCE_FLOOR,
    MAX_DECLINE_7D,
    MIN_DECLINE_7D,
    MIN_REVERSAL_SCORE,
    VOL_RATIO_FLOOR,
    scan_reversal_candidates,
)
from .strategy import STRATEGY, allocate_rank_weights

logger = logging.getLogger(__name__)

# ── 策略参数（V12b 筛选 + V12b 风控）──────────────────────────────
# 2026-05-31 回滚到 V12b：撤掉 V13 防追高护栏（bounce≤20 / RSI6≤70 / 2日≤15%），
# 筛选层恢复 v12b / score_v7 口径：7 日涨跌 ∈ [-25%, -5%]、5 日低点反弹 ≥ 3.5%、
# 量比 ≥ 1.5 三道硬过滤 + 反转分 ≥ 40。universe 收回大中盘（市值≥100亿，近似 HS300+ZZ500）。
# 组合层沿用 V12b：Top5 35/25/20/12/8、单股 -6%、组合 -4%。
V10_WEIGHTS = list(STRATEGY.rank_weights)      # 兼容旧调用；唯一来源在 strategy.py
V10_STOP_LOSS_PCT = STRATEGY.single_stop_pct
V10_TARGET_PCT = STRATEGY.target_pct

# V12 新增：组合级周内追踪止损（由 portfolio_monitor 在运行期执行，
# 周报生成后自动保存活跃持仓，交易时段每 5 分钟检查一次；亦可通过
# /api/weekly-advisor/portfolio-stop/check 手动触发）
V12_PORTFOLIO_STOP_PCT = STRATEGY.portfolio_stop_pct
V12_MIN_SCORE = MIN_REVERSAL_SCORE            # 反转分最低门槛（已在 screener 执行）

# ── 并发锁：防止重复调用（一次完整流程约需3-5分钟）────────────────────────
_ADVISOR_LOCK = asyncio.Lock()

# ── 日内缓存：同一天内复用上次结果 ───────────────────────────────────────
_REPORT_CACHE: Dict[str, Any] = {
    "date": "",       # YYYY-MM-DD
    "report": None,   # WeeklyReport 实例
}


def _get_target_week_str() -> str:
    """计算下一个完整交易周的日期范围（周一到周五）"""
    today = datetime.now()
    # 找到下周一
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # 今天是周一，取下周一
    next_monday = today + timedelta(days=days_until_monday)
    next_friday = next_monday + timedelta(days=4)
    return f"{next_monday.strftime('%Y-%m-%d')} ~ {next_friday.strftime('%Y-%m-%d')}"


async def _generate_llm_report(
    top_candidates: List[StockCandidate],
) -> LLMWeeklyOutput:
    """
    调用 LLM 生成结构化反转周报
    """
    # 构建每只股票的详细信息供 LLM 分析
    stocks_info = []
    for c in top_candidates:
        stocks_info.append(
            f"""
股票: {c.name}（{c.code}）
当前价格: {c.price:.2f}元
5日涨跌: {c.decline_5d:+.2f}%
7日涨跌: {c.decline_7d:+.2f}%
5日低点反弹: {c.bounce_pct:.2f}%
RSI6: {c.rsi6:.1f}
主力净流入: {c.net_inflow/1e8:.2f}亿元
PE TTM: {c.pe_ttm or 'N/A'}  PB: {c.pb or 'N/A'}  市值: {c.market_cap_b or 'N/A'}亿
反转得分: {c.reversal_score:.1f}/100
量比（当日量/前5日均量）: {(c.vol_ratio or 0):.2f}
""".strip()
        )

    prompt = f"""你是A股量化报告解释器，需要为一组已经由规则选出的候选生成可核验的周报文字。

## 推荐标的候选（{len(top_candidates)}只，V12b 反转因子策略：7日涨跌{MIN_DECLINE_7D:.0f}%~{MAX_DECLINE_7D:.0f}% ∧ 5日低点反弹≥{BOUNCE_FLOOR:.1f}% ∧ 量比≥{VOL_RATIO_FLOOR:.1f} ∧ 反转分≥{MIN_REVERSAL_SCORE}）：

{chr(10).join(['---' + info for info in stocks_info])}

## 本周选股目标
- 观察周期：下周（{_get_target_week_str()}）
- +5%仅是观察目标，不是收益预测或承诺
- 止损价 = 当前价 × 0.94（单股 -6% 硬止损）
- 仓位配置：按35/25/20/12/8%的排名槽位分配；候选不足时未使用槽位保留现金
- 组合保护：持仓组合周内加权回撤 ≤ -4% 应次日清仓（运行期监控，无法静态挂单）

## 要求
请基于反转策略数据，生成结构化分析：
1. market_summary：只概括本批候选的数量和共同特征，不推断未提供的大盘趋势，100字以内
2. risk_warning：整体风险提示（市场系统性风险、反转策略风险、操作注意事项），100字以内
3. strategy_notes：本周策略要点（反转选股逻辑、仓位管理建议），150字以内
4. stock_analyses：对每只推荐股给出：
   - buy_reason：支持该反转观察的已提供数据证据，150字以内
   - risk_note：个股风险提示（80字以内）
   - reversal_reason：只解释7日涨跌、5日低点反弹、量比和RSI6，100字以内
   - position_pct：按排名依次使用 35/25/20/12/8%；候选不足时不得重分配，剩余仓位保留现金

事实约束：只能引用上面明确提供的数据。不得编造布林带、均线、支撑位、新闻、公告、行业事件、资金行为或大盘状态；不得把信号分解释为胜率。"""

    try:
        output = await acall_llm(
            prompt=prompt,
            pydantic_model=LLMWeeklyOutput,
            system_prompt="你是一位专业的A股反转策略投资顾问，擅长技术面分析和反转信号识别。",
            max_tokens=4096,
            temperature=0.3,
        )
        return output
    except Exception as e:
        logger.error(f"LLM 周报生成失败: {e}")
        # 构造一个默认输出
        fallback_weights, _ = allocate_rank_weights(len(top_candidates))
        default_analyses = [
            LLMStockAnalysis(
                code=c.code,
                buy_reason=f"V12b反转因子评分{c.reversal_score:.1f}分，7日涨跌{c.decline_7d:+.2f}%，5日低点反弹{c.bounce_pct:.2f}%，量比{(c.vol_ratio or 0):.2f}，技术面处于反转修复区。",
                risk_note="反转策略存在延续下跌风险，请严格执行止损策略。",
                reversal_reason=(
                    f"7日涨跌{c.decline_7d:+.2f}%，5日低点反弹{c.bounce_pct:.2f}%，"
                    f"量比{(c.vol_ratio or 0):.2f}，RSI6={c.rsi6:.1f}；这些是规则信号，不代表确定反转。"
                ),
                position_pct=fallback_weights[idx],
            )
            for idx, c in enumerate(top_candidates)
        ]
        return LLMWeeklyOutput(
            market_summary=f"本期共有{len(top_candidates)}只大中盘股票通过反转规则，仅反映候选特征，不包含大盘趋势判断。",
            risk_warning="反转策略需要严格止损，下跌延续风险不可忽视。市场有风险，投资需谨慎。",
            strategy_notes="采用 V12b 反转因子策略：7日涨跌位于-25%~-5%、5日低点反弹≥3.5%、量比≥1.5且反转分≥40 才入选；严格执行+5%目标、单股-6%硬止损和组合-4%周内止损纪律。",
            stock_analyses=default_analyses,
        )


async def _notify_weekly_report(report: WeeklyReport) -> None:
    """推送周报到 Telegram"""
    try:
        lines = [
            f"📊 <b>QuantAI 反转策略周报</b>",
            f"🗓 目标交易周：{report.target_week}",
            f"📅 生成时间：{report.report_date}",
            "",
            f"🏦 <b>大盘环境</b>",
            f"{report.market_summary}",
            "",
            f"🎯 <b>推荐标的（共{len(report.recommendations)}只）</b>",
        ]
        for i, rec in enumerate(report.recommendations, 1):
            chg_arrow = "▲" if rec.target_price > rec.current_price else "▼"
            lines += [
                f"",
                f"{'①②③④⑤'[i-1]} <b>{rec.name}（{rec.code}）</b>",
                f"   现价: {rec.current_price:.2f} | 目标: {chg_arrow}{rec.target_price:.2f} | 止损: {rec.stop_loss_price:.2f}",
                f"   5日涨跌: {rec.decline_5d:+.2f}% | 7日涨跌: {(rec.decline_7d or 0):+.2f}% | 反转分: {rec.reversal_score:.1f}/100",
                f"   仓位建议: {rec.position_pct:.0f}% | 信号分: {rec.confidence:.1f}/100（非胜率）",
                f"   📝 {rec.buy_reason[:120]}",
            ]
        lines += [
            "",
            f"⚠️ <b>风险提示</b>",
            f"{report.risk_warning}",
            "",
            f"💡 <b>策略要点</b>",
            f"{report.strategy_notes}",
            "",
            f"📈 扫描 {report.total_candidates_scanned} 只 → 反转候选 {report.reversal_filtered} 只 → 推荐 {len(report.recommendations)} 只",
        ]
        text = "\n".join(lines)
        await send_telegram(text, parse_mode="HTML")
        logger.info("周报已推送到 Telegram")
    except Exception as e:
        logger.warning(f"Telegram 推送周报失败: {e}")


class WeeklyAdvisor:
    """
    周度选股顾问 - 纯反转策略

    执行两阶段流程：
    1. 反转扫描：全A股按成交额拉取后筛市值≥100亿大中盘，寻找“先跌后弹”的深V候选
    2. 反转评分+LLM周报：反转分≥40后按分数排序，选出Top 1-5只，生成结构化周报
    """

    def __init__(self):
        pass

    async def generate_weekly_picks(self, force: bool = False) -> WeeklyReport:
        """
        生成周度选股报告（主入口）
        - 加并发锁防止重复调用
        - 同日内复用缓存结果
        - force=True 时清除缓存，强制重新生成
        """
        today_str = datetime.now().strftime("%Y-%m-%d")

        # ── 强制刷新：清除缓存 ────────────────────────────────
        if force:
            logger.info("weekly_advisor 收到 force=True，清除日内缓存")
            _REPORT_CACHE["date"] = ""
            _REPORT_CACHE["report"] = None

        # ── 缓存命中 ──────────────────────────────────────────
        if _REPORT_CACHE["date"] == today_str and _REPORT_CACHE["report"] is not None:
            logger.info("weekly_advisor 命中日内缓存，直接返回上次报告")
            return _REPORT_CACHE["report"]

        # ── 并发锁：同时只允许一个完整流程运行 ──────────────
        async with _ADVISOR_LOCK:
            # 再次检查缓存（等锁期间可能已生成）
            if not force and _REPORT_CACHE["date"] == today_str and _REPORT_CACHE["report"] is not None:
                logger.info("weekly_advisor 等锁后命中缓存")
                return _REPORT_CACHE["report"]

            report = await self._run_full_pipeline()

            # 写入缓存
            _REPORT_CACHE["date"] = today_str
            _REPORT_CACHE["report"] = report

            # 持久化报告和不可覆盖的推荐流水，服务重启后仍可审计与读取。
            try:
                save_weekly_report(report)
            except Exception as e:
                logger.warning(f"持久化周报失败（不影响本次返回）: {e}")

            # ── V12b 组合级止损：锁定当期活跃持仓（供 portfolio_monitor 日常检查）──
            try:
                await save_active_positions(report)
            except Exception as e:
                logger.warning(f"保存活跃持仓失败（不影响周报）: {e}")

            # 推送 Telegram
            await _notify_weekly_report(report)

            return report

    async def _run_full_pipeline(self) -> WeeklyReport:
        """执行完整的反转策略选股流程"""
        report_date = datetime.now().strftime("%Y-%m-%d")
        target_week = _get_target_week_str()

        # ════════════════════════════════════════════════════════
        # Phase 1: 反转扫描 - V12b 大中盘 universe（市值≥100亿，近似 HS300+ZZ500）
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 1: V12b 反转因子扫描 ===")
        scan_stats: Dict[str, Any] = {}
        candidates = await scan_reversal_candidates(
            limit=STRATEGY.universe_limit,
            scan_stats=scan_stats,
        )
        total_scanned = int(scan_stats.get("received", 0))
        market_cap_eligible = int(scan_stats.get("market_cap_eligible", 0))
        kline_evaluated = int(scan_stats.get("kline_evaluated", 0))
        scan_data_complete = bool(scan_stats.get("data_complete", False))
        reversal_filtered = len(candidates)

        logger.info(f"Phase 1 完成: 扫描 {total_scanned} 只 → 反转候选 {reversal_filtered} 只")

        if not candidates:
            logger.warning("反转候选为空，返回空报告")
            return WeeklyReport(
                report_date=report_date,
                target_week=target_week,
                market_summary="本轮未检出同时满足全部反转硬条件的标的；该结果不代表大盘方向。",
                recommendations=[],
                total_candidates_scanned=total_scanned,
                market_cap_eligible=market_cap_eligible,
                kline_evaluated=kline_evaluated,
                scan_data_complete=scan_data_complete,
                scan_metrics_version="actual-v1",
                reversal_filtered=0,
                risk_warning="空候选可能来自信号稀疏或行情数据不完整，不应据此作方向性判断。",
                strategy_notes="股票仓位0%，保留现金100%；等待后续完整数据与新信号。",
                strategy_version=STRATEGY.version,
                generated_at=datetime.now().isoformat(timespec="seconds"),
                invested_position_pct=0.0,
                cash_position_pct=100.0,
            )

        # ════════════════════════════════════════════════════════
        # Phase 2: 反转评分 + LLM 周报生成 + 选出 Top 5 只
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 2: 反转评分与报告生成 ===")

        # 候选已按反转分排序，取 Top 5（有几只给几只；不够 5 就按实有数量）
        top_count = min(STRATEGY.max_picks, len(candidates))
        top_candidates = candidates[:top_count]

        logger.info("反转得分排名:")
        for i, c in enumerate(top_candidates, 1):
            logger.info(f"  {i}. {c.code} {c.name}: 反转{c.reversal_score:.1f} "
                       f"(5日{c.decline_5d:+.2f}%, 7日{(c.decline_7d or 0):+.2f}%)")

        # 调用 LLM 生成结构化周报文本
        llm_output = await _generate_llm_report(top_candidates)

        # 构建 LLM 分析查找表（code → LLMStockAnalysis）
        llm_analysis_map: Dict[str, LLMStockAnalysis] = {}
        if llm_output and llm_output.stock_analyses:
            for analysis in llm_output.stock_analyses:
                llm_analysis_map[analysis.code] = analysis

        # ── 构建最终推荐列表（排名槽位 + 候选不足保留现金 + 两级风险线）──
        recommendations: List[StockRecommendation] = []
        n_picks = len(top_candidates)
        # 候选不足时保留现金，不再把少数股票强行归一化到满仓。
        position_pcts, cash_position_pct = allocate_rank_weights(n_picks)
        invested_position_pct = round(sum(position_pcts), 1)

        for idx, candidate in enumerate(top_candidates):
            code = candidate.code
            price = candidate.price or 1.0  # 避免除零
            target_price = round(price * (1.0 + V10_TARGET_PCT / 100.0), 2)   # +5%
            stop_loss_price = round(price * (1.0 + V10_STOP_LOSS_PCT / 100.0), 2)  # -6%

            llm = llm_analysis_map.get(code)

            # 排名槽位（覆盖 LLM 建议）；候选不足时不重归一化。
            position_pct = position_pcts[idx]

            rec = StockRecommendation(
                code=code,
                name=candidate.name,
                current_price=price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                position_pct=position_pct,
                buy_reason=(llm.buy_reason if llm else
                           f"V12b反转因子策略，5日涨跌{candidate.decline_5d:+.2f}%，"
                           f"7日涨跌{(candidate.decline_7d or 0):+.2f}%，反转得分{candidate.reversal_score:.1f}分，"
                           f"技术面处于低位修复区。"),
                risk_note=(llm.risk_note if llm else
                          "反转策略存在延续下跌风险，请严格执行止损策略。"),
                reversal_reason=(llm.reversal_reason if llm else
                               f"7日仍处回撤区间，5日低点反弹{(candidate.bounce_pct or 0):.2f}%且未过热，"
                               f"RSI6={(candidate.rsi6 or 0):.1f}，具备反转修复条件。"),
                reversal_score=candidate.reversal_score,
                decline_5d=candidate.decline_5d,
                # API 字段为兼容历史前端保留 confidence 名称，语义是信号分而非胜率。
                confidence=candidate.composite_score,
                bounce_pct=candidate.bounce_pct,
                decline_7d=candidate.decline_7d,
                vol_ratio=candidate.vol_ratio,
                rsi6=candidate.rsi6,
            )
            recommendations.append(rec)

        # ── 构建完整周报 ─────────────────────────────────────
        report = WeeklyReport(
            report_date=report_date,
            target_week=target_week,
            market_summary=(
                f"本期{reversal_filtered}只股票通过V14反转规则，最终展示{len(recommendations)}只；"
                "摘要仅基于候选数据，不包含未提供的大盘趋势判断。"
            ),
            recommendations=recommendations,
            total_candidates_scanned=total_scanned,
            market_cap_eligible=market_cap_eligible,
            kline_evaluated=kline_evaluated,
            scan_data_complete=scan_data_complete,
            scan_metrics_version="actual-v1",
            reversal_filtered=reversal_filtered,
            risk_warning=(llm_output.risk_warning if llm_output else
                         "反转策略需要严格止损，下跌延续风险不可忽视。市场有风险，投资需谨慎。"),
            strategy_notes=(
                (llm_output.strategy_notes if llm_output else
                 "7日涨跌位于-25%~-5%，5日低点反弹≥3.5%、量比≥1.5、反转分≥40才入选。")
                + f" 股票仓位{invested_position_pct:.0f}%，保留现金{cash_position_pct:.0f}%；"
                  "信号分不是预测胜率，+5%仅为观察目标。"
            ),
            strategy_version=STRATEGY.version,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            invested_position_pct=invested_position_pct,
            cash_position_pct=cash_position_pct,
        )

        logger.info(f"=== 周报生成完成: {len(recommendations)} 只推荐股 ===")
        return report
