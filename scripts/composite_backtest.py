#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组合(横截面rank)策略回测 vs V12b基线, 分 train(21-23)/test(24-26)。
因子取IC研究里样本外稳健的: 短期反转(rev_5/rev_10) + 低波动(lowvol_20) + 跌破均线(-dist_ma20)。
组合 = 各因子横截面rank加权和, 每周取top-N做多, 同V12b的组合构造(35/25/20/12/8 + -6%/-4%止损)。"""
import pickle, numpy as np, datetime as dt

import pathlib as _pl
PKL = str(_pl.Path(__file__).resolve().parents[1] / "cache" / "kline_5y_portable.pkl")
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]; SS, PS = -6.0, -4.0; TOPN = 5
D = pickle.load(open(PKL, "rb")); CODES = list(D.keys())
ref = max(CODES, key=lambda c: len(D[c]["date"])); DATES = D[ref]["date"]
DIDX = {d: i for i, d in enumerate(DATES)}
WD = [dt.date.fromisoformat(d).weekday() for d in DATES]
WEEK_ENDS = [i for i in range(len(DATES)-1) if WD[i+1] < WD[i]]
A = {}
for c in CODES:
    v = D[c]; A[c] = {"o": np.array(v["open"], float), "h": np.array(v["high"], float),
        "l": np.array(v["low"], float), "c": np.array(v["close"], float), "v": np.array(v["volume"], float),
        "pos": {d: i for i, d in enumerate(v["date"])}}

def shift(a, k):
    o = np.full_like(a, np.nan)
    if 0 < k < len(a): o[k:] = a[:-k]
    return o
def rmean(a, n):
    o = np.full_like(a, np.nan); cs = np.cumsum(np.nan_to_num(a))
    o[n-1:] = (cs[n-1:] - np.concatenate(([0], cs[:-n])))/n; return o
def rstd(a, n):
    o = np.full_like(a, np.nan)
    for i in range(n-1, len(a)): o[i] = a[i-n+1:i+1].std()
    return o

# 因子序列(已定向: 数值越大=预期下周涨越多)
F = {}
for c in CODES:
    cl = A[c]["c"]; ret1 = cl/shift(cl, 1)-1
    F[c] = {
        "rev_5":   -(cl/shift(cl, 5)-1),
        "rev_10":  -(cl/shift(cl, 10)-1),
        "lowvol":  -rstd(ret1, 20),
        "ndist20": -(cl/rmean(cl, 20)-1),
        "nmom60":  -(cl/shift(cl, 60)-1),
    }

def _port(picks, bd, sd):
    seq = DATES[DIDX[bd]:DIDX[sd]+1]
    bps = [A[c]["o"][A[c]["pos"][bd]] if bd in A[c]["pos"] else None for c in picks]
    wr = WEIGHTS[:len(picks)]; t = sum(wr); wr = [x/t for x in wr]
    stp = [False]*len(picks); pf = None
    for d in seq:
        acc = 0.0
        for i, c in enumerate(picks):
            P = A[c]["pos"]; bo = bps[i]
            if bo is None or d not in P: pnl = 0.0
            elif stp[i]: pnl = SS
            else:
                lo = A[c]["l"][P[d]]; clo = A[c]["c"][P[d]]
                if lo <= bo*(1+SS/100): stp[i] = True; pnl = SS
                else: pnl = (clo-bo)/bo*100
            acc += wr[i]*pnl
        if acc <= PS: pf = PS; break
    pp = []
    for i, c in enumerate(picks):
        P = A[c]["pos"]; bo = bps[i]
        if bo is None: pp.append(0.0)
        elif stp[i]: pp.append(SS)
        else: pp.append((A[c]["c"][P[sd]]-bo)/bo*100 if sd in P else 0.0)
    return pf if pf is not None else sum(wr[i]*pp[i] for i in range(len(picks)))

def rank01(x):
    r = np.argsort(np.argsort(x)).astype(float)
    return r/(len(x)-1) if len(x) > 1 else r

def run_composite(weights: dict):
    """weights: {factor: w}. 每周横截面rank加权 → top-N。"""
    out = []
    for w in range(len(WEEK_ENDS)-1):
        si = WEEK_ENDS[w]; screen = DATES[si]; yr = screen[:4]
        bd = DATES[si+1]; sd = DATES[WEEK_ENDS[w+1]]
        elig = []; fv = {f: [] for f in weights}
        for c in CODES:
            j = A[c]["pos"].get(screen, -1)
            if j < 130: continue
            if bd not in A[c]["pos"] or sd not in A[c]["pos"]: continue
            vals = {f: F[c][f][j] for f in weights}
            if any(not np.isfinite(v) for v in vals.values()): continue
            elig.append(c)
            for f in weights: fv[f].append(vals[f])
        if len(elig) < 30: continue
        score = np.zeros(len(elig))
        for f, wt in weights.items():
            score += wt*rank01(np.array(fv[f]))
        order = np.argsort(-score)
        picks = [elig[i] for i in order[:TOPN]]
        out.append((yr, _port(picks, bd, sd)))
    return out

def run_v12b():
    """V12b(去ATR)绝对评分 top-N, 作基准。"""
    def score(o, h, l, c, v):
        if len(c) < 30: return None
        d7 = (c[-1]-c[-8])/c[-8]*100 if c[-8] > 0 else 0
        if d7 > -5 or d7 < -25: return None
        low5 = l[-5:].min(); b = (c[-1]-low5)/low5*100 if low5 > 0 else 0
        if b < 3.5: return None
        va = v[-6:-1].mean(); vr = v[-1]/va if va > 0 else 0
        if va > 0 and vr < 1.2: return None
        s = (20 if b > 8 else 17 if b > 6 else 13 if b > 4 else 9 if b > 3 else 5)
        rg = (c[-1]-c[-2])/c[-2]*100+(c[-2]-c[-3])/c[-3]*100 if c[-2] > 0 and c[-3] > 0 else 0
        s += 12 if rg > 6 else 7 if rg > 2 else 0
        s += 8 if d7 < -15 else 6 if d7 < -10 else 4 if d7 < -8 else 2
        s += 18 if vr > 3 else 12 if vr > 2 else 8 if vr > 1.5 else 4
        s += 6 if v[-1] > v[-2] else 0
        dd = np.diff(c[-7:]); g = np.where(dd > 0, dd, 0).mean(); ll = np.where(dd < 0, -dd, 0).mean()
        r = 100.0 if ll == 0 else 100-100/(1+g/ll)
        s += 10 if r < 30 else 3 if r < 45 else 0
        return s if s >= 40 else None
    out = []
    for w in range(len(WEEK_ENDS)-1):
        si = WEEK_ENDS[w]; screen = DATES[si]; yr = screen[:4]
        bd = DATES[si+1]; sd = DATES[WEEK_ENDS[w+1]]; sc = []
        for c in CODES:
            j = A[c]["pos"].get(screen, -1)
            if j < 80: continue
            if bd not in A[c]["pos"] or sd not in A[c]["pos"]: continue
            sl = slice(j-79, j+1)
            s = score(A[c]["o"][sl], A[c]["h"][sl], A[c]["l"][sl], A[c]["c"][sl], A[c]["v"][sl])
            if s is not None: sc.append((c, s))
        sc.sort(key=lambda x: -x[1]); picks = [c for c, _ in sc[:TOPN]]
        if picks: out.append((yr, _port(picks, bd, sd)))
    return out

def stat(weeks, lo, hi):
    r = np.array([x[1] for x in weeks if lo <= x[0] <= hi])
    if len(r) == 0: return None
    eq = np.cumprod(1+r/100); peak = np.maximum.accumulate(eq)
    return {"n": len(r), "cum": (eq[-1]-1)*100, "avg": r.mean(), "win": (r > 0).mean()*100,
            "sharpe": r.mean()/r.std()*np.sqrt(50) if r.std() > 0 else 0, "mdd": ((eq-peak)/peak*100).min()}

STRATS = {
    "V12b基线(去ATR)": run_v12b(),
    "C1 纯反转rev5":     run_composite({"rev_5": 1}),
    "C2 反转+低波":       run_composite({"rev_5": 1, "lowvol": 1}),
    "C3 反转x2+低波":     run_composite({"rev_5": 1, "rev_10": 1, "lowvol": 1}),
    "C4 4因子等权":       run_composite({"rev_5": 1, "rev_10": 1, "lowvol": 1, "ndist20": 1}),
    "C5 5因子(含-mom60)": run_composite({"rev_5": 1, "rev_10": 1, "lowvol": 1, "ndist20": 1, "nmom60": 1}),
}
for seg, lo, hi in [("训练 21-23", "2021", "2023"), ("样本外 24-26", "2024", "2026")]:
    print(f"\n{'='*88}\n[{seg}]\n{'='*88}")
    print(f"{'策略':<22}{'周':>4}{'累计%':>9}{'均周%':>7}{'周胜率':>7}{'夏普':>7}{'回撤%':>8}")
    for name, wk in STRATS.items():
        s = stat(wk, lo, hi)
        if s: print(f"{name:<22}{s['n']:>4}{s['cum']:>+9.1f}{s['avg']:>+7.2f}{s['win']:>6.0f}%{s['sharpe']:>7.2f}{s['mdd']:>+8.1f}")
