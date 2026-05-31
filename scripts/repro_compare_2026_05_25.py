#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复现 + 对比：2026-05-25 那一周（筛选日 05-22 周五收盘）
=====================================================
目的：
  1) 复现 V13（生产·防追高反转·全 A 股）当周 Top-5，核对 方正科技/倍杰特/联合水务。
  2) 用 v12b 评分（score_v7, bounce_floor=3.5 + 量比≥1.2 硬过滤 + 评分≥40）在同一周
     给出 Top-5，并对比表现。
  3) 三个口径隔离“评分”和“universe”两个变量：
       A. V13          = 全 A 股 + score_reversal（实际生产，生成了那三只）
       B. v12b@全A股   = 全 A 股 + score_v7  （只换评分，universe 不变）
       C. v12b@蓝筹    = market_cap≥BLUE_CHIP_CAP 亿 + score_v7（近似 HS300+ZZ500，
                          即 backtest_v12.py 原始 v12b 的大中盘 universe）

数据：东方财富（与生产同源）。**必须在能访问 eastmoney 的机器上运行**（如本机）。
universe：默认读 backend/cache/universe/amount.json（2026-05-24 写入的那份快照，
          就是当周实际推荐所用的同一份全 A 股候选源）。加 --refetch 可改为实时重新拉取。

用法：
    cd ~/codes/quant-ai/backend
    python ../scripts/repro_compare_2026_05_25.py
    # 或实时重新拉 universe：
    python ../scripts/repro_compare_2026_05_25.py --refetch
