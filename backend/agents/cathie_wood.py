"""
Cathie Wood Agent - 颠覆性成长投资（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

CATHIE_SYSTEM = """你是Cathie Wood，ARK Invest创始人，专注颠覆性科技和指数级成长投资。

核心原则：颠覆性创新重新定价一切；5年以上时间维度；技术融合带来指数增长；TAM远大于市场预期。
分析重点：
- 所属赛道是否为颠覆性科技（AI、基因组、机器人、区块链、储能）
- 业绩是否处于加速增长阶段
- 渗透率是否仍处于早期（S曲线爬升段）
- 高PE是否可被未来增长消化（wright's law：成本随规模下降）
- 即使当前亏损，只要TAM足够大也可接受

判断标准：颠覆性赛道+加速增长+早期渗透 → bullish；传统行业或成熟期 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class CathieWood(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CathieWood",
            description="Cathie Wood创新成长：颠覆性科技、指数增长、5年维度"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"CathieWood 数据获取失败 {code}: {e}")
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
            "以Cathie Wood的颠覆性成长投资视角（5年维度、TAM、创新赛道），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=CATHIE_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="成长分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
