#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多年周度回测引擎 v4（本地5年数据·无网络）。
生产口径: 去ATR、量比>=1.5、现金仓位、T+1、交易摩擦与涨跌停可成交性近似。
注意: universe=当前HS300+ZZ500成分, 含明显幸存者偏差, 绝对收益被高估,
      看相对(vs同口径基准)和风险指标更可靠。"""
import argparse
import pickle, datetime as dt
import numpy as np

try:  # 兼容 `python scripts/backtest_engine.py` 与 `import scripts.backtest_engine`
    from .execution_model import (
        DEFAULT_EXECUTION,
        ExecutionConfig,
        is_intraday_sellable,
        is_open_buyable,
        is_open_sellable,
        net_trade_return_pct,
    )
except ImportError:
    from execution_model import (
        DEFAULT_EXECUTION,
        ExecutionConfig,
        is_intraday_sellable,
        is_open_buyable,
        is_open_sellable,
        net_trade_return_pct,
    )

import pathlib as _pl
PKL = str(_pl.Path(__file__).resolve().parents[1] / "cache" / "kline_5y_portable.pkl")
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]
SINGLE_STOP, PORT_STOP = -6.0, -4.0
WIN = 80   # 只把最近 80 日喂给打分(提速; MA60/RSI/bounce 都够用)

with open(PKL, "rb") as _cache_file:
    D = pickle.load(_cache_file)
CODES = list(D.keys())
ref = max(CODES, key=lambda c: len(D[c]["date"]))
DATES = D[ref]["date"]
DIDX = {d: i for i, d in enumerate(DATES)}
WD = [dt.date.fromisoformat(d).weekday() for d in DATES]
A = {}
for c in CODES:
    v = D[c]
    A[c] = {"name": v.get("name", ""),
            "o": np.array(v["open"], float), "h": np.array(v["high"], float),
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


def score_v12b(o, h, l, c, v, dec7_floor=-25.0, rsi_excl=None,
               need_ma60=False, no_atr=False, vol_ratio_floor=1.2):
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
    if va5 > 0 and vr < vol_ratio_floor: return None
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


def score_production(o, h, l, c, v):
    """当前生产筛选口径的回测入口，防止研究脚本继续使用旧阈值。"""
    return score_v12b(o, h, l, c, v, no_atr=True, vol_ratio_floor=1.5)


def backtest(
    strat,
    regime_gate=False,
    soft_regime=False,
    take_profit=None,
    topn=5,
    label="",
    start_date=None,
    end_date=None,
    execution_config=DEFAULT_EXECUTION,
):
    rets, ic_list = [], []
    bench_rets = []
    eq = peak = 1.0; mdd = 0.0; stock_w = stock_n = 0; cash = 0
    unfilled_entries = delayed_exits = unresolved_exits = 0
    cost_drag = 0.0
    for w in range(len(WEEK_ENDS) - 1):
        si = WEEK_ENDS[w]
        if si + 1 >= len(DATES): continue
        bd, sd = DATES[si + 1], DATES[WEEK_ENDS[w + 1]]
        if start_date and bd < start_date: continue
        if end_date and bd > end_date: continue
        bench = BENCH_W[w]
        bench_rets.append(bench)
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
        # 不足5只时未使用的排名槽位保持现金，不再把少数股票归一化到满仓。
        wr = WEIGHTS[:len(picks)]
        if sum(wr) > 1.0:
            wr = [weight / sum(wr) for weight in wr]
        pr = _port(
            picks, bd, sd, wr,
            take_profit=take_profit,
            execution_config=execution_config,
        )
        week_ret = pr["ret"] * scale
        rets.append(week_ret)
        for x, executed in zip(pr["picks"], pr["executed"]):
            if not executed:
                continue
            stock_n += 1; stock_w += 1 if x > 0 else 0
        if pr["executed_count"] == 0:
            cash += 1
        unfilled_entries += pr["unfilled_entries"]
        delayed_exits += pr["delayed_exits"]
        unresolved_exits += pr["unresolved_exits"]
        cost_drag += pr["cost_drag_pct"] * scale
        eq *= (1 + week_ret/100); peak = max(peak, eq); mdd = min(mdd, (eq-peak)/peak*100)
    rets = np.array(rets); bw = np.array(bench_rets)
    return {"label": label, "weeks": len(rets), "cum": round((eq-1)*100, 1),
            "avg_w": round(rets.mean(), 3) if len(rets) else 0.0,
            "win_w": round((rets > 0).mean()*100, 1) if len(rets) else 0.0,
            "beat": round((rets > bw).mean()*100, 1) if len(rets) else 0.0,
            "sharpe": round(rets.mean()/rets.std()*np.sqrt(50), 2) if len(rets) and rets.std() > 0 else 0,
            "mdd": round(mdd, 1), "cash": cash, "stock_wr": round(stock_w/max(1, stock_n)*100, 1),
            "ic": round(np.mean(ic_list), 3) if ic_list else None,
            "ic_pos": round(float((np.array(ic_list) > 0).mean()*100), 0) if ic_list else None,
            "trades": stock_n, "unfilled_entries": unfilled_entries,
            "delayed_exits": delayed_exits, "unresolved_exits": unresolved_exits,
            "cost_drag": round(cost_drag, 2)}


def _port(picks, bd, sd, wr, take_profit=None, execution_config=DEFAULT_EXECUTION):
    """按可执行价格计算组合收益。

    - 开盘涨停或停牌时不假设可以买入；
    - 周一买入遵守 T+1：买入日触发止损/止盈，下一可成交日退出；
    - 此后跳空穿越阈值按开盘成交，盘中触及才按阈值成交；
    - 跌停或停牌无法卖出时向后延迟，最多检查 ``max_exit_delay_days`` 个交易日；
    - 组合收盘触发 -4% 后，剩余仓位按下一可成交日开盘退出，允许跨周；
    - 所有已执行交易计入双边滑点、佣金和卖出印花税；
    - ``wr`` 是占总资金比例，剩余部分视为现金。
    """
    buy_idx, sell_idx = DIDX[bd], DIDX[sd]
    extension_end = min(len(DATES) - 1, sell_idx + execution_config.max_exit_delay_days)
    seq = DATES[buy_idx:extension_end + 1]
    buy_date_obj = dt.date.fromisoformat(bd)

    bps = []
    for c, _ in picks:
        P = A[c]["pos"]
        j = P.get(bd, -1)
        if j <= 0:
            bps.append(None)
            continue
        bar_date = dt.date.fromisoformat(bd)
        buyable = is_open_buyable(
            A[c]["o"][j], A[c]["h"][j], A[c]["l"][j], A[c]["v"][j],
            A[c]["c"][j - 1], c, A[c]["name"], bar_date, execution_config,
        )
        bps.append(A[c]["o"][j] if buyable else None)

    exits = [None] * len(picks)
    exit_dates = [None] * len(picks)
    pending_single_exit = [False] * len(picks)
    portfolio_pending_exit = False
    portfolio_stopped = False
    regular_exit_pending = False
    delayed_exit_indices = set()

    def _bar(c, d):
        j = A[c]["pos"].get(d, -1)
        if j <= 0:
            return None
        return j, A[c]["o"][j], A[c]["h"][j], A[c]["l"][j], A[c]["c"][j], A[c]["v"][j], A[c]["c"][j - 1]

    def _try_open_exit(i, c, d):
        bar = _bar(c, d)
        if bar is None:
            delayed_exit_indices.add(i)
            return False
        j, op, hi, lo, cl, vol, prev_close = bar
        trade_date = dt.date.fromisoformat(d)
        if not is_open_sellable(op, hi, lo, vol, prev_close, c, A[c]["name"], trade_date, execution_config):
            delayed_exit_indices.add(i)
            return False
        exits[i] = op
        exit_dates[i] = trade_date
        return True

    for day_idx, d in enumerate(seq):
        after_week = DIDX[d] > sell_idx
        # 前一收盘产生的信号在下一可成交日开盘执行；跌停/停牌则继续等待。
        for i, (c, _) in enumerate(picks):
            if exits[i] is not None or bps[i] is None:
                continue
            if portfolio_pending_exit or pending_single_exit[i] or regular_exit_pending:
                _try_open_exit(i, c, d)
        if portfolio_pending_exit:
            portfolio_stopped = True
            continue
        if after_week:
            continue

        for i, (c, _) in enumerate(picks):
            P = A[c]["pos"]; bo = bps[i]
            if bo is None or exits[i] is not None or pending_single_exit[i] or d not in P:
                continue
            j = P[d]
            op, lo, hi, vol = A[c]["o"][j], A[c]["l"][j], A[c]["h"][j], A[c]["v"][j]
            prev_close = A[c]["c"][j - 1] if j > 0 else 0.0
            trade_date = dt.date.fromisoformat(d)
            stop_price = bo * (1 + SINGLE_STOP / 100)
            target_price = bo * (1 + take_profit / 100) if take_profit is not None else None

            stop_hit = lo <= stop_price
            target_hit = target_price is not None and hi >= target_price
            if day_idx == 0 and (stop_hit or target_hit):
                pending_single_exit[i] = True
            elif day_idx > 0:
                sellable = is_intraday_sellable(
                    op, hi, lo, vol, prev_close, c, A[c]["name"], trade_date, execution_config,
                )
                if stop_hit and sellable:  # 同日同时触发时止损优先，保持保守假设
                    exits[i] = op if op <= stop_price else stop_price
                    exit_dates[i] = trade_date
                elif stop_hit:
                    pending_single_exit[i] = True
                    delayed_exit_indices.add(i)
                elif target_hit and sellable:
                    exits[i] = op if op >= target_price else target_price
                    exit_dates[i] = trade_date

        acc = 0.0
        for i, (c, _) in enumerate(picks):
            bo = bps[i]
            if bo is None:
                continue
            if exits[i] is not None:
                mark = exits[i]
            elif d in A[c]["pos"]:
                mark = A[c]["c"][A[c]["pos"][d]]
            else:
                mark = bo
            acc += wr[i] * ((mark - bo) / bo * 100)
        if acc <= PORT_STOP:
            portfolio_pending_exit = True

        # 正常周末平仓；一字跌停/停牌则从下一交易日继续尝试。
        if d == sd and not portfolio_pending_exit:
            for i, (c, _) in enumerate(picks):
                if bps[i] is None or exits[i] is not None or pending_single_exit[i]:
                    continue
                bar = _bar(c, d)
                if bar is None:
                    regular_exit_pending = True
                    delayed_exit_indices.add(i)
                    continue
                j, op, hi, lo, cl, vol, prev_close = bar
                trade_date = dt.date.fromisoformat(d)
                if is_intraday_sellable(op, hi, lo, vol, prev_close, c, A[c]["name"], trade_date, execution_config):
                    exits[i] = cl
                    exit_dates[i] = trade_date
                else:
                    regular_exit_pending = True
                    delayed_exit_indices.add(i)

    pp = []
    executed = []
    gross_ret = 0.0
    unresolved = 0
    for i, (c, _) in enumerate(picks):
        P = A[c]["pos"]; bo = bps[i]
        if bo is None:
            pp.append(0.0)
            executed.append(False)
        else:
            exit_price = exits[i]
            exit_date = exit_dates[i]
            if exit_price is None:
                # 延迟窗口后仍无法成交：以最后可见收盘做保守盯市，并显式计为未解决退出。
                last_d = next((day for day in reversed(seq) if day in P), sd)
                exit_price = A[c]["c"][P[last_d]] if last_d in P else bo
                exit_date = dt.date.fromisoformat(last_d)
                unresolved += 1
            net_ret = net_trade_return_pct(bo, exit_price, buy_date_obj, exit_date, execution_config)
            pp.append(net_ret)
            executed.append(True)
            gross_ret += wr[i] * ((exit_price - bo) / bo * 100)
    ret = sum(wr[i] * pp[i] for i in range(len(picks)))
    return {
        "ret": round(ret, 3), "picks": pp, "executed": executed,
        "executed_count": sum(executed),
        "unfilled_entries": len(picks) - sum(executed),
        "delayed_exits": len(delayed_exit_indices),
        "unresolved_exits": unresolved,
        "cost_drag_pct": round(gross_ret - ret, 4),
        "portfolio_stopped": portfolio_stopped,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="冻结生产策略的分段回测与执行成本诊断")
    parser.add_argument(
        "--research-grid", action="store_true",
        help="额外输出历史参数敏感性网格；不得把该网格当作未触碰样本外结果",
    )
    args = parser.parse_args()
    bench_cum = round((np.cumprod(1 + np.array(BENCH_W)/100)[-1]-1)*100, 1)
    print(f"universe {len(CODES)} | 交易日 {len(DATES)} ({DATES[0]}~{DATES[-1]}) | 周 {len(WEEK_ENDS)} | 基准等权累计 {bench_cum:+.1f}%")
    print("（注意: 成分股幸存者偏差仍未消除，结果只能做相对敏感性分析）\n")
    print(
        "冻结执行假设: 双边佣金3bp、双边滑点10bp、卖出印花税10bp(2023-08-28前)/5bp(之后)，"
        "开盘涨停不买、开盘跌停/停牌延迟退出。\n"
    )
    hdr = f"{'评估区间':<29}{'周':>4}{'累计%':>9}{'均周':>6}{'周胜':>6}{'跑赢':>6}{'夏普':>6}{'回撤':>7}{'空仓':>5}{'交易':>6}{'成本拖累':>9}"
    print(hdr); print("-"*len(hdr))
    zero_cost = ExecutionConfig(
        commission_bps=0.0, slippage_bps=0.0,
        stamp_duty_bps_before_20230828=0.0,
        stamp_duty_bps_after_20230828=0.0,
    )
    runs = [
        ("全样本·冻结生产口径", dict(strat_fn=score_production)),
        ("开发期·已参与研究", dict(strat_fn=score_production, end_date="2023-12-31")),
        ("复用验证期·非纯OOS", dict(strat_fn=score_production, start_date="2024-01-01")),
        ("全样本·零成本诊断", dict(strat_fn=score_production, execution_config=zero_cost)),
    ]
    if args.research_grid:
        runs.extend([
            ("[研究] Legacy量比1.2+ATR", dict()),
            ("[研究] no_atr+量比1.2", dict(strat_kw=dict(no_atr=True))),
            ("[研究] no_atr+止盈5%", dict(take_profit=5.0, strat_kw=dict(no_atr=True))),
            ("[研究] no_atr+止盈8%", dict(take_profit=8.0, strat_kw=dict(no_atr=True))),
            ("[研究] no_atr+软择时", dict(soft_regime=True, strat_kw=dict(no_atr=True))),
        ])
    for label, kw in runs:
        skw = kw.pop("strat_kw", {})
        strat = kw.pop("strat_fn", None)
        if strat is None:
            strat = (lambda o,h,l,c,v, _k=skw: score_v12b(o,h,l,c,v, **_k))
        r = backtest(strat, label=label, **kw)
        print(f"{r['label']:<29}{r['weeks']:>4}{r['cum']:>+9.1f}{r['avg_w']:>+6.2f}{r['win_w']:>5.0f}%{r['beat']:>5.0f}%{r['sharpe']:>6.2f}{r['mdd']:>+7.1f}{r['cash']:>5}{r['trades']:>6}{r['cost_drag']:>+9.2f}")
        if r["unfilled_entries"] or r["delayed_exits"] or r["unresolved_exits"]:
            print(
                f"  执行诊断: 未成交买入={r['unfilled_entries']}，"
                f"延迟退出={r['delayed_exits']}，窗口后仍未解决={r['unresolved_exits']}"
            )
