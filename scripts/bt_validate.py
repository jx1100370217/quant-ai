#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分年 + 样本外(train/test) 验证: 去ATR 优化是否在所有历史区间都稳健,
不是只在全样本平均上好看(防过拟合)。复用 backtest_engine 的数据与打分。"""
import importlib.util, numpy as np, datetime as dt
import pathlib as _pl
spec = importlib.util.spec_from_file_location("E", str(_pl.Path(__file__).resolve().parent / "backtest_engine.py"))
E = importlib.util.module_from_spec(spec)
# 阻止其 __main__ 段运行
import sys; sys.argv = ["x"]
spec.loader.exec_module(E)

CODES, DATES, A, WEEK_ENDS, BENCH_W = E.CODES, E.DATES, E.A, E.WEEK_ENDS, E.BENCH_W
IDX_LVL, IDX_MA20, WIN, WEIGHTS = E.IDX_LVL, E.IDX_MA20, E.WIN, E.WEIGHTS


def run(strat, soft_regime=False, take_profit=None, topn=5):
    """返回每周 (year, ret, bench)。"""
    out = []
    for w in range(len(WEEK_ENDS) - 1):
        si = WEEK_ENDS[w]
        if si + 1 >= len(DATES): continue
        bd, sd = DATES[si + 1], DATES[WEEK_ENDS[w + 1]]
        screen = DATES[si]; yr = screen[:4]; bench = BENCH_W[w]
        regime_ok = (not np.isnan(IDX_MA20[si])) and (IDX_LVL[si] > IDX_MA20[si])
        scale = 0.5 if (soft_regime and not regime_ok) else 1.0
        scored = []
        for c in CODES:
            P = A[c]["pos"]; j = P.get(screen, -1)
            if j < WIN: continue
            sl = slice(j - WIN + 1, j + 1)
            s = strat(A[c]["o"][sl], A[c]["h"][sl], A[c]["l"][sl], A[c]["c"][sl], A[c]["v"][sl])
            if s is not None: scored.append((c, s))
        scored.sort(key=lambda x: -x[1]); picks = scored[:topn]
        if not picks: out.append((yr, 0.0, bench)); continue
        wr = WEIGHTS[:len(picks)]; t = sum(wr); wr = [x/t for x in wr]
        pr = E._port(picks, bd, sd, wr, take_profit=take_profit)
        out.append((yr, pr["ret"] * scale, bench))
    return out


def stats(weeks):
    r = np.array([x[1] for x in weeks]); b = np.array([x[2] for x in weeks])
    if len(r) == 0: return None
    eq = np.cumprod(1 + r/100); peak = np.maximum.accumulate(eq)
    mdd = ((eq - peak)/peak*100).min()
    return {"n": len(r), "cum": (eq[-1]-1)*100, "avg": r.mean(), "win": (r > 0).mean()*100,
            "beat": (r > b).mean()*100, "sharpe": r.mean()/r.std()*np.sqrt(50) if r.std() > 0 else 0,
            "mdd": mdd, "bench": (np.cumprod(1+b/100)[-1]-1)*100}


def by_year(weeks):
    years = sorted({x[0] for x in weeks})
    return {y: stats([x for x in weeks if x[0] == y]) for y in years}


base = run(E.score_v12b)
noatr = run(lambda o,h,l,c,v: E.score_v12b(o,h,l,c,v, no_atr=True))
noatr_soft = run(lambda o,h,l,c,v: E.score_v12b(o,h,l,c,v, no_atr=True), soft_regime=True)

print("="*92)
print("分年验证: 每年 累计% (夏普) — 看去ATR是否每年都不输基线")
print("="*92)
print(f"{'年份':<8}{'V12b基线':>22}{'去ATR(已上线)':>24}{'去ATR+弱市半仓':>26}{'基准%':>9}")
by = {"base": by_year(base), "noatr": by_year(noatr), "soft": by_year(noatr_soft)}
years = sorted(by["base"].keys())
wins = 0
for y in years:
    a, n, s = by["base"][y], by["noatr"][y], by["soft"][y]
    flag = "✓" if n["cum"] >= a["cum"] else "✗"
    if n["cum"] >= a["cum"]: wins += 1
    print(f"{y:<8}{a['cum']:>+13.1f} ({a['sharpe']:>4.2f}){n['cum']:>+14.1f} ({n['sharpe']:>4.2f}){flag}{s['cum']:>+15.1f} ({s['sharpe']:>4.2f}){a['bench']:>+9.1f}")
print(f"\n去ATR 在 {wins}/{len(years)} 个年份 累计≥基线")

print("\n" + "="*92)
print("样本外验证 (train 2021-2023 / test 2024-2026) — 优化不能只在训练段好")
print("="*92)
def split(weeks, lo, hi): return [x for x in weeks if lo <= x[0] <= hi]
for seg, lo, hi in [("训练 21-23", "2021", "2023"), ("样本外 24-26", "2024", "2026")]:
    a = stats(split(base, lo, hi)); n = stats(split(noatr, lo, hi)); s = stats(split(noatr_soft, lo, hi))
    print(f"\n[{seg}]  周数 {a['n']}")
    print(f"  V12b基线      累计{a['cum']:>+8.1f}% 夏普{a['sharpe']:>5.2f} 回撤{a['mdd']:>+7.1f}% 周胜{a['win']:>4.0f}% 跑赢{a['beat']:>4.0f}%")
    print(f"  去ATR         累计{n['cum']:>+8.1f}% 夏普{n['sharpe']:>5.2f} 回撤{n['mdd']:>+7.1f}% 周胜{n['win']:>4.0f}% 跑赢{n['beat']:>4.0f}%")
    print(f"  去ATR+弱市半仓 累计{s['cum']:>+8.1f}% 夏普{s['sharpe']:>5.2f} 回撤{s['mdd']:>+7.1f}% 周胜{s['win']:>4.0f}% 跑赢{s['beat']:>4.0f}%")
