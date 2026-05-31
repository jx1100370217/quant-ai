#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用「回滚后的 V12b 周推荐」重新推荐上周（2026-05-25 那一周）的股票
================================================================
- 直接复用生产 backend/weekly_advisor/screener.score_reversal（已回滚为 V12b/score_v7）。
- 筛选日 = 2026-05-22 周五收盘（把每只票的 K 线截断到该日再打分，等价当周实时推荐）。
- universe = backend/cache/universe/amount.json（2026-05-24 写入，就是当周实际候选源）。
- 输出 Top-5 推荐 + 周一开盘买入/周五收盘卖出实际收益，并和 V13 实盘三只（方正/倍杰特/
  联合水务）对照。

**必须在能访问 eastmoney 的机器上运行**：
    cd ~/codes/quant-ai/backend
    python ../scripts/predict_last_week_v12b.py
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
from weekly_advisor.screener import (  # noqa: E402  ← 生产 V12b 评分
    BLUE_CHIP_CAP,
    LOOKBACK_DAYS,
    MIN_REVERSAL_SCORE,
    score_reversal,
)

SCREEN_DATE = "2026-05-22"
BUY_DATE = "2026-05-25"
SELL_DATE = "2026-05-29"
HOLD_DAYS = ["2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29"]
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]
SINGLE_STOP_PCT = -6.0
PORTFOLIO_STOP_PCT = -4.0
TOP_N = 5
CONCURRENCY = 32

# V13 实盘三只（你自选列表里的），用于对照
V13_ACTUAL = [("600601", "方正科技"), ("300774", "倍杰特"), ("603291", "联合水务")]


def load_universe() -> List[Dict[str, Any]]:
    path = BACKEND_DIR / "cache" / "universe" / "amount.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen, out = set(), []
    for s in payload.get("data", []):
        code, name = s.get("code"), s.get("name") or ""
        if not code or code in seen:
            continue
        seen.add(code)
        if (s.get("price") or 0) <= 0 or "ST" in name or "退" in name:
            continue
        if (s.get("market_cap_b") or 0) < BLUE_CHIP_CAP:   # V12b 大中盘过滤
            continue
        out.append(s)
    return out


async def fetch_kline(code: str) -> List[Dict[str, Any]]:
    try:
        kl = await eastmoney_api.get_kline_data(code, klt="101", limit=80)
        return [k for k in (kl or []) if k.get("date") <= SELL_DATE]
    except Exception:
        return []


