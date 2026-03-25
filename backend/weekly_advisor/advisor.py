"""
周度选股顾问核心模块 - WeeklyAdvisor
四阶段流程：宽选 → 量化预筛 → AI大师评审 → 综合评分+LLM周报生成
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from agents.base import AgentManager
from data.eastmoney import eastmoney_api
from llm.client import acall_llm
from models.agent_models import AgentSignal
from utils.telegram import send_telegram

from .models import (
    LLMStockAnalysis,
    LLMWeeklyOutput,
    StockCandidate,
    StockRecommendation,
    WeeklyReport,
)
from .screener import build_candidate_pool, run_phase2_screening

logger = logging.getLogger(__name__)

# ── 并发锁：防止重复调用（一次完整流程约需5-10分钟）────────────────────────
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


def _compute_master_score(agent_signals: Dict[str, Any], code: str) -> Tuple[float, int, int, int]:
    """
    计算某只股票的大师共识分(0-100)
    返回 (master_score, bullish_count, bearish_count, neutral_count)
    """
    bullish = bearish = neutral = 0
    total_conf = 0.0
    n = 0

    for agent_name, signals in agent_signals.items():
        sig = signals.get(code)
        if not sig:
            continue
        sig_dict = sig.model_dump() if isinstance(sig, AgentSignal) else (sig if isinstance(sig, dict) else {})
        s = sig_dict.get("signal", "neutral")
        c = sig_dict.get("confidence", 0) or 0
        if s == "bullish":
            bullish += 1
        elif s == "bearish":
            bearish += 1
        else:
            neutral += 1
        total_conf += c
        n += 1

    if n == 0:
        return 0.0, 0, 0, 0

    avg_conf = total_conf / n
    # 大师共识分 = 看多比例 × 平均置信度
    bull_ratio = bullish / n
    master_score = round(bull_ratio * avg_conf, 2)
    return master_score, bullish, bearish, neutral


def _compute_composite_score(candidate: StockCandidate, inflow_max: float) -> float:
    """
    综合评分 = 量化分×0.3 + 大师共识×0.4 + 资金流入×0.2 + 技术突破×0.1
    量化分已是0-100，大师共识分0-100，资金流入标准化0-100
    """
    quant_score  = candidate.quant_score
    master_score = candidate.master_score
    # 资金流入标准化（相对最大值）
    inflow_norm = (candidate.net_inflow / inflow_max * 100) if inflow_max > 0 else 0
    inflow_norm = max(0.0, min(100.0, inflow_norm))
    # 技术突破分（利用 quant_score 的技术面子分近似，这里用 5日涨幅合理性）
    tech_break = 50.0 if 1 <= candidate.change_pct_5d <= 8 else 20.0

    composite = (
        quant_score  * 0.30
        + master_score * 0.40
        + inflow_norm  * 0.20
        + tech_break   * 0.10
    )
    return round(min(100.0, max(0.0, composite)), 2)


async def _generate_llm_report(
    top_candidates: List[StockCandidate],
    agent_signals: Dict[str, Any],
) -> LLMWeeklyOutput:
    """
    Phase 4: 调用 LLM 生成结构化周报
    """
    # 构建每只股票的详细信息供 LLM 分析
    stocks_info = []
    for c in top_candidates:
        # 收集该股票的大师信号摘要
        master_signals = []
        for agent_name, signals in agent_signals.items():
            sig = signals.get(c.code)
            if sig:
                sig_dict = sig.model_dump() if isinstance(sig, AgentSignal) else sig
                signal = sig_dict.get("signal", "neutral")
                conf   = sig_dict.get("confidence", 0)
                reason = sig_dict.get("reasoning", "")[:100]
                master_signals.append(f"{agent_name}: {signal}({conf}%) - {reason}")

        stocks_info.append(
            f"""
股票: {c.name}（{c.code}）
当前价格: {c.price:.2f}元
5日涨幅: {c.change_pct_5d:.2f}%
主力净流入: {c.net_inflow/1e8:.2f}亿元
PE TTM: {c.pe_ttm or 'N/A'}  PB: {c.pb or 'N/A'}  市值: {c.market_cap_b or 'N/A'}亿
量化得分: {c.quant_score:.1f}/100
大师共识分: {c.master_score:.1f}/100
综合评分: {c.composite_score:.1f}/100
来源: {c.source}

