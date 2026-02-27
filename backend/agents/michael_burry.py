"""
Michael Burry Agent - 大空头逆向深度价值（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

BURRY_SYSTEM = """你是Michael Burry，Scion Asset Management创始人，因"大空头"而闻名全球的逆向深度价值投资者。

核心原则：逆向思维；深度调研找市场定价错误；自由现金流是王道；清算价值提供安全垫。
分析重点：
- 自由现金流收益率（FCF Yield），越高越好（>10%是理想）
- EV/EBITDA，低于行业均值且业务扎实 → 低估
- 被市场遗忘的冷门低位股（反向指标：市场不关注但基本面稳健）
- 基本面与价格的明显背离（价格超跌，业务正常）
- 警惕：高负债、虚假账目、泡沫行业

判断标准：FCF充沛+低估值+市场恐慌超跌 → bullish；泡沫估值+基本面恶化 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class MichaelBurry(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MichaelBurry",
            description="伯里大空头：逆向深度价值、FCF、清算价值、做空泡沫"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Burry 数据获取失败 {code}: {e}")
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
            "以Michael Burry的逆向深度价值视角（FCF、清算价值、超跌错误定价），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=BURRY_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="逆向价值分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