def realized(kl: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    by = {k["date"]: k for k in kl}
    if BUY_DATE not in by or SELL_DATE not in by:
        return None
    bo = float(by[BUY_DATE]["open"]); sc = float(by[SELL_DATE]["close"])
    raw = (sc - bo) / bo * 100
    stop_price = bo * (1 + SINGLE_STOP_PCT / 100)
    single, stopped = raw, False
    for d in HOLD_DAYS:
        if d in by and float(by[d]["low"]) <= stop_price:
            single, stopped = SINGLE_STOP_PCT, True
            break
    return {"buy_open": round(bo, 2), "sell_close": round(sc, 2),
            "raw_ret": round(raw, 2), "single_stop_ret": round(single, 2),
            "stopped": stopped, "hold": [k for k in kl if BUY_DATE <= k["date"] <= SELL_DATE]}


def portfolio(picks: List[Dict[str, Any]]) -> Dict[str, float]:
    if not picks:
        return {"raw": 0.0, "single": 0.0, "port": 0.0}
    w = WEIGHTS[: len(picks)]; tot = sum(w); w = [x / tot for x in w]
    raw = sum(wi * p["raw_ret"] for wi, p in zip(w, picks))
    single = sum(wi * p["single_stop_ret"] for wi, p in zip(w, picks))
    port, flags = single, [False] * len(picks)
    for d in HOLD_DAYS:
        acc = 0.0
        for i, p in enumerate(picks):
            row = next((x for x in p["hold"] if x["date"] == d), None)
            bo = p["buy_open"]
            if row is None:
                pnl = 0.0
            elif flags[i]:
                pnl = SINGLE_STOP_PCT
            else:
                sp = bo * (1 + SINGLE_STOP_PCT / 100)
                if float(row["low"]) <= sp:
                    flags[i] = True; pnl = SINGLE_STOP_PCT
                else:
                    pnl = (float(row["close"]) - bo) / bo * 100
            acc += w[i] * pnl
        if acc <= PORTFOLIO_STOP_PCT:
            port = PORTFOLIO_STOP_PCT
            break
    return {"raw": round(raw, 2), "single": round(single, 2), "port": round(port, 2)}


async def main() -> int:
    stocks = load_universe()
    cap = {s.get("code"): (s.get("market_cap_b") or 0) for s in stocks}
    print("=" * 100)
    print(f"  V12b 周推荐（回滚后）· 重新推荐上周  筛选日 {SCREEN_DATE} → 持仓 {BUY_DATE}~{SELL_DATE}")
    print(f"  universe {len(stocks)} 只（市值≥{BLUE_CHIP_CAP:.0f}亿大中盘·2026-05-24 快照）· 评分=生产 score_reversal(V12b)")
    print("=" * 100)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(stock: Dict[str, Any]):
        async with sem:
            code = stock.get("code")
            kl = await fetch_kline(code)
            hist = [k for k in kl if k.get("date") <= SCREEN_DATE]
            if len(hist) < LOOKBACK_DAYS:
                return None
            c = np.array([k["close"] for k in hist], float)
            o = np.array([k["open"] for k in hist], float)
            h = np.array([k["high"] for k in hist], float)
            l = np.array([k["low"] for k in hist], float)
            v = np.array([k["volume"] for k in hist], float)
            s, det = score_reversal(c, v, {}, opens=o, highs=h, lows=l, return_details=True)
            if s < MIN_REVERSAL_SCORE:
                return None
            ret = realized(kl)
            if ret is None:
                return None
            return {"code": code, "name": stock.get("name", ""), "cap": cap.get(code, 0),
                    "score": float(s), "bounce": det.get("bounce_pct"),
                    "decline_7d": det.get("decline_7d"), "vol_ratio": det.get("vol_ratio"),
                    "rsi6": det.get("rsi6"), **ret}

    res = [r for r in await asyncio.gather(*[one(s) for s in stocks]) if r]
    res.sort(key=lambda x: -x["score"])
    top = res[:TOP_N]

    p = portfolio(top)
    print(f"\n通过 V12b 过滤 {len(res)} 只 · 本次推荐 Top {len(top)}")
    print(f"组合（{[int(x*100) for x in WEIGHTS[:len(top)]]}%）: 原始 {p['raw']:+.2f}% | "
          f"单股-6%止损 {p['single']:+.2f}% | +组合-4%止损 {p['port']:+.2f}%")
    print("-" * 100)
    print(f"{'#':<3}{'代码':<9}{'名称':<10}{'市值亿':>7}{'评分':>5}{'反弹%':>7}{'7日%':>7}"
          f"{'量比':>6}{'RSI6':>6}{'买入':>7}{'卖出':>7}{'周收益%':>8}{'止损后%':>8}")
    for i, c in enumerate(top, 1):
        print(f"{i:<3}{c['code']:<9}{c['name']:<10}{c['cap']:>7.0f}{c['score']:>5.0f}"
              f"{(c['bounce'] or 0):>7.2f}{(c['decline_7d'] or 0):>7.2f}{(c['vol_ratio'] or 0):>6.2f}"
              f"{(c['rsi6'] or 0):>6.1f}{c['buy_open']:>7.2f}{c['sell_close']:>7.2f}"
              f"{c['raw_ret']:>+8.2f}{c['single_stop_ret']:>+8.2f}{'  [止损]' if c['stopped'] else ''}")

    # 和 V13 实盘三只对照
    print("\n" + "-" * 100)
    print("对照：V13 实盘三只（你自选列表）在本次 V12b 排名里的位置")
    rank = {r["code"]: i + 1 for i, r in enumerate(res)}
    for code, name in V13_ACTUAL:
        r = next((x for x in res if x["code"] == code), None)
        if r:
            print(f"  {code} {name}: V12b 仍入选，排名第 {rank[code]}/{len(res)}，评分 {r['score']:.0f}，"
                  f"周收益 {r['raw_ret']:+.2f}%（{'进' if rank[code] <= TOP_N else '未进'} Top5）")
        else:
            print(f"  {code} {name}: V12b 未通过过滤（被剔除）")

    out = {"screen": SCREEN_DATE, "buy": BUY_DATE, "sell": SELL_DATE,
           "universe": len(stocks), "n_pass": len(res), "top": top[:TOP_N],
           "all_ranked": res[:30]}
    (REPO_ROOT / "scripts" / "predict_last_week_v12b_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON saved: scripts/predict_last_week_v12b_result.json")

    session = getattr(eastmoney_module, "_SHARED_SESSION", None)
    if session and not session.closed:
        await session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
