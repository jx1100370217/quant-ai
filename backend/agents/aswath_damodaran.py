"""
Aswath Damodaran Agent - 估值院长（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

DAMODARAN_SYSTEM = """你是Aswath Damodaran，纽约大学斯特恩商学院教授，被誉为"华尔街估值院长"。

核心原则：内在价值驱动投资决策；故事与数字必须匹配；增长不能脱离现实；风险溢价决定价值。
分析重点：PE/PB相对同行合理性、增长预期与现价是否匹配、风险调整后回报、股息贴现模型逻辑。

判断标准：
- PE低于行业均值且增长前景良好 → bullish
- 估值虚高、增长故事不可信 → bearish  
- 数据不足或估值合理 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class AswathDamodaran(BaseAgent):
    def __init__(self):
        super().__init__(
            name="AswathDamodaran",
            description="估值院长：DCF、相对估值、叙事与数字结合"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Damodaran 数据获取失败 {code}: {e}")
                all_data[code] = {"error": str(e)}
        return await self._llm_batch_analyze(all_data)

    async def _fetch_data(self, stock_code: str) -> Dict[str, Any]:
        from data.eastmoney import eastmoney_api
        try:
            quote = await eastmoney_api.get_quote(stock_code)
            return {
                "name": quote.get("name", ""),
                "price": quote.get("price", 0),
                "pe_ttm": quote.get("pe_ttm"),
                "pb": quote.get("pb"),
                "change_pct": quote.get("change_pct", 0),
                "market_cap_b": quote.get("market_cap_b"),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _llm_batch_analyze(self, all_data: Dict) -> Dict[str, AgentSignal]:
        prompt = (
            "以Damodaran的估值框架（DCF、相对估值、故事配数字），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=DAMODARAN_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="估值分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
