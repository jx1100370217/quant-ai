"""
情绪分析 Agent - 获取市场情绪数据，LLM 批量分析（1次LLM调用）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)


class SentimentAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SentimentAnalyst",
            description="分析龙虎榜、涨跌停数据、板块轮动、资金流向，判断市场情绪"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])
        sentiment_data = await self._fetch_market_sentiment()
        return await self._llm_batch_analyze(target_stocks, sentiment_data)

    async def _fetch_market_sentiment(self) -> Dict[str, Any]:
        from data.eastmoney import eastmoney_api
        result = {}

        try:
            stats = await eastmoney_api.get_market_stats()
            result["market_stats"] = {
                "up_count": stats.get("up_count", 0),
                "down_count": stats.get("down_count", 0),
                "limit_up": stats.get("limit_up", 0),
                "limit_down": stats.get("limit_down", 0),
            }
        except Exception as e:
            logger.warning(f"市场统计获取失败: {e}")
            result["market_stats"] = {}

        try:
            sectors = await eastmoney_api.get_sector_list()
            if sectors:
                result["hot_sectors"] = [
                    {"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)}
                    for s in sectors[:5]
                ]
        except Exception as e:
            logger.warning(f"板块数据获取失败: {e}")
            result["hot_sectors"] = []

        return result

    async def _llm_batch_analyze(self, stocks: list, sentiment_data: Dict) -> Dict[str, AgentSignal]:
        system_prompt = (
            "你是专业A股市场情绪分析师。根据市场涨跌停、热门板块等情绪数据，"
            "判断每只股票的市场情绪（bullish/bearish/neutral），"
            "给出置信度(0-100)和简短中文推理(≤80字)。"
        )
        prompt = (
            f"市场情绪数据：\n{json.dumps(sentiment_data, ensure_ascii=False, indent=2)}\n\n"
            f"请基于市场情绪对以下股票批量给出信号：\n{json.dumps(stocks)}"
        )

        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=system_prompt,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=35, reasoning="情绪分析暂时不可用")
                for code in stocks
            }),
        )
        return result.signals
