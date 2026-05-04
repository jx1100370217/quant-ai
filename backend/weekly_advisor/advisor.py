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
from .screener import scan_reversal_candidates

logger = logging.getLogger(__name__)

# ── V12 策略参数（V1→V7→V8→V9→V10→V11(废弃)→V12 迭代得出的最优配置）────
# 半年(26周)回测 2025-10-10 ~ 2026-04-17：
#   V12b 累计 +61.39%，夏普 0.40，最大回撤 -7.43%，最差单周 -4.00%
#   对比 V10：+23.03% / 0.18 / -17.44% / -6.00%
#
# V12 相对 V10 的两处关键改动：
#   1. 筛选收紧：反弹 >=3.5%（V10 是 2%），反转分 >=40（V10 是 >0）
#      效果：空仓周数 3→8，避开低质量入场，累计收益翻倍
#   2. 组合级周内止损 -4%：按持仓加权的组合当周累计回撤 <= -4% 即次日清仓
#      效果：最差单周从 -6.00% → -4.00%，最大回撤 -17.44% → -7.43%
V10_WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]  # Top1→Top5 按反转分排名加权
V10_STOP_LOSS_PCT = -6.0                      # 单股硬止损 -6%（下单时挂出）
V10_TARGET_PCT = 5.0                          # 目标收益 +5%

# V12 新增：组合级周内追踪止损（由 portfolio_monitor 在运行期执行，
# 周报生成后自动保存活跃持仓，交易时段每 5 分钟检查一次；亦可通过
# /api/weekly-advisor/portfolio-stop/check 手动触发）
V12_PORTFOLIO_STOP_PCT = -4.0                 # 组合加权回撤 <= -4% 则次日清仓
V12_MIN_SCORE = 40                            # 反转分最低门槛（已在 screener 执行）

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
5日跌幅: {c.decline_5d:.2f}%
主力净流入: {c.net_inflow/1e8:.2f}亿元
PE TTM: {c.pe_ttm or 'N/A'}  PB: {c.pb or 'N/A'}  市值: {c.market_cap_b or 'N/A'}亿
反转得分: {c.reversal_score:.1f}/100
""".strip()
        )

    prompt = f"""你是专业的A股反转策略投资顾问，需要生成一份反转策略周度选股报告。

## 推荐标的候选（{len(top_candidates)}只，V12 纯反转策略：反弹≥3.5% ∧ 反转分≥40）：

{chr(10).join(['---' + info for info in stocks_info])}

## 本周选股目标
- 投资目标：下周（{_get_target_week_str()}）实现约5%的盈利
- 目标价 = 当前价 × 1.05（取整到小数点后2位）
- 止损价 = 当前价 × 0.94（单股 -6% 硬止损）
- 分散配置：Top 5 按反转分加权 35/25/20/12/8%（服务端会覆盖 position_pct）
- 组合保护：持仓组合周内加权回撤 ≤ -4% 应次日清仓（运行期监控，无法静态挂单）

## 要求
请基于反转策略数据，生成结构化分析：
1. market_summary：大盘环境简评（当前市场风格、趋势、风险等），100字以内
2. risk_warning：整体风险提示（市场系统性风险、反转策略风险、操作注意事项），100字以内
3. strategy_notes：本周策略要点（反转选股逻辑、仓位管理建议），150字以内
4. stock_analyses：对每只推荐股给出：
   - buy_reason：买入理由（基于反转指标分析，为何会反弹至+5%），150字以内
   - risk_note：个股风险提示（80字以内）
   - reversal_reason：反转理由分析（为什么是反转机会，RSI/布林带/支撑位等），100字以内
   - position_pct：建议仓位占比(%)，所有推荐股合计约100%