大师信号：
{chr(10).join(master_signals[:8])}
""".strip()
        )

    prompt = f"""你是专业的A股量化投资顾问，需要生成一份周度选股报告。

## 推荐标的候选（{len(top_candidates)}只，已经过量化预筛和16位投资大师AI评审）：

{chr(10).join(['---' + info for info in stocks_info])}

## 本周选股目标
- 投资目标：下周（{_get_target_week_str()}）实现约5%的盈利
- 目标价 = 当前价 × 1.05（取整到小数点后2位）
- 止损价 = 当前价 × 0.97
- 分散配置，单股仓位不超过30%

## 要求
请基于上述量化数据和大师共识，生成结构化分析：
1. market_summary：大盘环境简评（当前市场风格、趋势、风险等），100字以内
2. risk_warning：整体风险提示（市场系统性风险、操作注意事项），100字以内  
3. strategy_notes：本周策略要点（选股逻辑、仓位管理建议），150字以内
4. stock_analyses：对每只推荐股给出：
   - buy_reason：买入理由（结合量化指标+大师观点，150字以内，说明为何能涨5%）
   - risk_note：个股风险提示（80字以内）
   - master_consensus：大师共识摘要（哪些大师看多/看空，80字以内）
   - position_pct：建议仓位占比(%)，所有推荐股合计约100%

