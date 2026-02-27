"""
Warren Buffett Agent - 价值投资风格（批量模式：1次LLM调用分析所有股票）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

BUFFETT_SYSTEM = """你是沃伦·巴菲特 (Warren Buffett)，用价值投资原则分析A股。

核心原则：护城河、安全边际、长期持有、财务保守、能力圈。
分析重点：ROE、毛利率、PE/PB估值、负债率、现金流、股息。

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class WarrenBuffett(BaseAgent):
    def __init__(self):
        super().__init__(
            name="WarrenBuffett",
            description="巴菲特价值投资风格：寻找护城河、安全边际、长期持有"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])

        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Buffett 数据获取失败 {code}: {e}")
                all_data[code] = {"error": str(e)}

        return await self._llm_batch_analyze(all_data)

    async def _fetch_data(self, stock_code: str) -> Dict[str, Any]:
        from data.eastmoney import eastmoney_api
        try:
            quote = await eastmoney_api.get_quote(stock_code)
            return {
                "name": quote.get("name", ""),
                "price": quote.get("price", 0),
                "pe": quote.get("pe_ttm") or quote.get("pe", 0),
                "pb": quote.get("pb", 0),
                "change_pct": quote.get("change_pct", 0),
                "market_cap_b": round((quote.get("market_cap", 0) or 0) / 1e8, 2),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _llm_batch_analyze(self, all_data: Dict) -> Dict[str, AgentSignal]:
        prompt = (
            f"以巴菲特的价值投资视角，分析以下A股股票并批量返回信号：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=BUFFETT_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="价值分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
