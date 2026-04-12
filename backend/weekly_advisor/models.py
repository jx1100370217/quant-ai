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
    change_pct_5d: float = Field(default=0.0, description="近5日涨幅(%)")
    decline_5d: float = Field(default=0.0, description="5日跌幅(%)")
    net_inflow: float = Field(default=0.0, description="主力净流入(元)")
    pe_ttm: Optional[float] = Field(default=None, description="PE TTM")
    pb: Optional[float] = Field(default=None, description="市净率 PB")
    market_cap_b: Optional[float] = Field(default=None, description="市值(亿元)")
    quant_score: float = Field(default=0.0, description="量化预筛分(0-100)")
    reversal_score: float = Field(default=0.0, description="反转得分(0-100)")
    composite_score: float = Field(default=0.0, description="综合评分(0-100)")
    # 辅助字段（内部使用）
    source: str = Field(default="", description="来源：reversal")
    sector_name: str = Field(default="", description="所属板块")


class StockRecommendation(BaseModel):
    """推荐股票（最终输出）"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    current_price: float = Field(description="当前价格")
    target_price: float = Field(description="目标价(+5%)")
    stop_loss_price: float = Field(description="止损价(-3%)")
    position_pct: float = Field(description="建议仓位占比(%)")
    buy_reason: str = Field(description="买入理由")
    risk_note: str = Field(description="风险提示")
    reversal_reason: str = Field(description="反转理由分析")
    reversal_score: float = Field(default=0.0, description="反转得分(0-100)")
    decline_5d: float = Field(default=0.0, description="5日跌幅(%)")
    confidence: float = Field(default=0.0, description="综合置信度(0-100)")


class WeeklyReport(BaseModel):
    """周度选股报告"""
    report_date: str = Field(description="报告生成日期，格式 YYYY-MM-DD")
    target_week: str = Field(description="目标交易周，如 '2026-03-23 ~ 2026-03-27'")
    market_summary: str = Field(description="大盘环境简评")
    recommendations: List[StockRecommendation] = Field(description="推荐股票列表(3-5只)")
    total_candidates_scanned: int = Field(default=0, description="扫描候选总数")
    reversal_filtered: int = Field(default=0, description="反转候选数量")
    risk_warning: str = Field(description="整体风险提示")
    strategy_notes: str = Field(description="本周策略要点")


class LLMStockAnalysis(BaseModel):
    """单只股票的LLM分析输出（内部使用）"""
    code: str = Field(description="股票代码")
    buy_reason: str = Field(description="买入理由（150字以内，基于反转分析）")
    risk_note: str = Field(description="个股风险提示（80字以内）")
    reversal_reason: str = Field(description="反转理由分析（100字以内）")
    position_pct: float = Field(description="建议仓位占比(%)，各股合计约100%")


class LLMWeeklyOutput(BaseModel):
    """LLM 生成周报的结构化输出（内部使用）"""
    market_summary: str = Field(description="大盘环境简评（100字以内）")
    risk_warning: str = Field(description="整体风险提示（100字以内）")
    strategy_notes: str = Field(description="本周策略要点（150字以内）")
    stock_analyses: List[LLMStockAnalysis] = Field(description="每只推荐股的详细分析")
