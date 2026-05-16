#!/usr/bin/env python3
"""
验证 2026-05-15 防追高修复：
- 使用 2026-05-10 23:53 本地 universe 缓存（即原周报同一份全 A 股候选源）
- 使用 2026-05-08 收盘前历史 K 线做筛选
- 验证 2026-05-11 周一开盘买入 → 2026-05-15 周五收盘卖出的本周表现

对比：
A. old：修复前 V7 口径（仅 bounce>=3.5%、score>=40）
B. fixed：当前生产 score_reversal（先跌后弹 + 防追高硬过滤）
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import data.eastmoney as eastmoney_module  # noqa: E402
from data.eastmoney import eastmoney_api  # noqa: E402
from weekly_advisor.screener import score_reversal  # noqa: E402

SCREEN_DATE = "2026-05-08"
BUY_DATE = "2026-05-11"
SELL_DATE = "2026-05-15"
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]
SINGLE_STOP_PCT = -6.0
PORTFOLIO_STOP_PCT = -4.0


def _calc_rsi(closes: np.ndarray, period: int = 6) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = float(np.mean(gains)) if gains.size else 0.0
    avg_loss = float(np.mean(losses)) if losses.size else 0.0
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def old_score_reversal(klines: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """修复前口径：仅 bounce>=3.5 做硬过滤，其余都只是加分。"""
    closes = np.array([k["close"] for k in klines], dtype=float)
    volumes = np.array([k["volume"] for k in klines], dtype=float)
    highs = np.array([k["high"] for k in klines], dtype=float)
    lows = np.array([k["low"] for k in klines], dtype=float)
    if len(closes) < 20:
        return None

    low_5d = float(np.min(lows[-5:]))
    bounce = (closes[-1] - low_5d) / low_5d * 100 if low_5d > 0 else 0.0
    if bounce < 3.5:
        return None

    recent_gain = (closes[-1] - closes[-3]) / closes[-3] * 100 if len(closes) >= 3 and closes[-3] > 0 else 0.0
    decline_7d = (closes[-1] - closes[-8]) / closes[-8] * 100 if len(closes) >= 8 and closes[-8] > 0 else 0.0
    avg_vol_5d = float(np.mean(volumes[-6:-1])) if len(volumes) >= 6 else float(np.mean(volumes[:-1]))
    vol_ratio = float(volumes[-1]) / avg_vol_5d if avg_vol_5d > 0 else 1.0
    rsi6 = _calc_rsi(closes, 6)

    score = 0.0
    if bounce > 8:
        score += 20
    elif bounce > 6:
        score += 17
    elif bounce > 4:
        score += 13
    elif bounce > 3:
        score += 9
    else:
        score += 5

    if recent_gain > 6:
        score += 12
    elif recent_gain > 2:
        score += 7

    if decline_7d < -15:
        score += 8
    elif decline_7d < -10:
        score += 6
    elif decline_7d < -8:
        score += 4
    else:
        score += 2

    if vol_ratio > 3.0:
        score += 18
    elif vol_ratio > 2.0:
        score += 12
    elif vol_ratio > 1.5:
        score += 8
    else:
        score += 4
    if len(volumes) >= 2 and volumes[-1] > volumes[-2]:
        score += 6

    if len(highs) >= 14:
        atr = float(np.mean(highs[-14:] - lows[-14:]))
        atr_ratio = atr / closes[-1] * 100 if closes[-1] > 0 else 0.0
        if atr_ratio > 5:
            score += 12
        elif atr_ratio > 3:
            score += 6

    if rsi6 < 30:
        score += 10
    elif rsi6 < 45:
        score += 3

    final_score = round(min(100.0, max(0.0, score)), 2)
    if final_score < 40:
        return None
    change_5d = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 and closes[-6] > 0 else 0.0
    return {
        "score": final_score,
        "bounce_pct": round(float(bounce), 2),
        "decline_7d": round(float(decline_7d), 2),
        "vol_ratio": round(float(vol_ratio), 2),
        "rsi6": round(float(rsi6), 1),
        "change_5d": round(float(change_5d), 2),
        "recent_gain_2d": round(float(recent_gain), 2),
    }


def fixed_score_reversal(klines: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    closes = np.array([k["close"] for k in klines], dtype=float)
    volumes = np.array([k["volume"] for k in klines], dtype=float)
    highs = np.array([k["high"] for k in klines], dtype=float)
    lows = np.array([k["low"] for k in klines], dtype=float)
    opens = np.array([k["open"] for k in klines], dtype=float)
    score, details = score_reversal(
        closes,
        volumes,
        {},
        opens=opens,
        highs=highs,
        lows=lows,
        return_details=True,
    )
    if score < 40:
        return None
    change_5d = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 and closes[-6] > 0 else 0.0
    recent_gain = (closes[-1] - closes[-3]) / closes[-3] * 100 if len(closes) >= 3 and closes[-3] > 0 else 0.0
    return {
        "score": float(score),
        "bounce_pct": details.get("bounce_pct"),
        "decline_7d": details.get("decline_7d"),
        "vol_ratio": details.get("vol_ratio"),
        "rsi6": details.get("rsi6"),
        "change_5d": round(float(change_5d), 2),
        "recent_gain_2d": round(float(recent_gain), 2),
    }


def load_cached_universe() -> List[Dict[str, Any]]:
    path = REPO_ROOT / "backend" / "cache" / "universe" / "amount.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    stocks = []
    for s in payload.get("data", []):
        code = s.get("code")
        name = s.get("name") or ""
        price = s.get("price") or 0
        if not code or code in seen:
            continue
        seen.add(code)
        if price <= 0 or "ST" in name or "退" in name:
            continue
        stocks.append(s)
    return stocks


async def fetch_kline(code: str) -> List[Dict[str, Any]]:
    try:
        klines = await eastmoney_api.get_kline_data(code, klt="101", limit=80)
        return [k for k in (klines or []) if k.get("date") <= SELL_DATE]
    except Exception:
        return []


def add_returns(row: Dict[str, Any], klines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    by_date = {k["date"]: k for k in klines}
    if BUY_DATE not in by_date or SELL_DATE not in by_date:
        return None
    buy_open = float(by_date[BUY_DATE]["open"])
    sell_close = float(by_date[SELL_DATE]["close"])
    row["buy_open"] = round(buy_open, 2)
    row["sell_close"] = round(sell_close, 2)
    row["raw_ret"] = round((sell_close - buy_open) / buy_open * 100, 2)

    stop_price = buy_open * (1 + SINGLE_STOP_PCT / 100)
    exit_price = sell_close
    stopped = False
    for k in [x for x in klines if BUY_DATE <= x["date"] <= SELL_DATE]:
        if float(k["low"]) <= stop_price:
            exit_price = stop_price
            stopped = True
            break
    row["single_stop_ret"] = round((exit_price - buy_open) / buy_open * 100, 2)
    row["single_stopped"] = stopped
    return row


def portfolio_ret(picks: List[Dict[str, Any]], use_portfolio_stop: bool) -> float:
    if not picks:
        return 0.0
    weights = WEIGHTS[: len(picks)]
    total = sum(weights)
    weights = [w / total for w in weights]
    final_single = sum(w * p["single_stop_ret"] for w, p in zip(weights, picks))
    if not use_portfolio_stop:
        return round(final_single, 2)

    days = sorted({k["date"] for p in picks for k in p["hold"] if BUY_DATE <= k["date"] <= SELL_DATE})
    stopped_flags = [False] * len(picks)
    for day in days:
        port = 0.0
        for i, p in enumerate(picks):
            row = next((x for x in p["hold"] if x["date"] == day), None)
            if row is None:
                pnl = 0.0
            elif stopped_flags[i]:
                pnl = SINGLE_STOP_PCT
            else:
                stop_price = p["buy_open"] * (1 + SINGLE_STOP_PCT / 100)
                if float(row["low"]) <= stop_price:
                    stopped_flags[i] = True
                    pnl = SINGLE_STOP_PCT
                else:
                    pnl = (float(row["close"]) - p["buy_open"]) / p["buy_open"] * 100
            port += weights[i] * pnl
        if port <= PORTFOLIO_STOP_PCT:
            return PORTFOLIO_STOP_PCT
    return round(final_single, 2)


def print_variant(name: str, candidates: List[Dict[str, Any]]) -> None:
    picks = candidates[:5]
    raw_weights = WEIGHTS[: len(picks)]
    total = sum(raw_weights) or 1
    weights = [w / total for w in raw_weights]
    raw = round(sum(w * p["raw_ret"] for w, p in zip(weights, picks)), 2) if picks else 0.0
    single = portfolio_ret(picks, use_portfolio_stop=False)
    port = portfolio_ret(picks, use_portfolio_stop=True)
    print(f"\n{name}: 候选 {len(candidates)} 只 | 原始持有 {raw:+.2f}% | 单股止损 {single:+.2f}% | V12b组合止损 {port:+.2f}%")
    print("排名  权重   代码      名称      分数   周收益  止损后  7日%    反弹%  RSI6  2日%   5日%")
    for i, p in enumerate(picks, 1):
        w = weights[i - 1] * 100
        print(
            f"{i:<4}{w:>5.0f}%  {p['code']:<8}{p['name']:<8}"
            f"{p['score']:>5.0f}  {p['raw_ret']:>+6.2f}% {p['single_stop_ret']:>+6.2f}% "
            f"{p['decline_7d']:>+6.2f} {p['bounce_pct']:>6.2f} {p['rsi6']:>5.1f} "
            f"{p['recent_gain_2d']:>+6.2f} {p['change_5d']:>+6.2f}"
        )


async def main() -> int:
    stocks = load_cached_universe()
    print(f"使用本地 universe 缓存: {len(stocks)} 只 | 筛选日 {SCREEN_DATE} | 验证周 {BUY_DATE}~{SELL_DATE}")

    sem = asyncio.Semaphore(32)

    async def one(idx: int, stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with sem:
            code = stock.get("code")
            klines = await fetch_kline(code)
            hist = [k for k in klines if k.get("date") <= SCREEN_DATE]
            if len(hist) < 20:
                return None
            base = {"order": idx, "code": code, "name": stock.get("name", ""), "hold": [k for k in klines if BUY_DATE <= k.get("date") <= SELL_DATE]}
            old = old_score_reversal(hist)
            fixed = fixed_score_reversal(hist)
            out: Dict[str, Any] = {"old": None, "fixed": None}
            if old:
                row = add_returns({**base, **old}, klines)
                out["old"] = row
            if fixed:
                row = add_returns({**base, **fixed}, klines)
                out["fixed"] = row
            return out if out["old"] or out["fixed"] else None

    results = await asyncio.gather(*[one(i, s) for i, s in enumerate(stocks)])
    old_candidates = [r["old"] for r in results if r and r.get("old")]
    fixed_candidates = [r["fixed"] for r in results if r and r.get("fixed")]
    old_candidates.sort(key=lambda x: (-x["score"], x["order"]))
    fixed_candidates.sort(key=lambda x: (-x["score"], x["order"]))

    print_variant("修复前 old", old_candidates)
    print_variant("修复后 fixed", fixed_candidates)

    # 关闭共享 aiohttp session，避免脚本结束时出现 unclosed warning。
    session = getattr(eastmoney_module, "_SHARED_SESSION", None)
    if session and not session.closed:
        await session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
