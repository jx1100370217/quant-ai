#!/usr/bin/env python3
"""
V12b 下周推荐 — 本地 CLI 入口

设计：直接复用 backend/weekly_advisor/screener.py 的 scan_reversal_candidates，
      保证本地脚本和网页后端输出完全一致。

数据：每次运行实时拉取 eastmoney（近 6 周 / 30 交易日 K 线 + buffer）。
Universe：大中盘（全 A 股按成交额拉取后筛市值≥100亿，近似 HS300+ZZ500）。
打分：V12b 反转因子（score_v7）— 7日涨跌 -25%~-5%、5日低点反弹≥3.5%、
      量比≥1.5、反转分≥40。
Top-N：按反转分排序取前 5；有几只给几只（不足 5 就按实有数量）。

注：2026-05-31 已回滚到 V12b（score_v7：7日∈[-25,-5]、5日低点反弹≥3.5%、量比≥1.5、分≥40）。

用法：
    python predict_next_week.py
    # 或指定 universe 上限
    python predict_next_week.py --limit 5500
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import os
import sys
import warnings

warnings.filterwarnings("ignore")
# 打开 INFO 级日志，方便观察 universe 构造 / 通过过滤数量 / 单股失败
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

# 清理代理环境（CLAUDE.md 记录：aiohttp 需要 trust_env=False 绕过本地代理）
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
         "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)

# 让 Python 能 import backend 包下的 data/ 和 weekly_advisor/
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from weekly_advisor.screener import (  # noqa: E402
    BOUNCE_FLOOR,
    MAX_DECLINE_7D,
    MIN_DECLINE_7D,
    MIN_REVERSAL_SCORE,
    VOL_RATIO_FLOOR,
    scan_reversal_candidates,
)

# V12b Top-5 固定权重 & 止损参数（和 backend/weekly_advisor/advisor.py 保持一致）
WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]
SINGLE_STOP_PCT = -6.0
PORTFOLIO_STOP_PCT = -4.0
MIN_SCORE = MIN_REVERSAL_SCORE


def next_monday(today: datetime.date) -> datetime.date:
    """下一个周一 —— 若今天是周末则返回下周一；若工作日则返回本周一。"""
    weekday = today.weekday()  # Mon=0, Sun=6
    if weekday == 0:   # 今天就是周一
        return today
    if weekday <= 4:   # 工作日
        return today - datetime.timedelta(days=weekday)
    # 周六/周日 → 下周一
    return today + datetime.timedelta(days=(7 - weekday))


def fmt(v, digits=2, signed=False) -> str:
    if v is None:
        return "—"
    s = f"{v:.{digits}f}"
    return f"+{s}" if (signed and v > 0) else s


async def main(limit: int) -> int:
    today = datetime.date.today()
    buy_day = next_monday(today)
    sell_day = buy_day + datetime.timedelta(days=4)

    print("=" * 95)
    print(f"  V12b 下周推荐 — 反转因子策略（大中盘 universe·市值≥100亿）")
    print(f"  建议 {buy_day} (周一) 开盘买入 → {sell_day} (周五) 收盘卖出")
    print("=" * 95)
    print()

    candidates = await scan_reversal_candidates(limit=limit)

    if not candidates:
        print(f"【结果】无候选通过过滤（7日{MIN_DECLINE_7D:.0f}%~{MAX_DECLINE_7D:.0f}% ∧ 反弹≥{BOUNCE_FLOOR:.1f}% ∧ 量比≥{VOL_RATIO_FLOOR:.1f} ∧ 反转分≥{MIN_SCORE}）")
        print("       建议本周空仓观望。")
        return 1

    # 候选已按反转分排序；按权重取 Top 5
    top = candidates[:min(5, len(candidates))]

    print(f"通过过滤 {len(candidates)} 只 · 本次推荐 Top {len(top)} 只")
    print()
    print("=" * 95)
    print(f"【V12b Top {len(top)} 推荐 — 建议 {buy_day} 开盘按权重买入】")
    print("=" * 95)
    print(f"{'排名':<4}{'权重':<7}{'代码':<13}{'名称':<12}{'评分':<7}{'收盘价':<9}"
          f"{'反弹%':<8}{'7日%':<8}{'量比':<7}{'RSI6':<6}")
    print("-" * 95)
    for i, c in enumerate(top, 1):
        w = WEIGHTS[i - 1] * 100
        print(f"{i:<4}{w:>4.0f}%  {c.code:<13}{c.name:<12}"
              f"{c.reversal_score:<7.0f}{c.price:<9.2f}"
              f"{fmt(c.bounce_pct):<8}{fmt(c.decline_7d, signed=True):<8}"
              f"{fmt(c.vol_ratio):<7}{fmt(c.rsi6, digits=1):<6}")
    print()

    print("【交易执行提示】")
    print(f"  • 单股挂单止损价：买入价 × (1 + {SINGLE_STOP_PCT}/100) = × 0.94 (触发即市价出)")
    print(f"  • 组合级监控：每日收盘前计算组合加权涨跌，≤ {PORTFOLIO_STOP_PCT}% 则次日开盘清仓")
    print(f"  • 持仓期：{buy_day} 开盘 → {sell_day} 收盘（若未触发止损）")
    print()

    if len(candidates) > 5:
        backup = candidates[5:20]
        print("【Top 6-20 候补（参考）】")
        print("-" * 95)
        print(f"{'排名':<4}{'代码':<13}{'名称':<12}{'评分':<7}{'收盘价':<9}"
              f"{'反弹%':<8}{'7日%':<8}{'量比':<7}")
        print("-" * 95)
        for i, c in enumerate(backup, 6):
            print(f"{i:<4}{c.code:<13}{c.name:<12}{c.reversal_score:<7.0f}"
                  f"{c.price:<9.2f}{fmt(c.bounce_pct):<8}"
                  f"{fmt(c.decline_7d, signed=True):<8}{fmt(c.vol_ratio):<7}")

    print()
    print("=" * 95)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V12b 下周推荐（实时 eastmoney · 全 A 股扫描）")
    parser.add_argument(
        "--limit", type=int, default=5500,
        help="universe 目标规模（全 A 股 ~5300，默认 5500 留余量）",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.limit)))
