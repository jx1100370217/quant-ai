"""
反转策略筛选器 V7 — 深 V 反弹评分（全 A 股 universe + 软过滤打分）

历史演进：
  · V10：bounce ≥ 2%、universe = 跌幅榜
  · V12b：bounce ≥ 3.5%、universe = 三榜并集（跌幅+成交额+inflow）、
          加入"7 日跌幅 ∈ [-25%,-5%]"和"量比 ≥ 1.2"两道硬过滤
  · V7（current）：保留 bounce ≥ 3.5% 唯一硬过滤，去掉 7 日 / 量比硬过滤，
                  universe 扩到全 A 股（~5300）。和 predict_last_week.py /
                  reproduce_2026_04_17.py 完全一致 —— 由 04-17 复现亨通光电/
                  东方盛虹/衢州发展/世运电路/中钨高新 这一组验证通过。

评分构成（总分 ≤ 100）：
  · 5 日低点反弹      0~20  （>8 → 20，>6 → 17，>4 → 13，>3 → 9，else 5）
  · 2 日动量          0~12  （recent_gain = (close[-1]-close[-3])/close[-3]）
  · 7 日跌幅深度      2~8   （仅加分，不再用作硬过滤）
  · 量比 vs MA5       4~18  （仅加分，不再用作硬过滤）
  · 当日量 > 昨日量   +6
  · 14 日 ATR/价格    0~12
  · RSI6 超卖         0~10  （<30 → +10，<45 → +3）

硬过滤（仅一道策略硬过滤）：
  · 5 日低点反弹 ≥ 3.5%
  · reversal_score ≥ 40 （在 _fetch_and_score 内做最终筛选）

工程性安全垫（不在复现策略内，仅为生产可用）：
  · price <= 0：剔除停牌票（无法成交）
  · 名称含 "ST" 或 "退"：剔除 ST / 退市流程中的票
  说明：cache 复现里这 5 只（亨通光电/东方盛虹/衢州发展/世运电路/中钨高新）
        都不带 ST/退，所以加这道过滤不影响 04-17 复现结果。
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any

import numpy as np

from data.eastmoney import eastmoney_api
from .models import StockCandidate

logger = logging.getLogger(__name__)

# ─── 策略窗口配置 ────────────────────────────────────────
# 打分所需的最少历史交易日；ATR 锚定 14 日窗口，bounce 锚定 5 日，
# RSI6 锚定 7 日，留 20 日做余量。
LOOKBACK_DAYS = 20
# 拉取 K 线时多取 10 根作为缓冲
KLINE_FETCH_LIMIT = LOOKBACK_DAYS + 10
# Bounce 硬过滤阈值（V12b 起统一 3.5%）
BOUNCE_FLOOR = 3.5
# 入选反转候选的最低反转分（候选层最终门槛）
MIN_REVERSAL_SCORE = 40
# Universe 目标规模：全 A 股 ≈ 5300，留余量
DEFAULT_UNIVERSE_LIMIT = 5500


def _calc_rsi(closes, period: int = 6) -> float:
    """6 周期 RSI"""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = float(np.mean(gains)) if gains.size else 0.0
    avg_loss = float(np.mean(losses)) if losses.size else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def score_reversal(
    closes: np.ndarray,
    volumes: np.ndarray,
    stock_info: dict,
    opens: np.ndarray = None,
    highs: np.ndarray = None,
    lows: np.ndarray = None,
    return_details: bool = False,
):
    """
    V7 深 V 反弹打分。和 predict_last_week.py / reproduce_2026_04_17.py 的
    `score_v7` 完全等价，唯一硬过滤是 bounce ≥ 3.5%。

    return_details=True 时返回 (score, details_dict)
    details: bounce_pct / decline_7d / vol_ratio / rsi6
    """
    def _return(score, details):
        return (score, details) if return_details else score

    details = {"bounce_pct": None, "decline_7d": None, "vol_ratio": None, "rsi6": None}

    if len(closes) < LOOKBACK_DAYS:
        return _return(0.0, details)

    # ── 唯一硬过滤：5 日低点反弹 ≥ BOUNCE_FLOOR ────────────────
    if lows is not None and len(lows) >= 5:
        low_5d = float(np.min(lows[-5:]))
    else:
        low_5d = float(np.min(closes[-5:]))
    bounce = (closes[-1] - low_5d) / low_5d * 100 if low_5d > 0 else 0.0
    details["bounce_pct"] = round(float(bounce), 2)
    if bounce < BOUNCE_FLOOR:
        return _return(0.0, details)

    # ── 评分项 1：bounce 强度（0-20）─────────────────────────
    score = 0.0
    if bounce > 8:
        score += 20
    elif bounce > 6:
        score += 17
    elif bounce > 4:
        score += 13
    elif bounce > 3:
        score += 9
    else:
        score += 5

    # ── 评分项 2：2 日动量（0-12）───────────────────────────
    recent_gain = (
        (closes[-1] - closes[-3]) / closes[-3] * 100
        if len(closes) >= 3 and closes[-3] > 0 else 0.0
    )
    if recent_gain > 6:
        score += 12
    elif recent_gain > 2:
        score += 7

    # ── 评分项 3：7 日跌幅深度（仅加分，不硬过滤）（2-8）────
    decline_7d = (
        (closes[-1] - closes[-8]) / closes[-8] * 100
        if len(closes) >= 8 and closes[-8] > 0 else 0.0
    )
    details["decline_7d"] = round(float(decline_7d), 2)
    if decline_7d < -15:
        score += 8
    elif decline_7d < -10:
        score += 6
    elif decline_7d < -8:
        score += 4
    else:
        score += 2

    # ── 评分项 4：量比 vs MA5（仅加分，不硬过滤）（4-18）────
    if len(volumes) >= 6:
        avg_vol_5d = float(np.mean(volumes[-6:-1]))
    elif len(volumes) >= 2:
        avg_vol_5d = float(np.mean(volumes[:-1]))
    else:
        avg_vol_5d = 0.0
    vol_ratio = float(volumes[-1]) / avg_vol_5d if avg_vol_5d > 0 else 1.0
    details["vol_ratio"] = round(vol_ratio, 2)
    if vol_ratio > 3.0:
        score += 18
    elif vol_ratio > 2.0:
        score += 12
    elif vol_ratio > 1.5:
        score += 8
    else:
        score += 4

    # ── 评分项 5：当日量 > 昨日量（+6）──────────────────────
    if len(volumes) >= 2 and volumes[-1] > volumes[-2]:
        score += 6

    # ── 评分项 6：14 日 ATR / 价格（0-12）───────────────────
    if highs is not None and lows is not None and len(highs) >= 14:
        atr = float(np.mean(highs[-14:] - lows[-14:]))
        atr_ratio = atr / closes[-1] * 100 if closes[-1] > 0 else 0.0
        if atr_ratio > 5:
            score += 12
        elif atr_ratio > 3:
            score += 6

    # ── 评分项 7：RSI6 超卖（0-10）──────────────────────────
    rsi6 = _calc_rsi(closes, 6)
    details["rsi6"] = round(float(rsi6), 1)
    if rsi6 < 30:
        score += 10
    elif rsi6 < 45:
        score += 3

    final_score = round(min(100.0, max(0.0, score)), 2)
    return _return(final_score, details)


# ─────────────────────────────────────────────────────────────
# 反转候选扫描 — 全 A 股 universe + V7 打分
# ─────────────────────────────────────────────────────────────

async def scan_reversal_candidates(limit: int = DEFAULT_UNIVERSE_LIMIT) -> List[StockCandidate]:
    """
    扫描全 A 股反转候选（V7 · 全市场扫描）：

    1. Universe：通过 eastmoney `clist` 接口按成交额降序拉取全市场（~5300 只），
       用 amount 排序仅是为了把停牌/废弃股排到最后；本质等价"全 A 股"。
    2. 每只取近 KLINE_FETCH_LIMIT (=30) 根日线
    3. score_reversal 打分（仅 bounce ≥ 3.5% 一道硬过滤）
    4. 反转分 ≥ 40 入选；按反转分降序返回
    """
    logger.info(f"反转策略扫描：全 A 股 universe target ≈ {limit}")

    try:
        # 全 A 股 universe —— 一次性拉取，按成交额降序（保证流动性头部覆盖完整）
        stocks = await eastmoney_api.get_top_stocks_market_wide(
            limit=limit, sort_by="amount"
        )
        if not stocks:
            logger.warning("universe 为空（eastmoney 拉取失败），返回空候选")
            return []

        # 去重（防御性 —— 单源拉取理论上不会重复，但分页拼接可能有边界重复）
        stocks_by_code: Dict[str, Dict] = {}
        for s in stocks:
            code = s.get("code")
            if code and code not in stocks_by_code:
                stocks_by_code[code] = s
        stocks = list(stocks_by_code.values())

        logger.info(f"universe 实际规模 {len(stocks)} 只（全 A 股 by amount 降序）")

        # 并发拉 K 线 + 打分（限流 24，配合 eastmoney._REQUEST_SEMAPHORE=24）
        # 历史值 8 在 5500 只全 A 股 universe 下需 5+ 分钟，超过前端 3min 超时；
        # 提升到 24 后实测整轮缩短到 ~90s。
        semaphore = asyncio.Semaphore(24)
        kline_failed = 0
        scored_count = 0

        async def _fetch_and_score(stock: Dict) -> Optional[StockCandidate]:
            nonlocal kline_failed, scored_count
            async with semaphore:
                code = stock.get("code", "")
                name = stock.get("name", "")
                price = stock.get("price", 0.0) or 0.0
                if not code:
                    return None
                # ── 工程性安全垫：剔除 ST / 退市 / 停牌（价格 = 0）─────────
                # 复现策略本身不带这道过滤；加上是为了避免全 A 股 universe
                # 把"僵尸票"按极端反弹形态排到 Top（实际无法成交）。
                if price <= 0:
                    return None
                if name and ("ST" in name or "退" in name):
                    return None
                try:
                    klines = await eastmoney_api.get_kline_data(
                        code, klt="101", limit=KLINE_FETCH_LIMIT
                    )
                    if not klines or len(klines) < LOOKBACK_DAYS:
                        kline_failed += 1
                        return None

                    closes  = np.array([k["close"]  for k in klines], dtype=float)
                    volumes = np.array([k["volume"] for k in klines], dtype=float)
                    opens   = np.array([k["open"]   for k in klines], dtype=float)
                    highs   = np.array([k["high"]   for k in klines], dtype=float)
                    lows    = np.array([k["low"]    for k in klines], dtype=float)

                    close_now = closes[-1]
                    close_5d_ago = closes[-6] if len(closes) >= 6 else closes[0]
                    if close_5d_ago <= 0:
                        return None
                    decline_5d = (close_now - close_5d_ago) / close_5d_ago * 100

                    stock_info = {"decline_5d": decline_5d}
                    reversal_score, details = score_reversal(
                        closes, volumes, stock_info,
                        opens=opens, highs=highs, lows=lows,
                        return_details=True,
                    )
                    if reversal_score < MIN_REVERSAL_SCORE:
                        return None
                    scored_count += 1

                    pe_ttm        = stock.get("pe_ttm")
                    pb            = stock.get("pb")
                    market_cap_b  = stock.get("market_cap_b")
                    net_inflow    = stock.get("net_inflow", 0.0) or 0.0

                    return StockCandidate(
                        code=code, name=name, price=price,
                        change_pct_5d=decline_5d,
                        decline_5d=abs(decline_5d),
                        net_inflow=net_inflow,
                        pe_ttm=pe_ttm, pb=pb, market_cap_b=market_cap_b,
                        quant_score=0.0,
                        reversal_score=reversal_score,
                        composite_score=reversal_score,
                        bounce_pct=details.get("bounce_pct"),
                        decline_7d=details.get("decline_7d"),
                        vol_ratio=details.get("vol_ratio"),
                        rsi6=details.get("rsi6"),
                        source="reversal",
                        sector_name=stock.get("sector_name", ""),
                    )
                except Exception as e:
                    logger.warning(f"处理股票 {code} {name} 失败: {type(e).__name__}: {e}")
                    return None

        results = await asyncio.gather(
            *[_fetch_and_score(s) for s in stocks],
            return_exceptions=False,
        )

        candidates = sorted(
            [c for c in results if c is not None],
            key=lambda x: x.reversal_score, reverse=True,
        )

        logger.info(
            f"反转策略筛选完成：通过过滤 {len(candidates)} 只 "
            f"(K线不足跳过 {kline_failed} 只 / 通过打分 {scored_count} 只)"
        )
        for i, c in enumerate(candidates[:10], 1):
            logger.info(
                f"  {i}. {c.code} {c.name}: 分={c.reversal_score:.0f} "
                f"反弹={c.bounce_pct} 7日={c.decline_7d:+.2f}% "
                f"量比={c.vol_ratio} rsi6={c.rsi6}"
            )

        return candidates

    except Exception as e:
        logger.error(f"反转候选扫描失败: {e}")
        return []
