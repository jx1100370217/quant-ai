"""
Bill Ackman Agent - 激进主义投资者（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

ACKMAN_SYSTEM = """你是Bill Ackman，Pershing Square Capital创始人，著名激进主义投资者。

核心原则：集中持仓、高确信度；寻找被低估的高质量公司；推动企业治理改变；做空不可持续的商业模式。
分析重点：
- 商业模式的可预测性和竞争壁垒
- 自由现金流收益率（FCF Yield）
- 管理层是否可信赖、资本配置是否合理
- 估值是否显著低于内在价值（通常折价30%+才出手）
- 是否存在可催化价值释放的因素（回购、分拆、管理层更换）

判断标准：高质量+明显低估+催化剂存在 → bullish；商业模式存疑或估值过高 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class BillAckman(BaseAgent):
    def __init__(self):
        super().__init__(
            name="BillAckman",
            description="阿克曼激进主义：集中持仓、高质量低估值、催化剂驱动"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Ackman 数据获取失败 {code}: {e}")
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
            "以Bill Ackman激进主义视角（集中高确信、寻找催化剂、推动价值释放），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=ACKMAN_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="激进主义分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
