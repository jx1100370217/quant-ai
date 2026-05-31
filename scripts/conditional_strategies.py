#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保留V12b的条件过滤(它真正的α来源), 但用IC稳健因子给幸存者重新排序。
全周期口径(不交易的周=0%), 分 train(21-23)/test(24-26)。"""
import pickle, numpy as np, datetime as dt
import pathlib as _pl
PKL = str(_pl.Path(__file__).resolve().parents[1] / "cache" / "kline_5y_portable.pkl")
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]; SS, PS = -6.0, -4.0; TOPN = 5
D = pickle.load(open(PKL, "rb")); CODES = list(D.keys())
ref = max(CODES, key=lambda c: len(D[c]["date"])); DATES = D[ref]["date"]; DIDX = {d: i for i, d in enumerate(DATES)}
WD = [dt.date.fromisoformat(d).weekday() for d in DATES]; WEEK_ENDS = [i for i in range(len(DATES)-1) if WD[i+1] < WD[i]]
A = {}
for c in CODES:
    v = D[c]; A[c] = {"o": np.array(v["open"], float), "h": np.array(v["high"], float), "l": np.array(v["low"], float),
                      "c": np.array(v["close"], float), "v": np.array(v["volume"], float), "pos": {d: i for i, d in enumerate(v["date"])}}
def shift(a, k):
    o = np.full_like(a, np.nan)
    if 0 < k < len(a): o[k:] = a[:-k]
    return o
def rmean(a, n):
    o = np.full_like(a, np.nan); cs = np.cumsum(np.nan_to_num(a)); o[n-1:] = (cs[n-1:]-np.concatenate(([0], cs[:-n])))/n; return o
def rstd(a, n):
    o = np.full_like(a, np.nan)
    for i in range(n-1, len(a)): o[i] = a[i-n+1:i+1].std()
    return o
F = {}
for c in CODES:
    cl = A[c]["c"]; r1 = cl/shift(cl, 1)-1
    F[c] = {"rev5": -(cl/shift(cl, 5)-1), "rev10": -(cl/shift(cl, 10)-1), "lowvol": -rstd(r1, 20),
            "bounce": (cl-np.array([np.nan]*4+[A[c]["l"][max(0,i-4):i+1].min() for i in range(4, len(cl))]))/1.0}  # placeholder
    # bounce5 properly:
    low5 = np.full_like(cl, np.nan)
    for i in range(4, len(cl)): low5[i] = A[c]["l"][i-4:i+1].min()
    F[c]["bounce"] = (cl-low5)/np.where(low5 > 0, low5, np.nan)

def v12b_score(o, h, l, c, v):
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
    r = 100.0 if ll == 0 else 100-100/(1+g/ll); s += 10 if r < 30 else 3 if r < 45 else 0
    return s if s >= 40 else None

def passes(o, h, l, c, v, require_bounce):
    if len(c) < 30: return False
    d7 = (c[-1]-c[-8])/c[-8]*100 if c[-8] > 0 else 0
    if d7 > -5 or d7 < -25: return False
    if require_bounce:
        low5 = l[-5:].min(); b = (c[-1]-low5)/low5*100 if low5 > 0 else 0
        if b < 3.5: return False
    va = v[-6:-1].mean(); vr = v[-1]/va if va > 0 else 0
    if va > 0 and vr < 1.2: return False
    return True

def _port(picks, bd, sd):
    seq = DATES[DIDX[bd]:DIDX[sd]+1]; bps = [A[c]["o"][A[c]["pos"][bd]] if bd in A[c]["pos"] else None for c in picks]
    wr = WEIGHTS[:len(picks)]; t = sum(wr); wr = [x/t for x in wr]; stp = [False]*len(picks); pf = None
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
    return np.argsort(np.argsort(x)).astype(float)/(len(x)-1) if len(x) > 1 else np.zeros(len(x))

def run(rank_mode, require_bounce=True):
    out = []
    for w in range(len(WEEK_ENDS)-1):
        si = WEEK_ENDS[w]; screen = DATES[si]; yr = screen[:4]; bd = DATES[si+1]; sd = DATES[WEEK_ENDS[w+1]]
        surv = []
        for c in CODES:
            j = A[c]["pos"].get(screen, -1)
            if j < 80: continue
            if bd not in A[c]["pos"] or sd not in A[c]["pos"]: continue
            sl = slice(j-79, j+1)
            o, h, l, cc, vv = A[c]["o"][sl], A[c]["h"][sl], A[c]["l"][sl], A[c]["c"][sl], A[c]["v"][sl]
            if rank_mode == "score":
                s = v12b_score(o, h, l, cc, vv)
                if s is None: continue
                surv.append((c, s, None))
            else:
                if not passes(o, h, l, cc, vv, require_bounce): continue
                fac = {k: F[c][k][j] for k in ("rev5", "rev10", "lowvol", "bounce")}
                if any(not np.isfinite(x) for x in fac.values()): continue
                surv.append((c, None, fac))
        if not surv: out.append((yr, 0.0)); continue
        if rank_mode == "score":
            surv.sort(key=lambda x: -x[1]); picks = [c for c, _, _ in surv[:TOPN]]
        else:
            codes = [c for c, _, _ in surv]
            facmat = {k: np.array([f[k] for _, _, f in surv]) for k in ("rev5", "rev10", "lowvol", "bounce")}
            if rank_mode == "rev5": sc = rank01(facmat["rev5"])
            elif rank_mode == "nbounce": sc = rank01(-facmat["bounce"])
            elif rank_mode == "lowvol": sc = rank01(facmat["lowvol"])
            elif rank_mode == "combo": sc = rank01(facmat["rev5"]) + rank01(facmat["lowvol"]) + rank01(-facmat["bounce"])
            elif rank_mode == "combo2": sc = rank01(facmat["rev5"]) + rank01(facmat["rev10"]) + rank01(facmat["lowvol"])
            order = np.argsort(-sc); picks = [codes[i] for i in order[:TOPN]]
        out.append((yr, _port(picks, bd, sd)))
    return out

def stat(weeks, lo, hi):
    r = np.array([x[1] for x in weeks if lo <= x[0] <= hi])
    eq = np.cumprod(1+r/100); peak = np.maximum.accumulate(eq)
    return {"n": len(r), "cum": (eq[-1]-1)*100, "avg": r.mean(), "win": (r > 0).mean()*100,
            "sharpe": r.mean()/r.std()*np.sqrt(50) if r.std() > 0 else 0, "mdd": ((eq-peak)/peak*100).min()}

STR = {
    "V12b基线(score排序)":      run("score"),
    "V12b过滤+rev5排序":        run("rev5"),
    "V12b过滤+(-bounce)排序":   run("nbounce"),
    "V12b过滤+lowvol排序":      run("lowvol"),
    "V12b过滤+combo排序":       run("combo"),
    "V12b过滤+combo2排序":      run("combo2"),
    "去bounce要求+combo":       run("combo", require_bounce=False),
    "去bounce要求+rev5":        run("rev5", require_bounce=False),
}
for seg, lo, hi in [("训练 21-23", "2021", "2023"), ("样本外 24-26", "2024", "2026")]:
    print(f"\n{'='*86}\n[{seg}]  (全周期口径, 不交易周=0%)\n{'='*86}")
    print(f"{'策略':<24}{'周':>4}{'累计%':>9}{'均周%':>7}{'周胜率':>7}{'夏普':>7}{'回撤%':>8}")
    for name, wk in STR.items():
        s = stat(wk, lo, hi)
        print(f"{name:<24}{s['n']:>4}{s['cum']:>+9.1f}{s['avg']:>+7.2f}{s['win']:>6.0f}%{s['sharpe']:>7.2f}{s['mdd']:>+8.1f}")
