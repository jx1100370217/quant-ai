#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""因子IC研究: 逐周算各候选因子与"下周收益(周一开→周五收)"的 Spearman IC,
分 train(2021-2023)/test(2024-2026) 统计, 找样本外稳健的预测因子。
数据: cache/kline_5y_portable.pkl (800 大中盘, 2020-12~2026-04, 前复权)。"""
import pickle, numpy as np

import pathlib as _pl
PKL = str(_pl.Path(__file__).resolve().parents[1] / "cache" / "kline_5y_portable.pkl")
D = pickle.load(open(PKL, "rb"))
CODES = list(D.keys())
ref = max(CODES, key=lambda c: len(D[c]["date"]))
DATES = D[ref]["date"]
import datetime as dt
WD = [dt.date.fromisoformat(d).weekday() for d in DATES]
WEEK_ENDS = [i for i in range(len(DATES) - 1) if WD[i + 1] < WD[i]]

A = {}
for c in CODES:
    v = D[c]
    A[c] = {"o": np.array(v["open"], float), "h": np.array(v["high"], float),
            "l": np.array(v["low"], float), "c": np.array(v["close"], float),
            "v": np.array(v["volume"], float),
            "pos": {d: i for i, d in enumerate(v["date"])}}


def shift(a, k):
    out = np.full_like(a, np.nan)
    if k < len(a): out[k:] = a[:-k] if k > 0 else a
    return out

def roll_mean(a, n):
    out = np.full_like(a, np.nan); cs = np.cumsum(a)
    out[n-1:] = (cs[n-1:] - np.concatenate(([0], cs[:-n]))) / n
    return out

def roll_min(a, n):
    out = np.full_like(a, np.nan)
    for i in range(n-1, len(a)): out[i] = a[i-n+1:i+1].min()
    return out

def roll_max(a, n):
    out = np.full_like(a, np.nan)
    for i in range(n-1, len(a)): out[i] = a[i-n+1:i+1].max()
    return out

def roll_std(a, n):
    out = np.full_like(a, np.nan)
    for i in range(n-1, len(a)): out[i] = a[i-n+1:i+1].std()
    return out

def rsi(c, n):
    d = np.diff(c, prepend=c[0]); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = roll_mean(g, n); al = roll_mean(l, n)
    return 100 - 100/(1 + ag/np.where(al == 0, np.nan, al))


# ── 预计算每只票的因子时间序列 ──
F = {}
for c in CODES:
    cl = A[c]["c"]; op = A[c]["o"]; hi = A[c]["h"]; lo = A[c]["l"]; vo = A[c]["v"]
    ret1 = cl/shift(cl, 1) - 1
    ma20 = roll_mean(cl, 20); ma60 = roll_mean(cl, 60); ma120 = roll_mean(cl, 120)
    vol20 = roll_std(ret1, 20)
    low5 = roll_min(lo, 5); max252 = roll_max(hi, 252)
    vma5 = roll_mean(vo, 5); vma20 = roll_mean(vo, 20)
    F[c] = {
        # 动量 (正=近期强)
        "mom_20":   cl/shift(cl, 20) - 1,
        "mom_60":   cl/shift(cl, 60) - 1,
        "mom_120s20": shift(cl, 20)/shift(cl, 120) - 1,   # 6月动量跳过近月
        # 反转 (正=近期弱, 用负号)
        "rev_5":   -(cl/shift(cl, 5) - 1),
        "rev_10":  -(cl/shift(cl, 10) - 1),
        "rev_1":   -(cl/shift(cl, 1) - 1),
        # 趋势/位置
        "dist_ma20": cl/ma20 - 1,
        "dist_ma60": cl/ma60 - 1,
        "ma20_ma60": ma20/ma60 - 1,
        "near_52wh": cl/max252,                # 越接近52周高越大
        # 波动 (低波动溢价: 用负号)
        "lowvol_20": -vol20,
        # 量能
        "volratio":  vo/vma5,
        "vol_trend": vma5/vma20,               # 近量/月量
        # 超买超卖
        "rsi6":  rsi(cl, 6),
        "rsi14": rsi(cl, 14),
        # 深V反弹 (V12b 核心信号)
        "bounce5": (cl - low5)/low5,
        # 隔夜跳空均值(近5日开盘相对昨收)
        "gap5": roll_mean(np.nan_to_num(op/shift(cl, 1) - 1, nan=0.0), 5),
    }

FACTORS = list(F[ref].keys())


def rank(x):
    return np.argsort(np.argsort(x)).astype(float)


ic_tr = {f: [] for f in FACTORS}
ic_te = {f: [] for f in FACTORS}
for w in range(len(WEEK_ENDS) - 1):
    si = WEEK_ENDS[w]; screen = DATES[si]; yr = screen[:4]
    bd = DATES[si + 1]; sd = DATES[WEEK_ENDS[w + 1]]
    fvec = {f: [] for f in FACTORS}; fwd = []
    for c in CODES:
        P = A[c]["pos"]; j = P.get(screen, -1)
        if j < 130: continue
        pb = P.get(bd, -1); ps = P.get(sd, -1)
        if pb < 0 or ps < 0: continue
        bo = A[c]["o"][pb]; sc = A[c]["c"][ps]
        if bo <= 0: continue
        for f in FACTORS: fvec[f].append(F[c][f][j])   # 可能含 nan, 下面逐因子掩码
        fwd.append((sc - bo) / bo)
    if len(fwd) < 30: continue
    fwd = np.array(fwd)
    tgt = ic_tr if yr <= "2023" else ic_te
    for f in FACTORS:
        xv = np.array(fvec[f])
        m = np.isfinite(xv) & np.isfinite(fwd)
        if m.sum() < 30 or xv[m].std() == 0: continue
        tgt[f].append(np.corrcoef(rank(xv[m]), rank(fwd[m]))[0, 1])


def summ(d):
    a = np.array(d)
    return (np.mean(a), np.mean(a)/np.std(a) if np.std(a) > 0 else 0, (a > 0).mean()*100, len(a))


print(f"universe {len(CODES)} | 周 {len(WEEK_ENDS)} | IC=每周因子↔下周收益(周一开→周五收) Spearman, 跨周平均")
print("="*96)
print(f"{'因子':<14}{'train IC':>10}{'train ICIR':>11}{'tr>0%':>7}   {'test IC':>10}{'test ICIR':>11}{'te>0%':>7}  稳健?")
print("-"*96)
rows = []
for f in FACTORS:
    tr = summ(ic_tr[f]); te = summ(ic_te[f])
    rows.append((f, tr, te))
# 按 |test IC| 排序
rows.sort(key=lambda r: -abs(r[2][0]))
for f, tr, te in rows:
    robust = "✓" if (np.sign(tr[0]) == np.sign(te[0]) and abs(te[0]) > 0.01 and te[1]*np.sign(te[0]) > 0.1) else ""
    print(f"{f:<14}{tr[0]:>+10.3f}{tr[1]:>+11.2f}{tr[2]:>6.0f}%   {te[0]:>+10.3f}{te[1]:>+11.2f}{te[2]:>6.0f}%   {robust}")
print("\n说明: IC>0=因子值越大下周涨越多; <0=越大越跌(取负即正向). ICIR=IC均值/IC标准差(稳定性).")
print("稳健✓ = train/test 同号 且 |test IC|>0.01 且 test 方向稳定。")
