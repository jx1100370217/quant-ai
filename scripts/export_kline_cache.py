#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 cache/kline_5y.pkl（pandas DataFrame，跨 pandas 版本 pickle 不兼容）导出成
纯 Python 原生类型的 pkl（只含 str/float/list），任何 pandas 版本都能读，
供沙箱里跑多年回测用。

在能正常读 pkl 的机器（写它的那台）上运行：
    cd ~/codes/quant-ai && ./backend/venv/bin/python scripts/export_kline_cache.py
"""
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "cache" / "kline_5y.pkl"
DST = REPO / "cache" / "kline_5y_portable.pkl"


def colpick(df, *names):
    for n in names:
        if n in df.columns:
            return n
    raise KeyError(f"列缺失，候选 {names}，实际 {list(df.columns)}")


def main() -> int:
    d = pickle.load(open(SRC, "rb"))   # 写它的机器上原生 pandas 能读
    # 结构是 {'all_kline': {code: DataFrame}, 'stock_names': {code: name}}
    if isinstance(d, dict) and "all_kline" in d:
        names = d.get("stock_names", {}) or {}
        kline = d["all_kline"]
    else:
        names, kline = {}, d
    print(f"源 pkl: 顶层键 {list(d.keys())[:5] if isinstance(d, dict) else type(d)} | all_kline {len(kline)} 个代码")
    # 打印第一只的列名，便于核对
    try:
        _c0 = next(iter(kline)); print(f"首只 {_c0} 列名: {list(kline[_c0].columns)} 行数 {len(kline[_c0])}")
    except Exception as e:
        print("列名探测失败:", e)
    out = {}
    bad = 0
    for code, df in kline.items():
        try:
            df = df.sort_values(colpick(df, "date", "Date"))
            dc = colpick(df, "date", "Date")
            oc = colpick(df, "open", "Open")
            hc = colpick(df, "high", "High")
            lc = colpick(df, "low", "Low")
            cc = colpick(df, "close", "Close")
            vc = colpick(df, "volume", "Volume", "vol")
            out[str(code)] = {
                "name": str(names.get(code, "")),
                "date": [str(x)[:10] for x in df[dc].tolist()],
                "open": [float(x) for x in df[oc].tolist()],
                "high": [float(x) for x in df[hc].tolist()],
                "low": [float(x) for x in df[lc].tolist()],
                "close": [float(x) for x in df[cc].tolist()],
                "volume": [float(x) for x in df[vc].tolist()],
            }
        except Exception as e:
            bad += 1
            if bad <= 5:
                print(f"  跳过 {code}: {type(e).__name__} {e}")
    pickle.dump(out, open(DST, "wb"), protocol=4)
    all_dates = sorted({x for v in out.values() for x in v["date"]})
    print(f"已导出 {len(out)} 个代码 → {DST}")
    print(f"日期范围 {all_dates[0]} → {all_dates[-1]}（{len(all_dates)} 个交易日）")
    print(f"样例代码 {list(out.keys())[:10]}")
    print(f"文件大小 {DST.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
