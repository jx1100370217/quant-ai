"""
周度选股顾问数据模型 - Pydantic v2
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class StockCandidate(BaseModel):
    """候选股票（反转策略阶段）"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    price: float = Field(default=0.0, description="当前价格")
    change_pct_5d: float = Field(default=0.0, description="近5日涨跌幅(%)")
    decline_5d: float = Field(default=0.0, description="近5日涨跌幅(%，保留历史字段名)")
    net_inflow: float = Field(default=0.0, description="主力净流入(元)")
    pe_ttm: Optional[float] = Field(default=None, description="PE TTM")
    pb: Optional[float] = Field(default=None, description="市净率 PB")
    market_cap_b: Optional[float] = Field(default=None, description="市值(亿元)")
    quant_score: float = Field(default=0.0, description="量化预筛分(0-100)")
    reversal_score: float = Field(default=0.0, description="反转得分(0-100)")
    composite_score: float = Field(default=0.0, description="综合评分(0-100)")
    # V12b 评分细节（前端表格展示）
    bounce_pct: Optional[float] = Field(default=None, description="5日低点反弹幅度(%)")
    decline_7d: Optional[float] = Field(default=None, description="7日涨跌幅(%)")
    vol_ratio: Optional[float] = Field(default=None, description="成交量/5日均量")
    rsi6: Optional[float] = Field(default=None, description="RSI6 指标")
    # 辅助字段（内部使用）
    source: str = Field(default="", description="来源：reversal")
    sector_name: str = Field(default="", description="所属板块")


class StockRecommendation(BaseModel):
    """推荐股票（最终输出）"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    current_price: float = Field(description="当前价格")
    target_price: float = Field(description="目标价(+5%)")
    stop_loss_price: float = Field(description="单股硬止损价(-6%)")
    position_pct: float = Field(description="建议仓位占比(%)")
    buy_reason: str = Field(description="买入理由")
    risk_note: str = Field(description="风险提示")
    reversal_reason: str = Field(description="反转理由分析")
    reversal_score: float = Field(default=0.0, description="反转得分(0-100)")
    decline_5d: float = Field(default=0.0, description="近5日涨跌幅(%，保留历史字段名)")
    confidence: float = Field(default=0.0, description="量化信号分(0-100)，不是预测胜率")
    # V12b 评分细节（前端 Top5 表格展示）
    bounce_pct: Optional[float] = Field(default=None, description="5日低点反弹幅度(%)")
    decline_7d: Optional[float] = Field(default=None, description="7日涨跌幅(%)")
    vol_ratio: Optional[float] = Field(default=None, description="成交量/5日均量")
    rsi6: Optional[float] = Field(default=None, description="RSI6 指标")


class WeeklyReport(BaseModel):
    """周度选股报告"""
    report_date: str = Field(description="报告生成日期，格式 YYYY-MM-DD")
    target_week: str = Field(description="目标交易周，如 '2026-03-23 ~ 2026-03-27'")
    market_summary: str = Field(description="大盘环境简评")
    recommendations: List[StockRecommendation] = Field(description="推荐股票列表(3-5只)")
    total_candidates_scanned: int = Field(default=0, description="本轮实际收到的去重股票数")
    market_cap_eligible: Optional[int] = Field(default=None, description="市值过滤后股票数")
    kline_evaluated: Optional[int] = Field(default=None, description="历史K线完整并完成评分的股票数")
    scan_data_complete: Optional[bool] = Field(default=None, description="universe 覆盖率是否达到90%")
    scan_metrics_version: str = Field(default="", description="扫描统计口径；空值表示历史报告")
    reversal_filtered: int = Field(default=0, description="反转候选数量")
    risk_warning: str = Field(description="整体风险提示")
    strategy_notes: str = Field(description="本周策略要点")
    strategy_version: str = Field(default="V14-research-baseline", description="策略版本")
    generated_at: str = Field(default="", description="报告生成时间 ISO-8601")
    invested_position_pct: float = Field(default=0.0, description="股票总仓位(%)")
    cash_position_pct: float = Field(default=100.0, description="保留现金仓位(%)")


class LLMStockAnalysis(BaseModel):
    """单只股票的LLM分析输出（内部使用）"""
    code: str = Field(description="股票代码")
    buy_reason: str = Field(description="买入理由（150字以内，基于反转分析）")
    risk_note: str = Field(description="个股风险提示（80字以内）")
    reversal_reason: str = Field(description="反转理由分析（100字以内）")
    position_pct: float = Field(description="排名槽位仓位(%)；候选不足时合计可低于100%，余为现金")


class LLMWeeklyOutput(BaseModel):
    """LLM 生成周报的结构化输出（内部使用）"""
    market_summary: str = Field(description="大盘环境简评（100字以内）")
    risk_warning: str = Field(description="整体风险提示（100字以内）")
    strategy_notes: str = Field(description="本周策略要点（150字以内）")
    stock_analyses: List[LLMStockAnalysis] = Field(description="每只推荐股的详细分析")
