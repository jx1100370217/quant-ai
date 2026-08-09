"""主流加密币周推荐：高流动性现货池上的横向盈利空间比较。"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import aiohttp

from .asset_models import CryptoRecommendation, CryptoWeeklyReport
from .asset_report_store import save_asset_report


logger = logging.getLogger(__name__)
STRATEGY_VERSION = "CRYPTO-CROSS-v1"
BINANCE_CANDLES_URL = "https://data-api.binance.vision/api/v3/klines"
RANK_WEIGHTS = (35.0, 25.0, 15.0)
CRYPTO_UNIVERSE: tuple[dict[str, str], ...] = (
    {"symbol": "BTCUSDT", "name": "Bitcoin", "category": "价值储存"},
    {"symbol": "ETHUSDT", "name": "Ethereum", "category": "智能合约"},
    {"symbol": "BNBUSDT", "name": "BNB", "category": "交易生态"},
    {"symbol": "SOLUSDT", "name": "Solana", "category": "高性能公链"},
    {"symbol": "XRPUSDT", "name": "XRP", "category": "支付网络"},
    {"symbol": "ADAUSDT", "name": "Cardano", "category": "智能合约"},
    {"symbol": "DOGEUSDT", "name": "Dogecoin", "category": "高波动社区币"},
    {"symbol": "TRXUSDT", "name": "TRON", "category": "支付公链"},
    {"symbol": "LINKUSDT", "name": "Chainlink", "category": "预言机"},
    {"symbol": "AVAXUSDT", "name": "Avalanche", "category": "智能合约"},
    {"symbol": "SUIUSDT", "name": "Sui", "category": "高性能公链"},
    {"symbol": "DOTUSDT", "name": "Polkadot", "category": "跨链生态"},
    {"symbol": "LTCUSDT", "name": "Litecoin", "category": "支付网络"},
    {"symbol": "BCHUSDT", "name": "Bitcoin Cash", "category": "支付网络"},
    {"symbol": "NEARUSDT", "name": "NEAR", "category": "智能合约"},
    {"symbol": "UNIUSDT", "name": "Uniswap", "category": "DeFi"},
)

_CACHE_FILE = Path(__file__).resolve().parent.parent / "cache" / "crypto" / "spot-daily.json"
_CRYPTO_LOCK = asyncio.Lock()
_CRYPTO_REPORT_CACHE: Dict[str, Any] = {"date": "", "report": None}


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _pct_change(current: float, previous: float) -> float:
    return (current / previous - 1.0) * 100 if previous > 0 else 0.0


def _max_drawdown(values: Iterable[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, (value / peak - 1.0) * 100)
    return worst


def _target_window() -> str:
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    start = today + timedelta(days=days_until_monday)
    end = start + timedelta(days=6)
    return f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"


def parse_binance_klines(payload: object) -> List[dict]:
    """解析 Binance K 线，并剔除尚未收盘的当日日线。"""
    if not isinstance(payload, list):
        return []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    candles: List[dict] = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            timestamp_ms = int(row[0])
            close_time_ms = int(row[6]) if len(row) > 6 else timestamp_ms + 86400 * 1000 - 1
            if close_time_ms > now_ms:
                continue
            candle = {
                "time": timestamp_ms // 1000,
                "date": datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).strftime("%Y-%m-%d"),
                "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
                "close": float(row[4]), "volume": float(row[5]),
            }
        except (TypeError, ValueError, OSError):
            continue
        if candle["close"] > 0:
            candles.append(candle)
    return sorted(candles, key=lambda item: item["time"])


def score_crypto_candidate(meta: dict[str, str], candles: List[dict]) -> Optional[dict]:
    """计算单币种的趋势、风险和未来一周上行情景。"""
    valid = sorted(
        (item for item in candles if float(item.get("close") or 0) > 0),
        key=lambda item: int(item.get("time") or 0),
    )
    if len(valid) < 65:
        return None
    closes = [float(item["close"]) for item in valid]
    volumes = [float(item.get("volume") or 0) for item in valid]
    current = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    return_7d = _pct_change(current, closes[-8])
    return_30d = _pct_change(current, closes[-31])
    ma20_gap = _pct_change(current, ma20)
    ma60_gap = _pct_change(current, ma60)
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - 19, len(closes))]
    volatility_20d = statistics.pstdev(log_returns) * math.sqrt(365) * 100
    max_drawdown_30d = _max_drawdown(closes[-31:])
    recent_volume = sum(volumes[-7:]) / 7
    previous_volume = sum(volumes[-14:-7]) / 7
    volume_ratio_7d = recent_volume / previous_volume if previous_volume > 0 else 1.0

    score = 44.0
    score += _clip(return_7d * 0.65, -10, 10)
    score += _clip(return_30d * 0.35, -16, 16)
    score += 11 if current > ma20 else -11
    score += 8 if current > ma60 else -8
    score += _clip((volume_ratio_7d - 1) * 5, -4, 6)
    score -= _clip((volatility_20d - 60) * 0.18, 0, 12)
    score -= _clip(abs(min(max_drawdown_30d, 0)) * 0.3, 0, 10)
    if meta["category"] == "高波动社区币":
        score -= 5
    potential_score = round(_clip(score, 0, 100), 1)

    weekly_sigma = volatility_20d / 100 / math.sqrt(365 / 7)
    upside_potential_pct = _clip(
        max(0.0, return_7d * 0.3 + return_30d * 0.06)
        + weekly_sigma * 100 * 0.85,
        0,
        25,
    )
    eligible = (
        current > ma20
        and current > ma60
        and return_30d > 0
        and max_drawdown_30d >= -30
        and potential_score >= 55
    )
    return {
        **meta,
        "current_price": round(current, 8),
        "potential_score": potential_score,
        "upside_potential_pct": round(upside_potential_pct, 2),
        "return_7d": round(return_7d, 2), "return_30d": round(return_30d, 2),
        "ma20_gap": round(ma20_gap, 2), "ma60_gap": round(ma60_gap, 2),
        "volume_ratio_7d": round(volume_ratio_7d, 2),
        "volatility_20d": round(volatility_20d, 2),
        "max_drawdown_30d": round(max_drawdown_30d, 2),
        "eligible": eligible,
    }


def _load_cache() -> dict:
    if not _CACHE_FILE.exists():
        return {}
    try:
        value = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_cache(cache: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, _CACHE_FILE)


def _cached_candles(cache: dict, symbol: str, max_age_seconds: float) -> Optional[List[dict]]:
    entry = cache.get(symbol)
    if not isinstance(entry, dict) or time.time() - float(entry.get("saved_at") or 0) > max_age_seconds:
        return None
    candles = entry.get("candles")
    return candles if isinstance(candles, list) and len(candles) >= 65 else None


async def _fetch_symbol(
    session: aiohttp.ClientSession,
    meta: dict[str, str],
    cache: dict,
    force: bool,
) -> Optional[List[dict]]:
    symbol = meta["symbol"]
    if not force:
        fresh = _cached_candles(cache, symbol, 30 * 60)
        if fresh is not None:
            return fresh
    try:
        async with session.get(
            BINANCE_CANDLES_URL,
            params={"symbol": symbol, "interval": "1d", "limit": 180},
            headers={"User-Agent": "QuantAI/2.0 weekly-research"},
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            candles = parse_binance_klines(await response.json(content_type=None))
            if len(candles) < 65:
                raise RuntimeError(f"日线不足: {len(candles)}")
            cache[symbol] = {"saved_at": time.time(), "candles": candles}
            return candles
    except Exception as exc:
        stale = _cached_candles(cache, symbol, 7 * 24 * 60 * 60)
        if stale is not None:
            logger.warning("%s 行情失败，使用缓存: %s", symbol, exc)
            return stale
        logger.debug("%s 行情失败且无缓存: %s", symbol, exc)
        return None


class CryptoWeeklyAdvisor:
    """生成主流加密货币盈利空间排行榜。"""

    async def generate(self, force: bool = False) -> CryptoWeeklyReport:
        today = datetime.now().strftime("%Y-%m-%d")
        if force:
            _CRYPTO_REPORT_CACHE.update({"date": "", "report": None})
        cached = _CRYPTO_REPORT_CACHE.get("report")
        if _CRYPTO_REPORT_CACHE.get("date") == today and cached is not None:
            return cached
        async with _CRYPTO_LOCK:
            cached = _CRYPTO_REPORT_CACHE.get("report")
            if not force and _CRYPTO_REPORT_CACHE.get("date") == today and cached is not None:
                return cached
            report = await self._run_pipeline(force=force)
            _CRYPTO_REPORT_CACHE.update({"date": today, "report": report})
            try:
                save_asset_report(report, "crypto")
            except Exception as exc:
                logger.warning("加密货币周报持久化失败: %s", exc)
            return report

    async def _run_pipeline(self, force: bool = False) -> CryptoWeeklyReport:
        cache = _load_cache()
        timeout = aiohttp.ClientTimeout(total=14, connect=7)
        semaphore = asyncio.Semaphore(6)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async def evaluate(meta: dict[str, str]) -> Optional[dict]:
                async with semaphore:
                    candles = await _fetch_symbol(session, meta, cache, force)
                    return score_crypto_candidate(meta, candles or [])

            results = await asyncio.gather(*(evaluate(meta) for meta in CRYPTO_UNIVERSE))
        try:
            _save_cache(cache)
        except Exception as exc:
            logger.warning("加密行情缓存写入失败: %s", exc)

        evaluated = [item for item in results if item is not None]
        eligible = sorted(
            (item for item in evaluated if item["eligible"]),
            key=lambda item: (item["potential_score"], item["upside_potential_pct"]),
            reverse=True,
        )
        selected = eligible[: len(RANK_WEIGHTS)]
        recommendations: List[CryptoRecommendation] = []
        for rank, item in enumerate(selected):
            recommendations.append(CryptoRecommendation(
                symbol=item["symbol"].replace("USDT", "-USDT"), name=item["name"],
                category=item["category"], current_price=item["current_price"],
                position_pct=RANK_WEIGHTS[rank], potential_score=item["potential_score"],
                upside_potential_pct=item["upside_potential_pct"], return_7d=item["return_7d"],
                return_30d=item["return_30d"], ma20_gap=item["ma20_gap"], ma60_gap=item["ma60_gap"],
                volume_ratio_7d=item["volume_ratio_7d"], volatility_20d=item["volatility_20d"],
                max_drawdown_30d=item["max_drawdown_30d"],
                risk_line_price=round(item["current_price"] * 0.9, 8),
                reason=(
                    f"7日/30日涨跌 {item['return_7d']:+.2f}%/{item['return_30d']:+.2f}%，"
                    f"价格距20/60日均线 {item['ma20_gap']:+.2f}%/{item['ma60_gap']:+.2f}%，"
                    f"近7日量能比 {item['volume_ratio_7d']:.2f}；盈利空间分在主流币池中靠前。"
                ),
                risk_note=(
                    f"20日年化波动 {item['volatility_20d']:.1f}%，30日最大回撤 "
                    f"{item['max_drawdown_30d']:.1f}%；不使用杠杆，跌破风险线不补仓。"
                ),
            ))

        invested = round(sum(item.position_pct for item in recommendations), 2)
        if recommendations:
            leaders = "、".join(item.name for item in recommendations)
            summary = (
                f"对 {len(CRYPTO_UNIVERSE)} 个高流动性现货币种完成 {len(evaluated)} 个评估，"
                f"{len(eligible)} 个通过趋势和回撤约束；本周盈利空间排名为 {leaders}。"
            )
        else:
            summary = (
                f"对 {len(CRYPTO_UNIVERSE)} 个高流动性现货币种完成 {len(evaluated)} 个评估，"
                "暂无币种同时通过趋势、量能和回撤约束，策略保持现金。"
            )
        now = datetime.now().isoformat(timespec="seconds")
        return CryptoWeeklyReport(
            report_date=now[:10], target_week=_target_window(), market_summary=summary,
            recommendations=recommendations, universe_size=len(CRYPTO_UNIVERSE),
            assets_evaluated=len(evaluated), eligible_count=len(eligible),
            invested_position_pct=invested, cash_position_pct=round(100 - invested, 2),
            risk_warning=(
                "盈利空间分和上行情景只用于币种间横向比较，不代表确定收益。加密资产全天交易，"
                "存在极端波动、流动性、监管、交易平台和稳定币计价风险；严禁使用杠杆。"
            ),
            strategy_notes=(
                "CRYPTO-CROSS-v1：在16个高流动性USDT现货币种中，综合7/30日动量、"
                "20/60日趋势、7日量能、20日波动和30日最大回撤；最多推荐3个币种。"
            ),
            data_source="Binance Spot 公共日线", data_updated_at=now,
            generated_at=now,
        )


crypto_weekly_advisor = CryptoWeeklyAdvisor()
