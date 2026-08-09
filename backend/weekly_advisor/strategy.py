"""周推荐策略的唯一配置源与仓位分配规则。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class WeeklyStrategyConfig:
    """生产与研究代码共享的稳定策略参数。"""

    version: str = "V14-research-baseline"
    lookback_days: int = 30
    kline_buffer_days: int = 10
    bounce_floor: float = 3.5
    min_decline_7d: float = -25.0
    max_decline_7d: float = -5.0
    vol_ratio_floor: float = 1.5
    min_reversal_score: float = 40.0
    min_market_cap_b: float = 100.0
    universe_limit: int = 5500
    max_picks: int = 5
    rank_weights: Tuple[float, ...] = (0.35, 0.25, 0.20, 0.12, 0.08)
    single_stop_pct: float = -6.0
    portfolio_stop_pct: float = -4.0
    target_pct: float = 5.0


STRATEGY = WeeklyStrategyConfig()


def allocate_rank_weights(n_picks: int) -> tuple[List[float], float]:
    """返回股票仓位百分比和现金仓位百分比。

    候选不足时保留未使用的排名仓位，不再把少数股票归一化到满仓：
    1只=35%股票+65%现金，2只=60%股票+40%现金，...，5只=100%股票。
    """
    if n_picks < 0:
        raise ValueError("n_picks must be non-negative")
    selected = STRATEGY.rank_weights[: min(n_picks, STRATEGY.max_picks)]
    weights_pct = [round(weight * 100.0, 1) for weight in selected]
    cash_pct = round(max(0.0, 100.0 - sum(weights_pct)), 1)
    return weights_pct, cash_pct
