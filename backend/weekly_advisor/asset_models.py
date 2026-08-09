"""公募基金与加密货币周推荐的数据模型。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class FundRecommendation(BaseModel):
    """具体公募基金份额的周推荐。"""

    code: str
    name: str
    fund_type: str
    strategy_group: str
    nav: float
    nav_date: str
    position_pct: float
    potential_score: float = Field(ge=0, le=100, description="盈利空间综合分，不是胜率")
    upside_potential_pct: float = Field(description="未来一周量化上行情景，不是收益预测")
    return_1w: float
    return_1m: float
    return_3m: float
    volatility_3m: float
    max_drawdown_3m: float
    positive_week_ratio: float
    subscribe_status: str
    redeem_status: str
    reason: str
    risk_note: str


class FundWeeklyReport(BaseModel):
    """具体公募基金产品横向比较报告。"""

    report_date: str
    target_week: str
    market_summary: str
    recommendations: List[FundRecommendation]
    universe_size: int
    funds_evaluated: int
    eligible_count: int
    invested_position_pct: float = 0.0
    cash_position_pct: float = 100.0
    risk_warning: str
    strategy_notes: str
    data_source: str
    strategy_version: str = "FUND-MOMENTUM-v1"
    generated_at: str = ""


class CryptoRecommendation(BaseModel):
    """单个主流加密币的横向推荐结果。"""

    symbol: str
    name: str
    category: str
    current_price: float
    position_pct: float
    potential_score: float = Field(ge=0, le=100, description="盈利空间综合分，不是胜率")
    upside_potential_pct: float = Field(description="未来一周量化上行情景，不是收益预测")
    return_7d: float
    return_30d: float
    ma20_gap: float
    ma60_gap: float
    volume_ratio_7d: float
    volatility_20d: float
    max_drawdown_30d: float
    risk_line_price: Optional[float] = None
    reason: str
    risk_note: str


class CryptoWeeklyReport(BaseModel):
    """主流加密币横向比较周报告。"""

    report_date: str
    target_week: str
    market_summary: str
    recommendations: List[CryptoRecommendation]
    universe_size: int
    assets_evaluated: int
    eligible_count: int
    invested_position_pct: float = 0.0
    cash_position_pct: float = 100.0
    risk_warning: str
    strategy_notes: str
    data_source: str
    data_updated_at: str
    strategy_version: str = "CRYPTO-CROSS-v1"
    generated_at: str = ""
