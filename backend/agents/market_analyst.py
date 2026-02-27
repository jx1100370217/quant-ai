"""
市场分析 Agent - 分析大盘走势，LLM 批量判断每只股票的市场环境（1次LLM调用）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from data.eastmoney import eastmoney_api
from llm.client import acall_llm

logger = logging.getLogger(__name__)


class MarketAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MarketAnalyst",
            description="分析大盘走势、板块轮动、资金流向，判断市场整体方向"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])
        market_data = await self._fetch_market_data()
        return await self._llm_batch_analyze(target_stocks, market_data)

    async def _fetch_market_data(self) -> Dict[str, Any]:
        result = {}

        # 主要指数
        try:
            quotes = await eastmoney_api.get_batch_quotes(["000001", "399001", "399006"])
            result["indices"] = {
                code: {
                    "name": q.get("name", code),
                    "price": q.get("price", 0),
                    "change_pct": round(q.get("change_pct", 0), 2),
                }
                for code, q in quotes.items()
            }
        except Exception as e:
            logger.warning(f"指数数据获取失败: {e}")
            result["indices"] = {}

        # 市场统计
        try:
            stats = await eastmoney_api.get_market_stats()
            result["market_stats"] = stats
        except Exception as e:
            logger.warning(f"市场统计获取失败: {e}")
            result["market_stats"] = {}

        # 板块数据
        try:
            sectors = await eastmoney_api.get_sector_list()
            if sectors:
                result["top_sectors"] = sectors[:5]
        except Exception as e:
            logger.warning(f"板块数据获取失败: {e}")
            result["top_sectors"] = []

        return result

    async def _llm_batch_analyze(self, stocks: list, market_data: Dict) -> Dict[str, AgentSignal]:
        system_prompt = (
            "你是专业A股市场分析师。根据大盘环境数据，"
            "判断每只股票所处的市场环境（bullish/bearish/neutral），"
            "给出置信度(0-100)和简短中文推理(≤80字)。"
        )
        prompt = (
            f"大盘市场数据：\n{json.dumps(market_data, ensure_ascii=False, indent=2)}\n\n"
            f"请基于以上市场环境，对以下股票代码各自给出市场环境信号：\n"
            f"{json.dumps(stocks, ensure_ascii=False)}"
        )

        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=system_prompt,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=40, reasoning="市场分析暂时不可用")
                for code in stocks
            }),
        )
        return result.signals
