"""
Peter Lynch Agent - 成长投资风格（批量模式：1次LLM调用）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

LYNCH_SYSTEM = """你是彼得·林奇 (Peter Lynch)，用成长投资原则分析A股。

核心原则：GARP（合理价格成长）、寻找十倍股、投资你了解的公司、PEG < 1 是好机会。
分析重点：营收/利润增长率、PEG比率、行业地位、业务简单易懂、内部人持股。

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class PeterLynch(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PeterLynch",
            description="彼得·林奇成长投资风格：GARP、寻找十倍股"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])

        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Lynch 数据获取失败 {code}: {e}")
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
                "change_pct": quote.get("change_pct", 0),
                "market_cap_b": round((quote.get("market_cap", 0) or 0) / 1e8, 2),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _llm_batch_analyze(self, all_data: Dict) -> Dict[str, AgentSignal]:
        prompt = (
            f"以彼得·林奇的成长投资视角（寻找十倍股、GARP），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=LYNCH_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="成长分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