注意：要求分析务实、有依据，不要空话套话，要结合具体数据。"""

    try:
        output = await acall_llm(
            prompt=prompt,
            pydantic_model=LLMWeeklyOutput,
            system_prompt="你是一位专业的A股量化投资顾问，擅长综合量化因子和基本面分析，生成高质量的选股周报。",
            max_tokens=200000,
            temperature=0.3,
        )
        return output
    except Exception as e:
        logger.error(f"LLM 周报生成失败: {e}")
        # 构造一个默认输出
        default_analyses = [
            LLMStockAnalysis(
                code=c.code,
                buy_reason=f"量化综合评分{c.composite_score:.1f}分，大师共识得分{c.master_score:.1f}分，技术面和资金面表现较好。",
                risk_note="个股存在市场系统性风险，请严格执行止损策略。",
                master_consensus=f"16位AI大师评审中，综合共识为{'看多' if c.master_score > 50 else '中性'}。",
                position_pct=round(100.0 / len(top_candidates), 1),
            )
            for c in top_candidates
        ]
        return LLMWeeklyOutput(
            market_summary="市场处于震荡行情，建议分散配置、控制仓位。",
            risk_warning="本报告基于历史数据和AI分析，不构成投资建议。市场有风险，投资需谨慎。",
            strategy_notes="采用量化+AI大师综合选股策略，重点关注资金流入和技术突破标的，严格执行5%目标价和3%止损纪律。",
            stock_analyses=default_analyses,
        )


async def _notify_weekly_report(report: WeeklyReport) -> None:
    """推送周报到 Telegram"""
    try:
        lines = [
            f"📊 <b>QuantAI 周度选股报告</b>",
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
                f"   仓位建议: {rec.position_pct:.0f}%  |  置信度: {rec.confidence:.1f}%",
                f"   👥 大师: 多{rec.bullish_count}/空{rec.bearish_count}/中{rec.neutral_count}",
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
            f"📈 扫描 {report.total_candidates_scanned} 只 → 量化筛选 {report.quant_filtered} 只 → 推荐 {len(report.recommendations)} 只",
        ]
        text = "\n".join(lines)
        await send_telegram(text, parse_mode="HTML")
        logger.info("周报已推送到 Telegram")
    except Exception as e:
        logger.warning(f"Telegram 推送周报失败: {e}")


class WeeklyAdvisor:
    """
    周度选股顾问
    
    执行四阶段流程：
    1. 宽选：从全A股多维度获取候选池
    2. 量化预筛：多因子打分，筛选8-12只候选
    3. AI大师评审：调用16位大师Agent进行分析
    4. 综合评分+LLM周报生成：选出Top 3-5只，生成结构化周报
    """

    def __init__(self, agent_manager: AgentManager):
        self.agent_mgr = agent_manager

    async def generate_weekly_picks(self) -> WeeklyReport:
        """
        生成周度选股报告（主入口）
        - 加并发锁防止重复调用
        - 同日内复用缓存结果
        """
        today_str = datetime.now().strftime("%Y-%m-%d")

        # ── 缓存命中 ──────────────────────────────────────────
        if _REPORT_CACHE["date"] == today_str and _REPORT_CACHE["report"] is not None:
            logger.info("weekly_advisor 命中日内缓存，直接返回上次报告")
            return _REPORT_CACHE["report"]

        # ── 并发锁：同时只允许一个完整流程运行 ──────────────
        async with _ADVISOR_LOCK:
            # 再次检查缓存（等锁期间可能已生成）
            if _REPORT_CACHE["date"] == today_str and _REPORT_CACHE["report"] is not None:
                logger.info("weekly_advisor 等锁后命中缓存")
                return _REPORT_CACHE["report"]

            report = await self._run_full_pipeline()

            # 写入缓存
            _REPORT_CACHE["date"] = today_str
            _REPORT_CACHE["report"] = report

            # 推送 Telegram
            await _notify_weekly_report(report)

            return report

    async def _run_full_pipeline(self) -> WeeklyReport:
        """执行完整的四阶段选股流程"""
        report_date = datetime.now().strftime("%Y-%m-%d")
        target_week = _get_target_week_str()

        # ════════════════════════════════════════════════════════
        # Phase 1: 宽选 - 建立候选池
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 1: 宽选 - 建立候选池 ===")
        raw_candidates = await build_candidate_pool()
        total_scanned = len(raw_candidates)
        logger.info(f"Phase 1 完成: 候选池共 {total_scanned} 只")

        if not raw_candidates:
            logger.warning("候选池为空，返回空报告")
            return WeeklyReport(
                report_date=report_date,
                target_week=target_week,
                market_summary="数据获取异常，无法生成本周选股报告，请稍后重试。",
                recommendations=[],
                total_candidates_scanned=0,
                quant_filtered=0,
                risk_warning="数据获取失败，请检查网络连接后重试。",
                strategy_notes="本周暂无推荐标的。",
            )

        # ════════════════════════════════════════════════════════
        # Phase 2: 量化预筛 - 多因子打分
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 2: 量化预筛 - 多因子打分 ===")
        quant_filtered_candidates = await run_phase2_screening(
            raw_candidates,
            target_count=12,  # 保留最多12只进入AI评审
        )
        quant_filtered_count = len(quant_filtered_candidates)
        logger.info(f"Phase 2 完成: 量化预筛保留 {quant_filtered_count} 只")

        if not quant_filtered_candidates:
            return WeeklyReport(
                report_date=report_date,
                target_week=target_week,
                market_summary="量化筛选后无符合条件标的，当前市场环境不佳。",
                recommendations=[],
                total_candidates_scanned=total_scanned,
                quant_filtered=0,
                risk_warning="当前市场技术面和资金面指标较弱，建议观望。",
                strategy_notes="本周不建议积极建仓，等待更好的入场时机。",
            )

        # ════════════════════════════════════════════════════════
        # Phase 3: AI大师评审
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 3: AI大师评审（16位投资大师） ===")
        candidate_codes = [c.code for c in quant_filtered_candidates]

        # 预热缓存：并发拉取行情+K线，避免16个Agent重复请求
        logger.info("预热数据缓存...")
        warmup_tasks = []
        for code in candidate_codes:
            warmup_tasks.append(eastmoney_api.get_stock_quote(code))
            warmup_tasks.append(eastmoney_api.get_kline_data(code, "101", 100))
            warmup_tasks.append(eastmoney_api.get_kline_data(code, "101", 60))
        warmup_tasks.append(eastmoney_api.get_market_stats())
        warmup_tasks.append(eastmoney_api.get_sector_ranking())
        warm_results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
        warm_fail = sum(1 for r in warm_results if isinstance(r, Exception))
        if warm_fail:
            logger.warning(f"数据预热 {warm_fail} 个失败，将降级运行")
        else:
            logger.info(f"数据预热完成: {candidate_codes}")

        # 运行所有大师Agent（并发，Semaphore=8）
        agent_signals = await self.agent_mgr.run_all_agents(
            {"target_stocks": candidate_codes},
            concurrency=8,
        )
        logger.info(f"Phase 3 完成: {len(agent_signals)} 个 Agent 分析完成")

        # ════════════════════════════════════════════════════════
        # Phase 4: 综合评分 + 选出 Top 3-5 只
        # ════════════════════════════════════════════════════════
        logger.info("=== Phase 4: 综合评分 + LLM 周报生成 ===")

        # 计算大师共识分，填充 master_score
        for candidate in quant_filtered_candidates:
            master_score, bullish, bearish, neutral = _compute_master_score(
                agent_signals, candidate.code
            )
            candidate.master_score = master_score

        # 计算综合评分
        inflow_max = max((c.net_inflow for c in quant_filtered_candidates), default=1.0) or 1.0
        for candidate in quant_filtered_candidates:
            candidate.composite_score = _compute_composite_score(candidate, inflow_max)

        # 按综合评分排序，取 Top 3-5（至少3只，最多5只）
        quant_filtered_candidates.sort(key=lambda x: x.composite_score, reverse=True)
        top_count = min(5, max(3, len(quant_filtered_candidates)))
        top_candidates = quant_filtered_candidates[:top_count]

        logger.info("综合评分排名:")
        for i, c in enumerate(top_candidates, 1):
            logger.info(f"  {i}. {c.code} {c.name}: 综合{c.composite_score:.1f} "
                        f"(量化{c.quant_score:.1f} 大师{c.master_score:.1f})")

        # 调用 LLM 生成结构化周报文本
        llm_output = await _generate_llm_report(top_candidates, agent_signals)

        # 构建大师信号查找表（code → {bullish, bearish, neutral}）
        master_counts: Dict[str, Tuple[int, int, int]] = {}
        for c in top_candidates:
            _, bullish, bearish, neutral = _compute_master_score(agent_signals, c.code)
            master_counts[c.code] = (bullish, bearish, neutral)

        # 构建 LLM 分析查找表（code → LLMStockAnalysis）
        llm_analysis_map: Dict[str, LLMStockAnalysis] = {}
        if llm_output and llm_output.stock_analyses:
            for analysis in llm_output.stock_analyses:
                llm_analysis_map[analysis.code] = analysis

        # ── 构建最终推荐列表 ──────────────────────────────────
        recommendations: List[StockRecommendation] = []
        for candidate in top_candidates:
            code = candidate.code
            price = candidate.price or 1.0  # 避免除零
            target_price = round(price * 1.05, 2)
            stop_loss_price = round(price * 0.97, 2)

            bullish, bearish, neutral = master_counts.get(code, (0, 0, 0))
            llm = llm_analysis_map.get(code)

            # 仓位建议（等权分配，或用 LLM 建议值）
            if llm and llm.position_pct and llm.position_pct > 0:
                position_pct = llm.position_pct
            else:
                position_pct = round(100.0 / len(top_candidates), 1)

            rec = StockRecommendation(
                code=code,
                name=candidate.name,
                current_price=price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                position_pct=position_pct,
                buy_reason=(llm.buy_reason if llm else
                           f"量化综合评分{candidate.composite_score:.1f}分，"
                           f"大师共识{candidate.master_score:.1f}分，技术和资金面良好。"),
                risk_note=(llm.risk_note if llm else
                          "个股存在市场系统性风险，请严格执行止损策略。"),
                master_consensus=(llm.master_consensus if llm else
                                 f"16位大师中看多{bullish}位、看空{bearish}位、中性{neutral}位。"),
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
                confidence=candidate.composite_score,
            )
            recommendations.append(rec)

        # ── 构建完整周报 ─────────────────────────────────────
        report = WeeklyReport(
            report_date=report_date,
            target_week=target_week,
            market_summary=(llm_output.market_summary if llm_output else
                           "量化分析显示当前市场整体处于震荡行情，资金面分化明显。"),
            recommendations=recommendations,
            total_candidates_scanned=total_scanned,
            quant_filtered=quant_filtered_count,
            risk_warning=(llm_output.risk_warning if llm_output else
                         "本报告基于历史数据和AI分析，不构成投资建议。市场有风险，投资需谨慎。"),
            strategy_notes=(llm_output.strategy_notes if llm_output else
                           "采用量化+AI大师综合选股策略，严格执行止盈止损纪律。"),
        )

        logger.info(f"=== 周报生成完成: {len(recommendations)} 只推荐股 ===")
        return report
