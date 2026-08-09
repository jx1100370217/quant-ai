"""A 股日线回测的可执行性与交易摩擦近似。

该模块只处理可由 OHLCV 推断的执行约束。封单队列、逐笔成交和真实冲击成本
无法从日线恢复，因此所有判断都应被视为保守近似，而不是成交保证。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple


@dataclass(frozen=True)
class ExecutionConfig:
    """冻结的基准执行假设，单位均为基点（1 bp = 0.01%）。"""

    commission_bps: float = 3.0
    slippage_bps: float = 10.0
    stamp_duty_bps_before_20230828: float = 10.0
    stamp_duty_bps_after_20230828: float = 5.0
    limit_tolerance_bps: float = 5.0
    max_exit_delay_days: int = 5


DEFAULT_EXECUTION = ExecutionConfig()


def normalize_code(code: str) -> str:
    """把 ``sh.600000``、``600000.SH`` 等形式统一为六位代码。"""
    raw = (code or "").lower().replace("sh.", "").replace("sz.", "").replace("bj.", "")
    return raw.split(".", 1)[0]


def price_limit_pct(code: str, name: str = "", trade_date: Optional[date] = None) -> float:
    """返回常规日涨跌停比例；不覆盖上市首日等特殊制度。"""
    pure = normalize_code(code)
    upper_name = (name or "").upper()
    if "ST" in upper_name:
        return 0.05
    if pure.startswith(("300", "301", "688", "689")):
        # 本项目缓存始于 2020-12，已在创业板 20% 制度实施之后。
        return 0.20
    if pure.startswith(("4", "8", "92")):
        return 0.30
    return 0.10


def daily_limit_prices(
    previous_close: float,
    code: str,
    name: str = "",
    trade_date: Optional[date] = None,
) -> Tuple[float, float]:
    """按复权价比例返回近似涨停价、跌停价。"""
    limit_pct = price_limit_pct(code, name, trade_date)
    return previous_close * (1.0 + limit_pct), previous_close * (1.0 - limit_pct)


def is_suspended(open_price: float, high: float, low: float, volume: float) -> bool:
    return volume <= 0 or min(open_price, high, low) <= 0


def is_open_buyable(
    open_price: float,
    high: float,
    low: float,
    volume: float,
    previous_close: float,
    code: str,
    name: str = "",
    trade_date: Optional[date] = None,
    config: ExecutionConfig = DEFAULT_EXECUTION,
) -> bool:
    """开盘即接近涨停时视为无法按开盘价买入。"""
    if previous_close <= 0 or is_suspended(open_price, high, low, volume):
        return False
    limit_up, _ = daily_limit_prices(previous_close, code, name, trade_date)
    tolerance = config.limit_tolerance_bps / 10_000.0
    return open_price < limit_up * (1.0 - tolerance)


def is_open_sellable(
    open_price: float,
    high: float,
    low: float,
    volume: float,
    previous_close: float,
    code: str,
    name: str = "",
    trade_date: Optional[date] = None,
    config: ExecutionConfig = DEFAULT_EXECUTION,
) -> bool:
    """开盘即接近跌停时不假设能在开盘成交。"""
    if previous_close <= 0 or is_suspended(open_price, high, low, volume):
        return False
    _, limit_down = daily_limit_prices(previous_close, code, name, trade_date)
    tolerance = config.limit_tolerance_bps / 10_000.0
    return open_price > limit_down * (1.0 + tolerance)


def is_intraday_sellable(
    open_price: float,
    high: float,
    low: float,
    volume: float,
    previous_close: float,
    code: str,
    name: str = "",
    trade_date: Optional[date] = None,
    config: ExecutionConfig = DEFAULT_EXECUTION,
) -> bool:
    """一字跌停或停牌日不假设止损单能够成交。"""
    if previous_close <= 0 or is_suspended(open_price, high, low, volume):
        return False
    _, limit_down = daily_limit_prices(previous_close, code, name, trade_date)
    tolerance = config.limit_tolerance_bps / 10_000.0
    return high > limit_down * (1.0 + tolerance)


def stamp_duty_bps(sell_date: date, config: ExecutionConfig = DEFAULT_EXECUTION) -> float:
    if sell_date >= date(2023, 8, 28):
        return config.stamp_duty_bps_after_20230828
    return config.stamp_duty_bps_before_20230828


def net_trade_return_pct(
    raw_buy_price: float,
    raw_sell_price: float,
    buy_date: date,
    sell_date: date,
    config: ExecutionConfig = DEFAULT_EXECUTION,
) -> float:
    """把双边滑点、佣金和卖出印花税计入单笔净收益。"""
    if raw_buy_price <= 0 or raw_sell_price <= 0:
        return 0.0
    bps = 10_000.0
    buy_cash = raw_buy_price * (1.0 + config.slippage_bps / bps) * (
        1.0 + config.commission_bps / bps
    )
    sell_cash = raw_sell_price * (1.0 - config.slippage_bps / bps) * (
        1.0 - (config.commission_bps + stamp_duty_bps(sell_date, config)) / bps
    )
    return (sell_cash / buy_cash - 1.0) * 100.0
