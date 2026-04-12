"""
反转策略筛选器 - 纯反转策略，扫描所有A股找出近5日跌幅3-8%的标的并进行反转评分
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any

import numpy as np

from data.eastmoney import eastmoney_api
from utils.indicators import TechnicalIndicators
from .models import StockCandidate

logger = logging.getLogger(__name__)

ti = TechnicalIndicators()


# ─────────────────────────────────────────────────────────────
# 技术指标计算（基于K线数据）
# ─────────────────────────────────────────────────────────────

def _calc_rsi_score(closes: np.ndarray) -> float:
    """RSI 超卖区加分（反转策略）"""
    if len(closes) < 15:
        return 0.0
    rsi_arr = ti.rsi(closes, period=14)
    if len(rsi_arr) == 0:
        return 0.0
    rsi = float(rsi_arr[-1])
    # 反转策略：RSI越低越容易反弹
    if rsi < 20:
        return 25.0  # 极度超卖，强反转信号
    elif 20 <= rsi <= 30:
        return 20.0  # 超卖区
    elif 30 < rsi <= 40:
        return 10.0  # 低位但非超卖
    else:
        return 0.0


def _calc_bollinger_position(closes: np.ndarray) -> float:
    """布林带位置：价格低于中轨加分（反转策略）"""
    if len(closes) < 25:
        return 0.0
    upper, middle, lower = ti.bollinger_bands(closes, period=20)
    if len(upper) == 0 or len(lower) == 0:
        return 0.0
    price = float(closes[-1])
    u, m, l = float(upper[-1]), float(middle[-1]), float(lower[-1])

    if price < l:
        return 15.0  # 价格低于下轨，强反转
    elif price < m:
        return 10.0  # 价格在中轨以下
    else:
        return 0.0


def _calc_support_proximity(closes: np.ndarray) -> float:
    """价格接近10日低点（反转策略）"""
    if len(closes) < 10:
        return 0.0
    low_10d = float(np.min(closes[-10:]))
    price = float(closes[-1])
    if low_10d == 0:
        return 0.0

    distance_pct = abs(price - low_10d) / low_10d * 100

    if distance_pct <= 2.0:
        return 15.0  # 接近10日低点
    elif distance_pct <= 5.0:
        return 8.0
    else:
        return 0.0


def _calc_volume_shrinkage(volumes: np.ndarray) -> float:
    """成交量萎缩评分：抛售力度衰竭（反转策略）"""
    if len(volumes) < 20:
        return 0.0

    vol_5d_avg = float(np.mean(volumes[-5:]))
    vol_20d_avg = float(np.mean(volumes[-20:]))

    if vol_20d_avg <= 0:
        return 0.0

    ratio = vol_5d_avg / vol_20d_avg

    # 0.4-0.7：前期高抛售，现已衰竭（反转信号强）
    if 0.4 <= ratio <= 0.7:
        return 20.0
    # 0.7-0.9：抛售略弱
    elif 0.7 < ratio <= 0.9:
        return 12.0
    else:
        return 5.0


def score_reversal(
    closes: np.ndarray,
    volumes: np.ndarray,
    stock_info: Dict[str, Any],
) -> float:
    """
    反转得分 (0-100)

    组成：
    - 跌幅幅度 (0-25): -3%~-5% → 20pts, -5%~-8% → 25pts
    - RSI超卖 (0-25): RSI<20 → 25pts, 20-30 → 20pts, 30-40 → 10pts
    - 成交量萎缩 (0-20): ratio 0.4-0.7 → 20pts, 0.7-0.9 → 12pts
    - 布林带位置 (0-15): 低于下轨 → 15pts, 低于中轨 → 10pts
    - 支撑接近度 (0-15): 2%内10日低 → 15pts, 5%内 → 8pts
    """
    score = 0.0

    # 1. 跌幅幅度评分 (0-25)
    decline_5d = stock_info.get("decline_5d", 0.0)
    if -5.0 <= decline_5d < -3.0:
        score += 20.0
    elif -8.0 <= decline_5d < -5.0:
        score += 25.0
    elif decline_5d < -8.0 or decline_5d > -3.0:
        score += 0.0  # 不在目标范围内

    # 2. RSI超卖 (0-25)
    rsi_score = _calc_rsi_score(closes)
    score += rsi_score

    # 3. 成交量萎缩 (0-20)
    vol_score = _calc_volume_shrinkage(volumes)
    score += vol_score

    # 4. 布林带位置 (0-15)
    boll_score = _calc_bollinger_position(closes)
    score += boll_score

    # 5. 支撑接近度 (0-15)
    support_score = _calc_support_proximity(closes)
    score += support_score

    return round(min(100.0, max(0.0, score)), 2)


# ─────────────────────────────────────────────────────────────
# 反转候选扫描
# ─────────────────────────────────────────────────────────────

async def scan_reversal_candidates(limit: int = 500) -> List[StockCandidate]:
    """
    扫描反转候选：
    1. 获取交易量前 500+ 的全A股
    2. 获取20日K线，计算5日跌幅
    3. 筛选 -3% ~ -8% 的股票
    4. 对每只进行反转评分
    5. 返回按反转分排序的候选
    """
    logger.info(f"反转策略扫描：获取交易量前 {limit} 只股票")

    try:
        # 获取交易量前 500+ 的股票
        stocks = await eastmoney_api.get_top_stocks_market_wide(limit=limit, sort_by="inflow")
        if not stocks:
            logger.warning("获取股票列表失败")
            return []

        logger.info(f"获取股票总数：{len(stocks)}")

        # 并发获取K线数据，并筛选符合条件的股票
        semaphore = asyncio.Semaphore(8)

        async def _fetch_and_score(stock: Dict) -> Optional[StockCandidate]:
            """获取K线、计算5日跌幅、评分"""
            async with semaphore:
                code = stock.get("code", "")
                name = stock.get("name", "")
                price = stock.get("price", 0.0) or 0.0

                if not code:
                    return None

                try:
                    # 获取20日K线
                    klines = await eastmoney_api.get_kline_data(code, klt="101", limit=20)
                    if not klines or len(klines) < 6:
                        return None

                    closes = np.array([k["close"] for k in klines], dtype=float)
                    volumes = np.array([k["volume"] for k in klines], dtype=float)

                    # 计算5日跌幅 (close[-1] - close[-6]) / close[-6] * 100
                    close_now = closes[-1]
                    close_5d_ago = closes[-6]

                    if close_5d_ago <= 0:
                        return None

                    decline_5d = (close_now - close_5d_ago) / close_5d_ago * 100

                    # 筛选条件：5日跌幅在 -3% ~ -8% 范围内
                    if not (-8.0 <= decline_5d <= -3.0):
                        return None

                    # 反转评分
                    stock_info = {
                        "decline_5d": decline_5d,
                    }
                    reversal_score = score_reversal(closes, volumes, stock_info)

                    # 获取基本信息
                    pe_ttm = stock.get("pe_ttm")
                    pb = stock.get("pb")
                    market_cap_b = stock.get("market_cap_b")
                    net_inflow = stock.get("net_inflow", 0.0) or 0.0

                    candidate = StockCandidate(
                        code=code,
                        name=name,
                        price=price,
                        change_pct_5d=decline_5d,  # 实际是跌幅（负数）
                        decline_5d=abs(decline_5d),  # 存储正的跌幅%
                        net_inflow=net_inflow,
                        pe_ttm=pe_ttm,
                        pb=pb,
                        market_cap_b=market_cap_b,
                        quant_score=0.0,  # 不使用量化分
                        reversal_score=reversal_score,
                        composite_score=reversal_score,  # 反转分就是综合分
                        source="reversal",
                        sector_name=stock.get("sector_name", ""),
                    )
                    return candidate

                except Exception as e:
                    logger.debug(f"处理股票 {code} 失败: {e}")
                    return None

        # 并发处理所有股票
        results = await asyncio.gather(
            *[_fetch_and_score(s) for s in stocks],
            return_exceptions=False
        )

        # 过滤None，按反转分排序
        candidates = [c for c in results if c is not None]
        candidates.sort(key=lambda x: x.reversal_score, reverse=True)

        logger.info(f"反转策略筛选完成：符合条件的股票 {len(candidates)} 只")
        for i, c in enumerate(candidates[:10], 1):
            logger.info(f"  {i}. {c.code} {c.name}: 反转分={c.reversal_score:.1f}, "
                       f"跌幅={c.decline_5d:.2f}%")

        return candidates

    except Exception as e:
        logger.error(f"反转候选扫描失败: {e}")
        return []
