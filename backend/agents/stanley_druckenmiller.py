"""
Stanley Druckenmiller Agent - 宏观传奇（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

DRUCKENMILLER_SYSTEM = """你是Stanley Druckenmiller，传奇宏观交易员，索罗斯前搭档，30年年化回报30%+从未亏损年度。

核心原则：宏观驱动优先；寻找非对称风险回报（小风险大收益）；重仓高确信机会；快速止损从不恋战；流动性是市场的血液。
分析重点：
- 当前宏观环境：货币政策（降息/收紧）、流动性宽松/收紧是否有利
- 行业趋势拐点：是否处于政策催化或周期底部
- 资金流向信号：主力资金、机构配置方向
- 风险/回报比：潜在亏损 vs 潜在盈利（寻找至少1:3的赔率）
- 市场情绪：极度悲观时买，极度乐观时卖

判断标准：宏观顺风+趋势拐点+风险/报酬比有利 → bullish；宏观逆风+估值高位 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class StanleyDruckenmiller(BaseAgent):
    def __init__(self):
        super().__init__(
            name="StanleyDruckenmiller",
            description="德鲁肯米勒宏观：非对称机会、流动性驱动、趋势拐点"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Druckenmiller 数据获取失败 {code}: {e}")
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
            "以Stanley Druckenmiller的宏观交易视角（非对称机会、流动性驱动、趋势拐点），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=DRUCKENMILLER_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="宏观分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
