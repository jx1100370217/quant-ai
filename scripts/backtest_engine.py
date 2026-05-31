#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多年周度回测引擎 v2（沙箱·本地5年数据·无网络）。
修复: 择时闸门bug; 提速(只切最近80日+预计算基准); 参数化V12b做加法式改进对比。
注意: universe=当前HS300+ZZ500成分, 含明显幸存者偏差, 绝对收益被高估,
      看相对(vs同口径基准)和风险指标更可靠。"""
import pickle, datetime as dt
import numpy as np

import pathlib as _pl
PKL = str(_pl.Path(__file__).resolve().parents[1] / "cache" / "kline_5y_portable.pkl")
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]
SINGLE_STOP, PORT_STOP = -6.0, -4.0
WIN = 80   # 只把最近 80 日喂给打分(提速; MA60/RSI/bounce 都够用)

D = pickle.load(open(PKL, "rb"))
CODES = list(D.keys())
ref = max(CODES, key=lambda c: len(D[c]["date"]))
DATES = D[ref]["date"]
DIDX = {d: i for i, d in enumerate(DATES)}
WD = [dt.date.fromisoformat(d).weekday() for d in DATES]
A = {}
for c in CODES:
    v = D[c]
    A[c] = {"o": np.array(v["open"], float), "h": np.array(v["high"], float),
            "l": np.array(v["low"], float), "c": np.array(v["close"], float),
            "v": np.array(v["volume"], float),
            "pos": {d: i for i, d in enumerate(v["date"])}}
WEEK_ENDS = [i for i in range(len(DATES) - 1) if WD[i + 1] < WD[i]]


def build_index():
    idx_ret = np.zeros(len(DATES))
    for k in range(1, len(DATES)):
        d0, d1 = DATES[k - 1], DATES[k]
        rs = []
        for c in CODES:
            P = A[c]["pos"]
            if d0 in P and d1 in P:
                a = A[c]["c"][P[d0]]; b = A[c]["c"][P[d1]]
                if a > 0: rs.append((b - a) / a)
        idx_ret[k] = np.mean(rs) if rs else 0.0
    lvl = np.cumprod(1 + idx_ret)
    ma20 = np.array([lvl[k-19:k+1].mean() if k >= 19 else np.nan for k in range(len(DATES))])
    return lvl, ma20

IDX_LVL, IDX_MA20 = build_index()


def _fwd(c, buy_d, sell_d):
    P = A[c]["pos"]
    if buy_d not in P or sell_d not in P: return None
    bo = A[c]["o"][P[buy_d]]; sc = A[c]["c"][P[sell_d]]
    return (sc - bo) / bo * 100 if bo > 0 else None

# 预计算每周基准(等权)收益 + 候选用的 forward map
BENCH_W = []
for w in range(len(WEEK_ENDS) - 1):
    si = WEEK_ENDS[w]
    if si + 1 >= len(DATES): BENCH_W.append(0.0); continue
    bd, sd = DATES[si + 1], DATES[WEEK_ENDS[w + 1]]
    rs = [_fwd(c, bd, sd) for c in CODES]; rs = [x for x in rs if x is not None]
    BENCH_W.append(float(np.mean(rs)) if rs else 0.0)


def _rsi(c, period=6):
    d = np.diff(c[-(period + 1):]); g = np.where(d > 0, d, 0); l = np.where(d < 0, -d, 0)
    ag, al = g.mean(), l.mean()
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def score_v12b(o, h, l, c, v, dec7_floor=-25.0, rsi_excl=None, need_ma60=False, no_atr=False):
    """当前生产 V12b/score_v7。可加法式改进:
       dec7_floor: 7日跌幅下限(默认-25; 设-15可去掉最深跌的接刀)
       rsi_excl:   RSI6 低于此值剔除(默认None; 设20去极端超卖)
       need_ma60:  要求收盘 > MA60(趋势过滤, 默认False)"""
    if len(c) < 30: return None
    dec7 = (c[-1] - c[-8]) / c[-8] * 100 if c[-8] > 0 else 0
    if dec7 > -5 or dec7 < dec7_floor: return None
    low5 = l[-5:].min(); bounce = (c[-1] - low5) / low5 * 100 if low5 > 0 else 0
    if bounce < 3.5: return None
    va5 = v[-6:-1].mean(); vr = v[-1] / va5 if va5 > 0 else 0
    if va5 > 0 and vr < 1.2: return None
    r = _rsi(c)
    if rsi_excl is not None and r < rsi_excl: return None
    if need_ma60 and len(c) >= 60 and c[-1] <= c[-60:].mean(): return None
    s = 0
    s += 20 if bounce > 8 else 17 if bounce > 6 else 13 if bounce > 4 else 9 if bounce > 3 else 5
    rg = (c[-1]-c[-2])/c[-2]*100 + (c[-2]-c[-3])/c[-3]*100 if c[-2] > 0 and c[-3] > 0 else 0
    s += 12 if rg > 6 else 7 if rg > 2 else 0
    s += 8 if dec7 < -15 else 6 if dec7 < -10 else 4 if dec7 < -8 else 2
    s += 18 if vr > 3 else 12 if vr > 2 else 8 if vr > 1.5 else 4
    s += 6 if v[-1] > v[-2] else 0
    if (not no_atr) and len(h) >= 20:
        atr = (h[-20:] - l[-20:]).mean() / c[-1] * 100
        s += 12 if atr > 5 else 6 if atr > 3 else 0
    s += 10 if r < 30 else 3 if r < 45 else 0
    s = round(min(100, max(0, s)), 2)
    return s if s >= 40 else None


def backtest(strat, regime_gate=False, soft_regime=False, take_profit=None, topn=5, label=""):
    rets, ic_list = [], []
    eq = peak = 1.0; mdd = 0.0; stock_w = stock_n = 0; cash = 0
    for w in range(len(WEEK_ENDS) - 1):
        si = WEEK_ENDS[w]
        if si + 1 >= len(DATES): continue
        bd, sd = DATES[si + 1], DATES[WEEK_ENDS[w + 1]]
        bench = BENCH_W[w]
        regime_ok = (not np.isnan(IDX_MA20[si])) and (IDX_LVL[si] > IDX_MA20[si])
        if regime_gate and not regime_ok:
            rets.append(0.0); cash += 1; continue
        scale = 0.5 if (soft_regime and not regime_ok) else 1.0
        scored, ic_pairs = [], []
        screen = DATES[si]
        for c in CODES:
            P = A[c]["pos"]
            j = P.get(screen, -1)
            if j < WIN: continue
            sl = slice(j - WIN + 1, j + 1)
            s = strat(A[c]["o"][sl], A[c]["h"][sl], A[c]["l"][sl], A[c]["c"][sl], A[c]["v"][sl])
            if s is None: continue
            fr = _fwd(c, bd, sd)
            if fr is None: continue
            scored.append((c, s)); ic_pairs.append((s, fr))
        if len(ic_pairs) >= 5:
            ss = np.array([x[0] for x in ic_pairs]); ff = np.array([x[1] for x in ic_pairs])
            if ss.std() > 0 and ff.std() > 0:
                ic_list.append(np.corrcoef(np.argsort(np.argsort(ss)), np.argsort(np.argsort(ff)))[0, 1])
        scored.sort(key=lambda x: -x[1])
        picks = scored[:topn]
        if not picks:
            rets.append(0.0); cash += 1
            eq *= 1; peak = max(peak, eq); mdd = min(mdd, (eq-peak)/peak*100); continue
        wr = WEIGHTS[:len(picks)]; tot = sum(wr); wr = [x/tot for x in wr]
        pr = _port(picks, bd, sd, wr, take_profit=take_profit)
        week_ret = pr["ret"] * scale
        rets.append(week_ret)
        for x in pr["picks"]:
            stock_n += 1; stock_w += 1 if x > 0 else 0
        eq *= (1 + week_ret/100); peak = max(peak, eq); mdd = min(mdd, (eq-peak)/peak*100)
    rets = np.array(rets); bw = np.array(BENCH_W[:len(rets)])
    return {"label": label, "weeks": len(rets), "cum": round((eq-1)*100, 1),
            "avg_w": round(rets.mean(), 3), "win_w": round((rets > 0).mean()*100, 1),
            "beat": round((rets > bw).mean()*100, 1),
            "sharpe": round(rets.mean()/rets.std()*np.sqrt(50), 2) if rets.std() > 0 else 0,
            "mdd": round(mdd, 1), "cash": cash, "stock_wr": round(stock_w/max(1, stock_n)*100, 1),
            "ic": round(np.mean(ic_list), 3) if ic_list else None,
            "ic_pos": round(float((np.array(ic_list) > 0).mean()*100), 0) if ic_list else None}


def _port(picks, bd, sd, wr, take_profit=None):
    seq = DATES[DIDX[bd]:DIDX[sd] + 1]
    bps = [A[c]["o"][A[c]["pos"][bd]] if bd in A[c]["pos"] else None for c, _ in picks]
    stopped = [False]*len(picks); tp_hit = [False]*len(picks); port_final = None
    for d in seq:
        acc = 0.0
        for i, (c, _) in enumerate(picks):
            P = A[c]["pos"]; bo = bps[i]
            if bo is None or d not in P: pnl = 0.0
            elif stopped[i]: pnl = SINGLE_STOP
            elif tp_hit[i]: pnl = take_profit
            else:
                lo = A[c]["l"][P[d]]; hi = A[c]["h"][P[d]]; cl = A[c]["c"][P[d]]
                if lo <= bo*(1+SINGLE_STOP/100): stopped[i] = True; pnl = SINGLE_STOP   # 止损优先(保守)
                elif take_profit is not None and hi >= bo*(1+take_profit/100): tp_hit[i] = True; pnl = take_profit
                else: pnl = (cl-bo)/bo*100
            acc += wr[i]*pnl
        if acc <= PORT_STOP: port_final = PORT_STOP; break
    pp = []
    for i, (c, _) in enumerate(picks):
        P = A[c]["pos"]; bo = bps[i]
        if bo is None: pp.append(0.0)
        elif stopped[i]: pp.append(SINGLE_STOP)
        elif tp_hit[i]: pp.append(take_profit)
        else: pp.append((A[c]["c"][P[sd]]-bo)/bo*100 if sd in P else 0.0)
    ret = port_final if port_final is not None else sum(wr[i]*pp[i] for i in range(len(picks)))
    return {"ret": round(ret, 3), "picks": pp}


if __name__ == "__main__":
    bench_cum = round((np.cumprod(1 + np.array(BENCH_W)/100)[-1]-1)*100, 1)
    print(f"universe {len(CODES)} | 交易日 {len(DATES)} ({DATES[0]}~{DATES[-1]}) | 周 {len(WEEK_ENDS)} | 基准等权累计 {bench_cum:+.1f}%")
    print("（注意: 成分股幸存者偏差，绝对收益偏高，重点看相对/风险/IC）\n")
    hdr = f"{'策略':<26}{'周':>4}{'累计%':>9}{'均周':>6}{'周胜':>6}{'跑赢':>6}{'夏普':>6}{'回撤':>7}{'空仓':>5}{'股胜':>6}{'IC':>7}{'IC>0':>6}"
    print(hdr); print("-"*len(hdr))
    runs = [
        ("V12b 基线",                      dict()),
        ("A: no_atr",                      dict(strat_kw=dict(no_atr=True))),
        ("B: no_atr +止盈5%",              dict(take_profit=5.0, strat_kw=dict(no_atr=True))),
        ("C: no_atr +止盈8%",              dict(take_profit=8.0, strat_kw=dict(no_atr=True))),
        ("D: no_atr +软择时",              dict(soft_regime=True, strat_kw=dict(no_atr=True))),
        ("E: no_atr +软择时+止盈8%",       dict(soft_regime=True, take_profit=8.0, strat_kw=dict(no_atr=True))),
        ("F: no_atr +软择时+止盈5%",       dict(soft_regime=True, take_profit=5.0, strat_kw=dict(no_atr=True))),
        ("G: no_atr +软择时+Top8+止盈8%",  dict(soft_regime=True, topn=8, take_profit=8.0, strat_kw=dict(no_atr=True))),
    ]
    for label, kw in runs:
        skw = kw.pop("strat_kw", {})
        strat = (lambda o,h,l,c,v, _k=skw: score_v12b(o,h,l,c,v, **_k))
        r = backtest(strat, label=label, **kw)
        print(f"{r['label']:<26}{r['weeks']:>4}{r['cum']:>+9.1f}{r['avg_w']:>+6.2f}{r['win_w']:>5.0f}%{r['beat']:>5.0f}%{r['sharpe']:>6.2f}{r['mdd']:>+7.1f}{r['cash']:>5}{r['stock_wr']:>5.0f}%{str(r['ic']):>7}{str(r['ic_pos']):>5}%")
