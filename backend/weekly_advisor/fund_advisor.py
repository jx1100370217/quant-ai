"""具体公募基金周推荐：在精选主动权益 C 类份额中横向比较盈利空间。"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import aiohttp

from .asset_models import FundRecommendation, FundWeeklyReport
from .asset_report_store import save_asset_report


logger = logging.getLogger(__name__)
STRATEGY_VERSION = "FUND-MOMENTUM-v1"
RANK_WEIGHTS = (25.0, 20.0, 15.0, 10.0, 10.0)
FUND_NAV_URL = "https://api.fund.eastmoney.com/f10/lsjz"
_NAV_CACHE_FILE = Path(__file__).resolve().parent.parent / "cache" / "funds" / "nav-history.json"

# 主动权益 C 类份额精选池。统一比较同一份额类别，避免 A/C 收费结构和净值差异混淆。
# 包含用户点名的“财通成长优选混合C”，并覆盖科技、制造、消费、医药和均衡成长。
FUND_UNIVERSE: tuple[dict[str, str], ...] = (
    {"code": "021528", "name": "财通成长优选混合C", "fund_type": "混合型-灵活"},
    {"code": "004241", "name": "中欧时代先锋股票C", "fund_type": "股票型"},
    {"code": "025333", "name": "诺安成长混合C", "fund_type": "混合型-偏股"},
    {"code": "012771", "name": "宝盈优势产业混合C", "fund_type": "混合型-灵活"},
    {"code": "017821", "name": "招商优势企业混合C", "fund_type": "混合型-偏股"},
    {"code": "025542", "name": "华夏行业景气混合C", "fund_type": "混合型-偏股"},
    {"code": "014162", "name": "万家人工智能混合C", "fund_type": "混合型-偏股"},
    {"code": "018125", "name": "永赢先进制造智选混合发起C", "fund_type": "混合型-偏股"},
    {"code": "018998", "name": "景顺长城研究精选股票C", "fund_type": "股票型"},
    {"code": "014320", "name": "德邦半导体产业混合发起式C", "fund_type": "混合型-偏股"},
    {"code": "021523", "name": "财通价值动量混合C", "fund_type": "混合型-灵活"},
    {"code": "016234", "name": "财通景气行业混合C", "fund_type": "混合型-偏股"},
    {"code": "019018", "name": "易方达信息产业混合C", "fund_type": "混合型-偏股"},
    {"code": "013620", "name": "华安媒体互联网混合C", "fund_type": "混合型-灵活"},
    {"code": "011705", "name": "东方阿尔法产业先锋混合C", "fund_type": "混合型-偏股"},
    {"code": "014642", "name": "摩根新兴动力混合C", "fund_type": "混合型-偏股"},
    {"code": "013511", "name": "汇丰晋信低碳先锋股票C", "fund_type": "股票型"},
    {"code": "008228", "name": "宝盈研究精选混合C", "fund_type": "混合型-偏股"},
    {"code": "018994", "name": "中欧数字经济混合发起C", "fund_type": "混合型-偏股"},
    {"code": "012800", "name": "宏利转型机遇股票C", "fund_type": "股票型"},
    {"code": "018241", "name": "嘉实制造升级股票发起式C", "fund_type": "股票型"},
    {"code": "015048", "name": "建信新能源行业股票C", "fund_type": "股票型"},
    {"code": "011323", "name": "国泰智能汽车股票C", "fund_type": "股票型"},
    {"code": "005928", "name": "创金合信新能源汽车股票C", "fund_type": "股票型"},
    {"code": "006229", "name": "中欧医疗创新股票C", "fund_type": "股票型"},
    {"code": "009163", "name": "广发医疗保健股票C", "fund_type": "股票型"},
    {"code": "010687", "name": "工银文体产业股票C", "fund_type": "股票型"},
    {"code": "014043", "name": "银华心怡灵活配置混合C", "fund_type": "混合型-灵活"},
    {"code": "013188", "name": "华夏能源革新股票C", "fund_type": "股票型"},
    {"code": "013860", "name": "宝盈品质甄选混合C", "fund_type": "混合型-偏股"},
    {"code": "026155", "name": "红土创新新科技股票C", "fund_type": "股票型"},
    {"code": "025541", "name": "华夏创新前沿股票C", "fund_type": "股票型"},
    {"code": "007491", "name": "南方信息创新混合C", "fund_type": "混合型-偏股"},
    {"code": "014243", "name": "富国新材料新能源混合C", "fund_type": "混合型-偏股"},
)

_FUND_LOCK = asyncio.Lock()
_FUND_REPORT_CACHE: Dict[str, Any] = {"date": "", "report": None}


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _pct_change(current: float, previous: float) -> float:
    return (current / previous - 1.0) * 100 if previous > 0 else 0.0


def _max_drawdown(values: Iterable[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, (value / peak - 1.0) * 100)
    return worst


def _target_week() -> str:
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_until_monday)
    friday = monday + timedelta(days=4)
    return f"{monday:%Y-%m-%d} ~ {friday:%Y-%m-%d}"


def _strategy_group(name: str) -> str:
    if any(word in name for word in ("医药", "医疗", "健康")):
        return "医药健康"
    if any(word in name for word in ("新能源", "汽车", "低碳", "能源")):
        return "新能源"
    if any(word in name for word in ("半导体", "科技", "数字", "信息", "互联网", "人工智能")):
        return "科技成长"
    if any(word in name for word in ("制造", "材料", "产业")):
        return "先进制造"
    if any(word in name for word in ("消费", "文体")):
        return "大消费"
    return "均衡成长"


def score_fund_candidate(meta: dict[str, str], history: List[dict]) -> Optional[dict]:
    """基于累计净值计算动量、持续性和回撤调整后的盈利空间分。"""
    valid = sorted(
        (
            item for item in history
            if float(item.get("cumulative_nav") or 0) > 0 and float(item.get("nav") or 0) > 0
        ),
        key=lambda item: str(item.get("date", "")),
    )
    if len(valid) < 65:
        return None

    total_navs = [float(item["cumulative_nav"]) for item in valid]
    current_total = total_navs[-1]
    return_1w = _pct_change(current_total, total_navs[-6])
    return_1m = _pct_change(current_total, total_navs[-21])
    return_3m = _pct_change(current_total, total_navs[-61])
    ma20 = sum(total_navs[-20:]) / 20
    ma60 = sum(total_navs[-60:]) / 60
    log_returns = [math.log(total_navs[i] / total_navs[i - 1]) for i in range(len(total_navs) - 59, len(total_navs))]
    volatility_3m = statistics.pstdev(log_returns) * math.sqrt(252) * 100
    max_drawdown_3m = _max_drawdown(total_navs[-61:])
    weekly_returns = [
        _pct_change(total_navs[index], total_navs[index - 5])
        for index in range(len(total_navs) - 56, len(total_navs), 5)
    ]
    positive_week_ratio = sum(value > 0 for value in weekly_returns) / len(weekly_returns) * 100

    score = 42.0
    score += _clip(return_1w * 0.8, -8, 8)
    score += _clip(return_1m * 0.5, -14, 14)
    score += _clip(return_3m * 0.22, -18, 18)
    score += 9 if current_total > ma20 else -9
    score += 6 if ma20 > ma60 else -6
    score += _clip((positive_week_ratio - 50) * 0.18, -7, 7)
    score -= _clip((volatility_3m - 28) * 0.18, 0, 12)
    score -= _clip(abs(min(max_drawdown_3m, 0)) * 0.35, 0, 10)
    potential_score = round(_clip(score, 0, 100), 1)

    daily_volatility = volatility_3m / 100 / math.sqrt(252)
    upside_potential_pct = _clip(
        max(0.0, return_1w * 0.35 + return_1m * 0.08)
        + daily_volatility * math.sqrt(5) * 100 * 0.75,
        0,
        15,
    )
    latest = valid[-1]
    eligible = (
        current_total > ma20
        and ma20 > ma60 * 0.99
        and return_1m > 0
        and max_drawdown_3m >= -25
        and potential_score >= 55
        and "开放" in str(latest.get("subscribe_status", ""))
    )
    return {
        **meta,
        "strategy_group": _strategy_group(meta["name"]),
        "nav": round(float(latest["nav"]), 4),
        "nav_date": str(latest["date"]),
        "potential_score": potential_score,
        "upside_potential_pct": round(upside_potential_pct, 2),
        "return_1w": round(return_1w, 2),
        "return_1m": round(return_1m, 2),
        "return_3m": round(return_3m, 2),
        "volatility_3m": round(volatility_3m, 2),
        "max_drawdown_3m": round(max_drawdown_3m, 2),
        "positive_week_ratio": round(positive_week_ratio, 1),
        "subscribe_status": str(latest.get("subscribe_status") or "未知"),
        "redeem_status": str(latest.get("redeem_status") or "未知"),
        "eligible": eligible,
    }


def _load_nav_cache() -> dict:
    if not _NAV_CACHE_FILE.exists():
        return {}
    try:
        payload = json.loads(_NAV_CACHE_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_nav_cache(payload: dict) -> None:
    _NAV_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _NAV_CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, _NAV_CACHE_FILE)


def _cached_history(cache: dict, code: str, max_age_seconds: float) -> Optional[List[dict]]:
    entry = cache.get(code)
    if not isinstance(entry, dict) or time.time() - float(entry.get("saved_at") or 0) > max_age_seconds:
        return None
    history = entry.get("history")
    return history if isinstance(history, list) and len(history) >= 65 else None


async def _fetch_fund_history(
    session: aiohttp.ClientSession,
    meta: dict[str, str],
    cache: dict,
    force: bool,
) -> Optional[List[dict]]:
    if not force:
        fresh = _cached_history(cache, meta["code"], 6 * 60 * 60)
        if fresh is not None:
            return fresh
    try:
        # 该接口实际最多返回20条/页，即便 pageSize 传入更大值也会被静默截断。
        # 拉取5页可覆盖约100个交易日，满足60日趋势和3个月回撤计算。
        rows: List[dict] = []
        for page_index in range(1, 6):
            async with session.get(
                FUND_NAV_URL,
                params={
                    "fundCode": meta["code"], "pageIndex": page_index, "pageSize": 20,
                    "startDate": "", "endDate": "",
                },
                headers={"Referer": "https://fundf10.eastmoney.com/", "User-Agent": "Mozilla/5.0 QuantAI/2.0"},
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                payload = await response.json(content_type=None)
                page_rows = payload.get("Data", {}).get("LSJZList", [])
                if not isinstance(page_rows, list) or not page_rows:
                    break
                rows.extend(page_rows)
                if len(page_rows) < 20:
                    break

        by_date = {
            str(row.get("FSRQ")): {
                "date": row.get("FSRQ"),
                "nav": float(row.get("DWJZ") or 0),
                "cumulative_nav": float(row.get("LJJZ") or 0),
                "subscribe_status": row.get("SGZT") or "未知",
                "redeem_status": row.get("SHZT") or "未知",
            }
            for row in rows
            if row.get("FSRQ") and row.get("DWJZ") and row.get("LJJZ")
        }
        history = list(by_date.values())
        if len(history) < 65:
            logger.info("基金 %s 历史净值不足: %s 条", meta["code"], len(history))
            return None
        cache[meta["code"]] = {"saved_at": time.time(), "history": history}
        return history
    except Exception as exc:
        stale = _cached_history(cache, meta["code"], 7 * 24 * 60 * 60)
        if stale is not None:
            logger.warning("基金 %s 行情失败，使用缓存: %s", meta["code"], exc)
            return stale
        logger.warning("基金 %s 行情失败且无缓存: %s", meta["code"], exc)
        return None


def _diversified_top(candidates: List[dict], limit: int = 5) -> List[dict]:
    selected: List[dict] = []
    group_counts: Counter[str] = Counter()
    for candidate in candidates:
        group = candidate["strategy_group"]
        if group_counts[group] >= 2:
            continue
        selected.append(candidate)
        group_counts[group] += 1
        if len(selected) >= limit:
            break
    return selected


class FundWeeklyAdvisor:
    """生成具体公募基金产品的横向周推荐。"""

    async def generate(self, force: bool = False) -> FundWeeklyReport:
        today = datetime.now().strftime("%Y-%m-%d")
        if force:
            _FUND_REPORT_CACHE.update({"date": "", "report": None})
        cached = _FUND_REPORT_CACHE.get("report")
        if _FUND_REPORT_CACHE.get("date") == today and cached is not None:
            return cached
        async with _FUND_LOCK:
            cached = _FUND_REPORT_CACHE.get("report")
            if not force and _FUND_REPORT_CACHE.get("date") == today and cached is not None:
                return cached
            report = await self._run_pipeline(force=force)
            _FUND_REPORT_CACHE.update({"date": today, "report": report})
            try:
                save_asset_report(report, "fund")
            except Exception as exc:
                logger.warning("公募基金周报持久化失败: %s", exc)
            return report

    async def _run_pipeline(self, force: bool = False) -> FundWeeklyReport:
        cache = _load_nav_cache()
        semaphore = asyncio.Semaphore(8)
        timeout = aiohttp.ClientTimeout(total=16, connect=7)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async def evaluate(meta: dict[str, str]) -> Optional[dict]:
                async with semaphore:
                    history = await _fetch_fund_history(session, meta, cache, force)
                    return score_fund_candidate(meta, history or [])

            results = await asyncio.gather(*(evaluate(meta) for meta in FUND_UNIVERSE))
        try:
            _save_nav_cache(cache)
        except Exception as exc:
            logger.warning("基金净值缓存写入失败: %s", exc)

        evaluated = [item for item in results if item is not None]
        eligible = sorted(
            (item for item in evaluated if item["eligible"]),
            key=lambda item: (item["potential_score"], item["upside_potential_pct"]),
            reverse=True,
        )
        selected = _diversified_top(eligible, len(RANK_WEIGHTS))
        recommendations: List[FundRecommendation] = []
        for rank, item in enumerate(selected):
            recommendations.append(FundRecommendation(
                code=item["code"], name=item["name"], fund_type=item["fund_type"],
                strategy_group=item["strategy_group"], nav=item["nav"], nav_date=item["nav_date"],
                position_pct=RANK_WEIGHTS[rank], potential_score=item["potential_score"],
                upside_potential_pct=item["upside_potential_pct"], return_1w=item["return_1w"],
                return_1m=item["return_1m"], return_3m=item["return_3m"],
                volatility_3m=item["volatility_3m"], max_drawdown_3m=item["max_drawdown_3m"],
                positive_week_ratio=item["positive_week_ratio"],
                subscribe_status=item["subscribe_status"], redeem_status=item["redeem_status"],
                reason=(
                    f"近1周/1月/3月收益 {item['return_1w']:+.2f}%/{item['return_1m']:+.2f}%/"
                    f"{item['return_3m']:+.2f}%，近12周正收益占比 {item['positive_week_ratio']:.0f}%；"
                    f"在{item['strategy_group']}组内盈利空间分靠前。"
                ),
                risk_note=(
                    f"近3月年化波动 {item['volatility_3m']:.1f}%，最大回撤 {item['max_drawdown_3m']:.1f}%。"
                    "公募基金按未知价申赎，短期赎回费和净值滞后需另行核对。"
                ),
            ))

        invested = round(sum(item.position_pct for item in recommendations), 2)
        if recommendations:
            names = "、".join(item.name for item in recommendations[:3])
            summary = (
                f"对 {len(FUND_UNIVERSE)} 只具体主动权益 C 类基金完成 {len(evaluated)} 只净值评估，"
                f"{len(eligible)} 只通过趋势与回撤约束；盈利空间排名优先关注 {names}。"
            )
        else:
            summary = (
                f"对 {len(FUND_UNIVERSE)} 只具体主动权益 C 类基金完成 {len(evaluated)} 只净值评估，"
                "暂无产品同时通过趋势、持续性与回撤约束。"
            )
        now = datetime.now().isoformat(timespec="seconds")
        return FundWeeklyReport(
            report_date=now[:10], target_week=_target_week(), market_summary=summary,
            recommendations=recommendations, universe_size=len(FUND_UNIVERSE),
            funds_evaluated=len(evaluated), eligible_count=len(eligible),
            invested_position_pct=invested, cash_position_pct=round(100 - invested, 2),
            risk_warning=(
                "盈利空间分和上行情景只用于横向排序，不代表未来收益。C类份额通常持续计提销售服务费，"
                "且各基金短期赎回费、暂停申购和持仓重合度不同，交易前必须核对最新招募说明书。"
            ),
            strategy_notes=(
                "FUND-MOMENTUM-v1：统一比较精选主动权益C类份额，综合1周/1月/3月收益、"
                "12周正收益占比、20/60日趋势、3月波动和最大回撤；同一策略组最多2只，最多推荐5只。"
            ),
            data_source="天天基金 / 东方财富历史净值", generated_at=now,
        )


fund_weekly_advisor = FundWeeklyAdvisor()
