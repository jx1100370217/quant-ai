"""
Ben Graham Agent - 价值投资之父（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

GRAHAM_SYSTEM = """你是本杰明·格雷厄姆 (Benjamin Graham)，价值投资之父，《证券分析》和《聪明的投资者》作者。

核心原则：安全边际（Margin of Safety）是一切；只买被严重低估的股票；逆向投资；用内在价值保护本金。
分析重点：
- 格雷厄姆数 = √(22.5 × EPS × BVPS)，低于格雷厄姆数30%以上才买
- PE < 15（最高不超过25）
- PB < 1.5（最高不超过2.5）
- 若PE×PB < 22.5，可接受
- 流动比率 > 2，负债率低
- 连续多年盈利，股息历史稳定

判断标准：PE<15且PB<1.5 → bullish；PE>25或PB>3 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class BenGraham(BaseAgent):
    def __init__(self):
        super().__init__(
            name="BenGraham",
            description="格雷厄姆价值投资：安全边际、低PE/PB、逆向投资"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Graham 数据获取失败 {code}: {e}")
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
            "以本杰明·格雷厄姆的严格价值标准（安全边际、PE<15、PB<1.5），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=GRAHAM_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="价值分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
