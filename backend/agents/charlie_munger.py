"""
Charlie Munger Agent - 品质投资风格（批量模式：1次LLM调用）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

MUNGER_SYSTEM = """你是查理·芒格 (Charlie Munger)，用品质投资原则分析A股。

核心原则：以合理价格买入优秀企业、多元思维模型、逆向思维、护城河可持续性。
分析重点：商业模式质量、管理层品德、定价权、行业竞争格局、长期可预测性。

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class CharlieMunger(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CharlieMunger",
            description="芒格品质投资风格：护城河、可预测性、逆向思考"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])

        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Munger 数据获取失败 {code}: {e}")
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
            }
        except Exception as e:
            return {"error": str(e)}

    async def _llm_batch_analyze(self, all_data: Dict) -> Dict[str, AgentSignal]:
        prompt = (
            f"以芒格的品质投资视角（多元思维、护城河可持续），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=MUNGER_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="品质分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
