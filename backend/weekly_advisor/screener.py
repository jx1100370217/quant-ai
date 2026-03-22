"""
量化预筛器 - 多因子打分，快速从候选池中筛出高质量标的
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
# Phase 1: 宽选 - 建立候选池
# ─────────────────────────────────────────────────────────────

async def fetch_inflow_top50() -> List[Dict]:
    """全A股净流入 Top50"""
    try:
        stocks = await eastmoney_api.get_top_stocks_market_wide(limit=50, sort_by="inflow")
        for s in stocks:
            s["_source"] = "inflow"
        logger.info(f"净流入 Top50 获取 {len(stocks)} 只")
        return stocks
    except Exception as e:
        logger.warning(f"净流入 Top50 获取失败: {e}")
        return []


async def fetch_momentum_stocks() -> List[Dict]:
    """近5日涨幅 5-15% 的动量股（不追涨停板）"""
    try:
        # 取全A股近期涨幅前100（不含ST，涨幅由高到低）
        stocks = await eastmoney_api.get_top_stocks_market_wide(limit=100, sort_by="change")
        result = []
        for s in stocks:
            chg = s.get("change_pct", 0) or 0
            # 5-15%区间：有动量但未涨停（涨停约>9.5%或20%，这里取<15%上限）
            if 5.0 <= chg <= 15.0:
                s["_source"] = "momentum"
                result.append(s)
        logger.info(f"动量股(5-15%涨幅) 筛选 {len(result)} 只")
        return result
    except Exception as e:
        logger.warning(f"动量股获取失败: {e}")
        return []


async def fetch_dragon_tiger_stocks() -> List[Dict]:
    """龙虎榜近期频繁出现的个股（最近3个交易日）"""
    from datetime import datetime, timedelta
    result_map: Dict[str, Dict] = {}
    try:
        # 获取最近3天的龙虎榜（包含非交易日会返回空，正常）
        today = datetime.now()
        for delta in range(7):  # 向前找7天，找出3个有数据的交易日
            date_str = (today - timedelta(days=delta)).strftime("%Y-%m-%d")
            items = await eastmoney_api.get_dragon_tiger(date_str)
            if not items:
                continue
            for item in items:
                code = item.get("code")
                if not code:
                    continue
                if code in result_map:
                    # 频繁出现加权
                    result_map[code]["_dragon_count"] = result_map[code].get("_dragon_count", 1) + 1
                else:
                    result_map[code] = {
                        "code": code,
                        "name": item.get("name", ""),
                        "price": 0,  # 龙虎榜只有涨幅，价格需后续补充
                        "change_pct": item.get("change_rate", 0) or 0,
                        "net_inflow": item.get("net_amount", 0) or 0,
                        "_source": "dragon_tiger",
                        "_dragon_count": 1,
                    }
            # 已找到足够数据就停止（避免过多请求）
            if len(result_map) >= 30:
                break

        # 只取频繁出现（2次及以上）或净买入较大的
        filtered = [
            s for s in result_map.values()
            if s.get("_dragon_count", 1) >= 2 or s.get("net_inflow", 0) > 1e7
        ]
        logger.info(f"龙虎榜候选 {len(filtered)} 只（原始 {len(result_map)} 只）")
        return filtered
    except Exception as e:
        logger.warning(f"龙虎榜获取失败: {e}")
        return []


async def fetch_sector_leaders() -> List[Dict]:
    """热门板块 Top3 的领涨股"""
    result = []
    try:
        sectors = await eastmoney_api.get_sector_ranking()
        if not sectors:
            return []
        # 取净流入前3板块
        top3_sectors = sectors[:3]
        for sector in top3_sectors:
            sector_code = sector.get("code", "")
            sector_name = sector.get("name", "")
            if not sector_code:
                continue
            stocks = await eastmoney_api.get_sector_stocks(sector_code, limit=5)
            if stocks:
                # 取板块内涨幅最大的前2只
                stocks_sorted = sorted(stocks, key=lambda x: x.get("change_pct", 0), reverse=True)
                for s in stocks_sorted[:2]:
                    s["_source"] = "sector_leader"
                    s["_sector_name"] = sector_name
                    result.append(s)
        logger.info(f"板块领涨股获取 {len(result)} 只（Top3板块各2只）")
        return result
    except Exception as e:
        logger.warning(f"板块领涨股获取失败: {e}")
        return []


async def build_candidate_pool() -> List[Dict]:
    """
    Phase 1: 并行宽选，合并去重，返回候选池
    来源：净流入Top50 + 动量股 + 龙虎榜 + 板块领涨
    """
    inflow_stocks, momentum_stocks, dragon_stocks, sector_stocks = await asyncio.gather(
        fetch_inflow_top50(),
        fetch_momentum_stocks(),
        fetch_dragon_tiger_stocks(),
        fetch_sector_leaders(),
        return_exceptions=True,
    )
    # 处理异常返回
    inflow_stocks = inflow_stocks if isinstance(inflow_stocks, list) else []
    momentum_stocks = momentum_stocks if isinstance(momentum_stocks, list) else []
    dragon_stocks = dragon_stocks if isinstance(dragon_stocks, list) else []
    sector_stocks = sector_stocks if isinstance(sector_stocks, list) else []

    # 合并去重（code 为 key，保留信息最丰富的那条）
    pool: Dict[str, Dict] = {}
    for stock_list in [inflow_stocks, momentum_stocks, sector_stocks, dragon_stocks]:
        for s in stock_list:
            code = s.get("code", "")
            if not code:
                continue
            if code not in pool:
                pool[code] = s
            else:
                # 合并信息：更新来源为组合，保留净流入（取较大值）
                existing = pool[code]
                existing["_source"] = f"{existing.get('_source','')},{s.get('_source','')}"
                if s.get("net_inflow", 0) > existing.get("net_inflow", 0):
                    existing["net_inflow"] = s["net_inflow"]

    candidates = list(pool.values())
    logger.info(f"Phase1 宽选候选池: {len(candidates)} 只（去重后）")
    return candidates


# ─────────────────────────────────────────────────────────────
# 技术指标计算（基于K线数据）
# ─────────────────────────────────────────────────────────────

def _calc_rsi_score(closes: np.ndarray) -> float:
    """RSI 在 30-65 区间加分，超买/超卖减分"""
    if len(closes) < 15:
        return 0.0
    rsi_arr = ti.rsi(closes, period=14)
    if len(rsi_arr) == 0:
        return 0.0
    rsi = float(rsi_arr[-1])
    if 30 <= rsi <= 65:
        return 15.0  # 健康区间，加分
    elif 20 <= rsi < 30:
        return 8.0   # 超卖区，可能反弹
    elif 65 < rsi <= 80:
        return 5.0   # 偏强但未超买
    elif rsi > 80:
        return -10.0 # 超买，风险高
    else:
        return 0.0


def _calc_macd_score(closes: np.ndarray) -> float:
    """MACD 金叉/即将金叉加分"""
    if len(closes) < 30:
        return 0.0
    macd_line, signal_line, histogram = ti.macd(closes)
    if len(histogram) < 3:
        return 0.0
    # 金叉：MACD上穿信号线（最近1-2根柱子）
    h_prev = float(histogram[-2]) if len(histogram) >= 2 else 0
    h_curr = float(histogram[-1])
    m_curr = float(macd_line[-1]) if len(macd_line) > 0 else 0
    s_curr = float(signal_line[-1]) if len(signal_line) > 0 else 0

    if h_prev < 0 and h_curr > 0:
        return 20.0  # 金叉发生
    elif h_curr > 0 and m_curr > s_curr and h_curr > h_prev:
        return 10.0  # MACD上行，柱子扩张
    elif h_prev < 0 and abs(h_curr) < abs(h_prev):
        return 8.0   # 死叉收敛，即将金叉
    elif h_curr < 0:
        return -5.0  # 死叉区域
    return 5.0


def _calc_bollinger_score(closes: np.ndarray) -> float:
    """布林带位置加分：下轨附近为买入区"""
    if len(closes) < 25:
        return 0.0
    upper, middle, lower = ti.bollinger_bands(closes, period=20)
    if len(upper) == 0 or len(lower) == 0:
        return 0.0
    price = float(closes[-1])
    u, m, l = float(upper[-1]), float(middle[-1]), float(lower[-1])
    band_width = u - l
    if band_width <= 0:
        return 0.0
    position = (price - l) / band_width  # 0=下轨, 1=上轨

    if position <= 0.25:
        return 15.0  # 下轨附近，强买信号
    elif position <= 0.5:
        return 8.0   # 中轨以下
    elif position <= 0.75:
        return 3.0   # 中轨以上
    else:
        return -5.0  # 接近上轨，超买风险


def _calc_ma_alignment_score(closes: np.ndarray) -> float:
    """均线多头排列：MA5 > MA10 > MA20 > MA60"""
    if len(closes) < 65:
        return 0.0
    ma5  = float(ti.sma(closes, 5)[-1])   if len(ti.sma(closes, 5))  > 0 else None
    ma10 = float(ti.sma(closes, 10)[-1])  if len(ti.sma(closes, 10)) > 0 else None
    ma20 = float(ti.sma(closes, 20)[-1])  if len(ti.sma(closes, 20)) > 0 else None
    ma60 = float(ti.sma(closes, 60)[-1])  if len(ti.sma(closes, 60)) > 0 else None

    if None in (ma5, ma10, ma20, ma60):
        return 0.0

    score = 0.0
    if ma5 > ma10:
        score += 3.0
    if ma10 > ma20:
        score += 4.0
    if ma20 > ma60:
        score += 5.0
    if ma5 > ma10 > ma20 > ma60:
        score += 5.0  # 完美多头排列额外加分
    return min(score, 15.0)


def _calc_volume_score(volumes: np.ndarray) -> float:
    """成交量温和放大：近5日均量 vs 近20日均量"""
    if len(volumes) < 20:
        return 0.0
    avg5  = float(np.mean(volumes[-5:]))
    avg20 = float(np.mean(volumes[-20:]))
    if avg20 <= 0:
        return 0.0
    ratio = avg5 / avg20
    if 1.1 <= ratio <= 2.5:
        return 10.0  # 温和放量，理想状态
    elif ratio > 2.5:
        return 3.0   # 放量过大，可能是高位出货
    elif 0.8 <= ratio < 1.1:
        return 5.0   # 缩量，中性偏弱
    else:
        return 0.0   # 严重缩量


def _calc_momentum_score(closes: np.ndarray) -> float:
    """动量因子：5日涨幅适中(1-8%)、20日动量为正"""
    score = 0.0
    if len(closes) >= 6:
        chg5d = (closes[-1] - closes[-6]) / closes[-6] * 100 if closes[-6] > 0 else 0
        if 1.0 <= chg5d <= 8.0:
            score += 15.0
        elif 8.0 < chg5d <= 15.0:
            score += 5.0  # 涨多了，谨慎
        elif chg5d < 0:
            score -= 5.0

    if len(closes) >= 21:
        chg20d = (closes[-1] - closes[-21]) / closes[-21] * 100 if closes[-21] > 0 else 0
        if chg20d > 5:
            score += 10.0
        elif chg20d > 0:
            score += 5.0
        else:
            score -= 5.0
    return score


# ─────────────────────────────────────────────────────────────
# Phase 2: 量化预筛 - 多因子打分
# ─────────────────────────────────────────────────────────────

def _score_fundamentals(stock: Dict) -> float:
    """基本面因子打分（最高25分）"""
    score = 0.0
    pe   = stock.get("pe_ttm") or stock.get("pe")
    pb   = stock.get("pb")
    mcap = stock.get("market_cap_b") or 0

    # PE 合理区间 5-40x（避免亏损股和高估股）
    if pe:
        if 5 < pe <= 20:
            score += 15.0
        elif 20 < pe <= 40:
            score += 8.0
        elif 0 < pe <= 5:
            score += 5.0  # 可能银行/低估值
        elif pe > 40:
            score -= 5.0

    # PB < 5（安全边际）
    if pb:
        if 0 < pb < 2:
            score += 7.0
        elif 2 <= pb < 5:
            score += 3.0
        elif pb >= 5:
            score -= 3.0

    # 市值 30-500亿（流动性良好）
    if 30 <= mcap <= 500:
        score += 5.0
    elif 500 < mcap <= 2000:
        score += 2.0  # 大盘股，流动性好但弹性小

    return min(score, 25.0)


def _score_capital_flow(stock: Dict) -> float:
    """资金面因子打分（最高25分）"""
    score = 0.0
    net_inflow = stock.get("net_inflow", 0) or 0
    inflow_rate = stock.get("inflow_rate", 0) or 0

    # 主力净流入（绝对值）
    if net_inflow > 5e8:       # >5亿
        score += 15.0
    elif net_inflow > 1e8:     # >1亿
        score += 10.0
    elif net_inflow > 3e7:     # >3000万
        score += 6.0
    elif net_inflow > 0:
        score += 3.0
    else:
        score -= 5.0           # 净流出

    # 净流入率（占成交额比例）
    if inflow_rate > 0.05:     # >5%
        score += 10.0
    elif inflow_rate > 0.02:
        score += 5.0
    elif inflow_rate > 0:
        score += 2.0

    return min(score, 25.0)


async def compute_technical_score(code: str) -> float:
    """
    拉取 K 线，计算技术面综合得分（最高50分）
    RSI(15) + MACD(20) + 布林带(15) + 均线排列(15) + 成交量(10) + 动量(15)
    标准化到0-50
    """
    try:
        klines = await eastmoney_api.get_kline_data(code, klt="101", limit=100)
        if not klines or len(klines) < 10:
            return 0.0

        closes  = np.array([k["close"]  for k in klines], dtype=float)
        volumes = np.array([k["volume"] for k in klines], dtype=float)

        rsi_score    = _calc_rsi_score(closes)
        macd_score   = _calc_macd_score(closes)
        boll_score   = _calc_bollinger_score(closes)
        ma_score     = _calc_ma_alignment_score(closes)
        vol_score    = _calc_volume_score(volumes)
        mom_score    = _calc_momentum_score(closes)

        raw = rsi_score + macd_score + boll_score + ma_score + vol_score + mom_score
        # 原始总分上限约 80，标准化到 0-50
        normalized = max(0.0, min(50.0, raw / 80.0 * 50.0))
        return round(normalized, 2)

    except Exception as e:
        logger.warning(f"技术评分失败 {code}: {e}")
        return 0.0


async def quant_prescore(stock: Dict) -> float:
    """
    综合量化预筛分（0-100）
    技术面(0-50) + 基本面(0-25) + 资金面(0-25)
    """
    code = stock.get("code", "")
    tech_score  = await compute_technical_score(code)
    fund_score  = _score_fundamentals(stock)
    cap_score   = _score_capital_flow(stock)

    total = tech_score + fund_score + cap_score
    return round(min(100.0, max(0.0, total)), 2)


async def run_phase2_screening(
    candidates: List[Dict],
    target_count: int = 10,
) -> List[StockCandidate]:
    """
    Phase 2: 对候选池进行量化多因子打分，筛选出 8-12 只候选股
    并发计算技术面分数
    """
    logger.info(f"Phase2 量化预筛: 对 {len(candidates)} 只候选股打分...")

    # 并发获取各股技术分（限制并发数避免触发限流）
    semaphore = asyncio.Semaphore(8)

    async def _score_one(stock: Dict) -> Dict:
        async with semaphore:
            code = stock.get("code", "")
            try:
                tech_score = await compute_technical_score(code)
            except Exception:
                tech_score = 0.0
            fund_score = _score_fundamentals(stock)
            cap_score  = _score_capital_flow(stock)
            total = round(min(100.0, max(0.0, tech_score + fund_score + cap_score)), 2)
            return {**stock, "_quant_score": total}

    scored_stocks = await asyncio.gather(*[_score_one(s) for s in candidates])

    # 按量化分降序排列，取前 target_count 只
    scored_stocks = sorted(scored_stocks, key=lambda x: x.get("_quant_score", 0), reverse=True)
    top_n = scored_stocks[:target_count]

    # 补充5日涨幅（从K线计算）
    result_candidates = []
    for s in top_n:
        code = s.get("code", "")
        change_pct_5d = 0.0
        try:
            klines = await eastmoney_api.get_kline_data(code, klt="101", limit=10)
            if klines and len(klines) >= 6:
                close_now  = klines[-1]["close"]
                close_5d   = klines[-6]["close"]
                change_pct_5d = round((close_now - close_5d) / close_5d * 100, 2) if close_5d > 0 else 0.0
        except Exception:
            change_pct_5d = s.get("change_pct", 0) or 0.0  # fallback 当日涨幅

        candidate = StockCandidate(
            code=code,
            name=s.get("name", ""),
            price=s.get("price", 0.0) or 0.0,
            change_pct_5d=change_pct_5d,
            net_inflow=s.get("net_inflow", 0.0) or 0.0,
            pe_ttm=s.get("pe_ttm"),
            pb=s.get("pb"),
            market_cap_b=s.get("market_cap_b"),
            quant_score=s.get("_quant_score", 0.0),
            master_score=0.0,   # Phase3 填充
            composite_score=0.0, # Phase4 填充
            source=s.get("_source", ""),
            sector_name=s.get("_sector_name", s.get("sector_name", "")),
        )
        result_candidates.append(candidate)

    logger.info(f"Phase2 量化预筛完成: 保留 {len(result_candidates)} 只候选股")
    for c in result_candidates:
        logger.info(f"  {c.code} {c.name}: quant_score={c.quant_score}")
    return result_candidates