注意：要求分析务实、有依据，重点强调反转的技术面信号。"""

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
        default_analyses = [
            LLMStockAnalysis(
                code=c.code,
                buy_reason=f"纯反转策略评分{c.reversal_score:.1f}分，近5日跌幅{c.decline_5d:.2f}%，技术面处于超卖状态，具有反转潜力。",
                risk_note="反转策略存在延续下跌风险，请严格执行止损策略。",
                reversal_reason=f"RSI指标超卖，成交量萎缩，价格接近支撑位，具备反转条件。",
                position_pct=round(100.0 / len(top_candidates), 1),
            )
            for c in top_candidates
        ]
        return LLMWeeklyOutput(
            market_summary="市场处于震荡行情，存在反转机会。",
            risk_warning="反转策略需要严格止损，下跌延续风险不可忽视。市场有风险，投资需谨慎。",
            strategy_notes="采用 V12b 纯反转策略：5日低点反弹≥3.5%且反转分≥40 才入选，严格执行+5%目标、单股-6%硬止损和组合-4%周内止损纪律。",
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
                f"   跌幅: {rec.decline_5d:.2f}% | 反转分: {rec.reversal_score:.1f}/100",
                f"   仓位建议: {rec.position_pct:.0f}% | 置信度: {rec.confidence:.1f}%",
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
    1. 反转扫描：扫描全A股约5500只，寻找5日低点反弹≥3.5%的深V候选
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
        # Phase 1: 反转扫描 - 全 A 股 universe（V7 策略，~5300 只）
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 1: 反转扫描 ===")
        candidates = await scan_reversal_candidates(limit=5500)
        total_scanned = 5500  # universe 目标（全 A 股 ~5300 + 余量）
        reversal_filtered = len(candidates)

        logger.info(f"Phase 1 完成: 扫描 {total_scanned} 只 → 反转候选 {reversal_filtered} 只")

        if not candidates:
            logger.warning("反转候选为空，返回空报告")
            return WeeklyReport(
                report_date=report_date,
                target_week=target_week,
                market_summary="当前市场无符合反转条件的标的，市场整体未出现明显调整。",
                recommendations=[],
                total_candidates_scanned=total_scanned,
                reversal_filtered=0,
                risk_warning="当前市场缺乏反转机会，建议观望。",
                strategy_notes="暂无符合反转条件的标的，建议继续关注市场走势。",
            )

        # ════════════════════════════════════════════════════════
        # Phase 2: 反转评分 + LLM 周报生成 + 选出 Top 5 只
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 2: 反转评分与报告生成 ===")

        # 候选已按反转分排序，取 Top 5（有几只给几只；不够 5 就按实有数量）
        top_count = min(5, len(candidates))
        top_candidates = candidates[:top_count]

        logger.info("反转得分排名:")
        for i, c in enumerate(top_candidates, 1):
            logger.info(f"  {i}. {c.code} {c.name}: 反转{c.reversal_score:.1f} "
                       f"(跌幅{c.decline_5d:.2f}%)")

        # 调用 LLM 生成结构化周报文本
        llm_output = await _generate_llm_report(top_candidates)

        # 构建 LLM 分析查找表（code → LLMStockAnalysis）
        llm_analysis_map: Dict[str, LLMStockAnalysis] = {}
        if llm_output and llm_output.stock_analyses:
            for analysis in llm_output.stock_analyses:
                llm_analysis_map[analysis.code] = analysis

        # ── 构建最终推荐列表（V12b 生产组合：V10固定加权 + 单股-6% + 组合-4%）──
        recommendations: List[StockRecommendation] = []
        n_picks = len(top_candidates)
        # 按反转分排名取权重前 n_picks 位，再重新归一化为百分比
        raw_weights = V10_WEIGHTS[:n_picks]
        weight_sum = sum(raw_weights) or 1.0
        normalized_pcts = [round(w / weight_sum * 100.0, 1) for w in raw_weights]

        for idx, candidate in enumerate(top_candidates):
            code = candidate.code
            price = candidate.price or 1.0  # 避免除零
            target_price = round(price * (1.0 + V10_TARGET_PCT / 100.0), 2)   # +5%
            stop_loss_price = round(price * (1.0 + V10_STOP_LOSS_PCT / 100.0), 2)  # -6%

            llm = llm_analysis_map.get(code)

            # 固定加权仓位（覆盖 LLM 建议）：Top1=35%, Top2=25%, Top3=20%, Top4=12%, Top5=8%
            position_pct = normalized_pcts[idx]

            rec = StockRecommendation(
                code=code,
                name=candidate.name,
                current_price=price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                position_pct=position_pct,
                buy_reason=(llm.buy_reason if llm else
                           f"纯反转策略，跌幅{candidate.decline_5d:.2f}%，反转得分{candidate.reversal_score:.1f}分，"
                           f"技术面处于超卖状态，具有反转潜力。"),
                risk_note=(llm.risk_note if llm else
                          "反转策略存在延续下跌风险，请严格执行止损策略。"),
                reversal_reason=(llm.reversal_reason if llm else
                               f"近5日跌幅{candidate.decline_5d:.2f}%，RSI超卖，成交量萎缩，"
                               f"价格接近支撑位，具备反转条件。"),
                reversal_score=candidate.reversal_score,
                decline_5d=candidate.decline_5d,
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
            market_summary=(llm_output.market_summary if llm_output else
                           "市场处于震荡行情，出现短期调整机会，存在反转空间。"),
            recommendations=recommendations,
            total_candidates_scanned=total_scanned,
            reversal_filtered=reversal_filtered,
            risk_warning=(llm_output.risk_warning if llm_output else
                         "反转策略需要严格止损，下跌延续风险不可忽视。市场有风险，投资需谨慎。"),
            strategy_notes=(llm_output.strategy_notes if llm_output else
                           "V12 反转策略：反弹≥3.5%且反转分≥40 才入选，Top 5 加权 35/25/20/12/8%，"
                           "单股 -6% 止损、+5% 目标；组合周内加权回撤 ≤ -4% 则次日清仓。"),
        )

        logger.info(f"=== 周报生成完成: {len(recommendations)} 只推荐股 ===")
        return report