"""
from __future__ import annotations

import argparse
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
from weekly_advisor.screener import score_reversal  # noqa: E402  V13 生产评分

# ── 时间窗口 ───────────────────────────────────────────────
SCREEN_DATE = "2026-05-22"   # 周五收盘 = 自选价基准
BUY_DATE = "2026-05-25"      # 周一开盘买入
SELL_DATE = "2026-05-29"     # 周五收盘卖出
HOLD_DAYS = ["2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29"]

WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]
SINGLE_STOP_PCT = -6.0
PORTFOLIO_STOP_PCT = -4.0
BLUE_CHIP_CAP = 100.0        # 亿；≥此值近似 HS300+ZZ500 大中盘池（ZZ500 最小成分≈此量级）
TOP_N = 5
CONCURRENCY = 32


# ════════════════════ v12b 评分：逐字移植 backtest_v12.py 的 score_v7 ════════════════════
def _calc_rsi(closes, period: int = 6) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = np.diff(closes[-(period + 1):])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = float(np.mean(gain))
    avg_loss = float(np.mean(loss))
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def score_v12b(opens, highs, lows, closes, volumes, bounce_floor: float = 3.5):
    """v12b = score_v7(bounce_floor=3.5) + 量比≥1.2 硬过滤 + 评分≥40。
    返回 (score, passed, details)。"""
    info: Dict[str, Any] = {"reject": None}
    if len(closes) < 30:
        info["reject"] = "len<30"
        return 0.0, False, info
    decline_7d = (closes[-1] - closes[-8]) / closes[-8] * 100 if closes[-8] > 0 else 0
    info["decline_7d"] = round(float(decline_7d), 2)
    if decline_7d > -5 or decline_7d < -25:
        info["reject"] = f"7日{decline_7d:.2f}出界[-25,-5]"
        return 0.0, False, info
    low_5d = float(min(lows[-5:]))
    bounce = (closes[-1] - low_5d) / low_5d * 100 if low_5d > 0 else 0
    info["bounce"] = round(float(bounce), 2)
    if bounce < bounce_floor:
        info["reject"] = f"bounce{bounce:.2f}<{bounce_floor}"
        return 0.0, False, info
    vol_avg5 = float(np.mean(volumes[-6:-1]))
    vol_ratio = volumes[-1] / vol_avg5 if vol_avg5 > 0 else 0
    info["vol_ratio"] = round(float(vol_ratio), 2)
    if vol_avg5 > 0 and volumes[-1] / vol_avg5 < 1.2:      # v12b 量比硬过滤
        info["reject"] = f"量比{vol_ratio:.2f}<1.2"
        return 0.0, False, info
    score = 0.0
    if bounce > 8:   score += 20
    elif bounce > 6: score += 17
    elif bounce > 4: score += 13
    elif bounce > 3: score += 9
    else:            score += 5
    day1 = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] > 0 else 0
    day2 = (closes[-2] - closes[-3]) / closes[-3] * 100 if closes[-3] > 0 else 0
    recent_gain = day1 + day2
    info["recent_gain"] = round(float(recent_gain), 2)
    if recent_gain > 6:   score += 12
    elif recent_gain > 2: score += 7
    if decline_7d < -15:  score += 8
    elif decline_7d < -10: score += 6
    elif decline_7d < -8:  score += 4
    else:                  score += 2
    if vol_ratio > 3.0:   score += 18
    elif vol_ratio > 2.0: score += 12
    elif vol_ratio > 1.5: score += 8
    else:                 score += 4
    if volumes[-1] > volumes[-2]:
        score += 6
    if len(highs) >= 20:
        atr_ratio = float(np.mean(highs[-20:] - lows[-20:]) / closes[-1] * 100)
        if atr_ratio > 5:   score += 12
        elif atr_ratio > 3: score += 6
    rsi6 = _calc_rsi(closes)
    info["rsi6"] = round(float(rsi6), 1)
    if rsi6 < 30:   score += 10
    elif rsi6 < 45: score += 3
    s = round(min(100.0, max(0.0, score)), 2)
    if s < 40:
        info["reject"] = f"评分{s}<40"
        return s, False, info
    return s, True, info


def score_v13(closes, volumes, opens, highs, lows):
    """V13 生产评分（直接调用 backend/weekly_advisor/screener.score_reversal）。"""
    s, details = score_reversal(
        closes, volumes, {}, opens=opens, highs=highs, lows=lows, return_details=True
    )
    return float(s), details


# ════════════════════ universe ════════════════════
def load_universe_from_cache() -> List[Dict[str, Any]]:
    path = BACKEND_DIR / "cache" / "universe" / "amount.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen, stocks = set(), []
    for s in payload.get("data", []):
        code, name = s.get("code"), s.get("name") or ""
        price = s.get("price") or 0
        if not code or code in seen:
            continue
        seen.add(code)
        if price <= 0 or "ST" in name or "退" in name:
            continue
        stocks.append(s)
    return stocks


async def fetch_universe_live(limit: int = 5500) -> List[Dict[str, Any]]:
    stocks = await eastmoney_api.get_top_stocks_market_wide(limit=limit, sort_by="amount")
    out, seen = [], set()
    for s in stocks or []:
        code, name = s.get("code"), s.get("name") or ""
        if not code or code in seen:
            continue
        seen.add(code)
        if (s.get("price") or 0) <= 0 or "ST" in name or "退" in name:
            continue
        out.append(s)
    return out


async def fetch_kline(code: str) -> List[Dict[str, Any]]:
    try:
        kl = await eastmoney_api.get_kline_data(code, klt="101", limit=80)
        return [k for k in (kl or []) if k.get("date") <= SELL_DATE]
    except Exception:
        return []


# ════════════════════ 收益 ════════════════════
def realized(klines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    by = {k["date"]: k for k in klines}
    if BUY_DATE not in by or SELL_DATE not in by:
        return None
    bo = float(by[BUY_DATE]["open"])
    sc = float(by[SELL_DATE]["close"])
    raw = (sc - bo) / bo * 100
    stop_price = bo * (1 + SINGLE_STOP_PCT / 100)
    single = raw
    stopped = False
    for d in HOLD_DAYS:
        if d in by and float(by[d]["low"]) <= stop_price:
            single = SINGLE_STOP_PCT
            stopped = True
            break
    return {"buy_open": round(bo, 2), "sell_close": round(sc, 2),
            "raw_ret": round(raw, 2), "single_stop_ret": round(single, 2),
            "stopped": stopped, "hold": [k for k in klines if BUY_DATE <= k["date"] <= SELL_DATE]}


def portfolio_with_stop(picks: List[Dict[str, Any]]) -> Dict[str, float]:
    if not picks:
        return {"raw": 0.0, "single": 0.0, "port": 0.0}
    w = WEIGHTS[: len(picks)]
    tot = sum(w)
    w = [x / tot for x in w]
    raw = sum(wi * p["raw_ret"] for wi, p in zip(w, picks))
    single = sum(wi * p["single_stop_ret"] for wi, p in zip(w, picks))
    # 组合 -4% 日度追踪止损
    port = single
    stopped_flags = [False] * len(picks)
    for d in HOLD_DAYS:
        acc = 0.0
        for i, p in enumerate(picks):
            row = next((x for x in p["hold"] if x["date"] == d), None)
            bo = p["buy_open"]
            if row is None:
                pnl = 0.0
            elif stopped_flags[i]:
                pnl = SINGLE_STOP_PCT
            else:
                sp = bo * (1 + SINGLE_STOP_PCT / 100)
                if float(row["low"]) <= sp:
                    stopped_flags[i] = True
                    pnl = SINGLE_STOP_PCT
                else:
                    pnl = (float(row["close"]) - bo) / bo * 100
            acc += w[i] * pnl
        if acc <= PORTFOLIO_STOP_PCT:
            port = PORTFOLIO_STOP_PCT
            break
    return {"raw": round(raw, 2), "single": round(single, 2), "port": round(port, 2)}


def show(title: str, picks: List[Dict[str, Any]]) -> None:
    p = portfolio_with_stop(picks)
    print(f"\n{'='*104}\n{title}")
    print(f"  组合（{len(picks)}只·{[int(x*100) for x in WEIGHTS[:len(picks)]]}权重）: "
          f"原始 {p['raw']:+.2f}% | 单股-6%止损 {p['single']:+.2f}% | +组合-4%止损 {p['port']:+.2f}%")
    print(f"{'-'*104}")
    print(f"{'#':<3}{'代码':<9}{'名称':<10}{'市值亿':>7} {'评分':>5} {'反弹%':>7} {'7日%':>7} "
          f"{'2日%':>6} {'量比':>6} {'RSI6':>6} {'买入':>7} {'卖出':>7} {'周收益%':>8} {'止损后%':>8}")
    for i, c in enumerate(picks, 1):
        print(f"{i:<3}{c['code']:<9}{c['name']:<10}{c.get('cap',0):>7.0f} {c['score']:>5.0f} "
              f"{c.get('bounce',0):>7.2f} {c.get('decline_7d',0):>7.2f} {c.get('recent_gain',0):>6.2f} "
              f"{c.get('vol_ratio',0):>6.2f} {c.get('rsi6',0):>6.1f} {c['buy_open']:>7.2f} "
              f"{c['sell_close']:>7.2f} {c['raw_ret']:>+8.2f} {c['single_stop_ret']:>+8.2f}"
              f"{'  [止损]' if c['stopped'] else ''}")


async def main(refetch: bool) -> int:
    stocks = await fetch_universe_live() if refetch else load_universe_from_cache()
    print(f"universe: {len(stocks)} 只 | 筛选日 {SCREEN_DATE} | 持仓 {BUY_DATE}~{SELL_DATE} | "
          f"来源 {'实时' if refetch else 'cache/universe/amount.json (2026-05-24 快照)'}")

    sem = asyncio.Semaphore(CONCURRENCY)
    cap_by_code = {s.get("code"): (s.get("market_cap_b") or 0) for s in stocks}

    async def one(stock: Dict[str, Any]):
        async with sem:
            code = stock.get("code")
            kl = await fetch_kline(code)
            hist = [k for k in kl if k.get("date") <= SCREEN_DATE]
            if len(hist) < 30:
                return None
            c = np.array([k["close"] for k in hist], float)
            o = np.array([k["open"] for k in hist], float)
            h = np.array([k["high"] for k in hist], float)
            l = np.array([k["low"] for k in hist], float)
            v = np.array([k["volume"] for k in hist], float)
            ret = realized(kl)
            if ret is None:
                return None
            base = {"code": code, "name": stock.get("name", ""),
                    "cap": cap_by_code.get(code, 0), **ret}
            # V13
            s13, d13 = score_v13(c, v, o, h, l)
            v13 = None
            if s13 >= 40:
                v13 = {**base, "score": s13, "bounce": d13.get("bounce_pct"),
                       "decline_7d": d13.get("decline_7d"), "recent_gain": d13.get("recent_gain_2d"),
                       "vol_ratio": d13.get("vol_ratio"), "rsi6": d13.get("rsi6")}
            # v12b
            s12, ok12, d12 = score_v12b(o, h, l, c, v)
            v12 = None
            if ok12:
                v12 = {**base, "score": s12, "bounce": d12.get("bounce"),
                       "decline_7d": d12.get("decline_7d"), "recent_gain": d12.get("recent_gain"),
                       "vol_ratio": d12.get("vol_ratio"), "rsi6": d12.get("rsi6")}
            return {"v13": v13, "v12": v12, "cap": cap_by_code.get(code, 0)}

    results = await asyncio.gather(*[one(s) for s in stocks])
    results = [r for r in results if r]

    v13_all = sorted([r["v13"] for r in results if r["v13"]], key=lambda x: -x["score"])
    v12_allA = sorted([r["v12"] for r in results if r["v12"]], key=lambda x: -x["score"])
    v12_blue = sorted([r["v12"] for r in results if r["v12"] and r["cap"] >= BLUE_CHIP_CAP],
                      key=lambda x: -x["score"])

    show(f"A. V13 生产（全A股 + score_reversal）  通过 {len(v13_all)} 只 · Top {TOP_N}",
         v13_all[:TOP_N])
    show(f"B. v12b 评分 @ 全A股（隔离评分变量）  通过 {len(v12_allA)} 只 · Top {TOP_N}",
         v12_allA[:TOP_N])
    show(f"C. v12b @ 蓝筹池 market_cap≥{BLUE_CHIP_CAP:.0f}亿（近似 HS300+ZZ500，原始v12b口径）"
         f"  通过 {len(v12_blue)} 只 · Top {TOP_N}", v12_blue[:TOP_N])

    out = {
        "screen_date": SCREEN_DATE, "buy": BUY_DATE, "sell": SELL_DATE,
        "universe_size": len(stocks),
        "A_v13_allA": v13_all[:20], "B_v12b_allA": v12_allA[:20], "C_v12b_bluechip": v12_blue[:20],
    }
    outp = REPO_ROOT / "scripts" / "repro_compare_2026_05_25_result.json"
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON saved: {outp}")

    session = getattr(eastmoney_module, "_SHARED_SESSION", None)
    if session and not session.closed:
        await session.close()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true", help="实时重拉 universe（默认用 05-24 缓存快照）")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.refetch)))
