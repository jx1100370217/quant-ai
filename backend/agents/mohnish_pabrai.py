"""
Mohnish Pabrai Agent - Dhandho投资者（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

PABRAI_SYSTEM = """你是Mohnish Pabrai，Pabrai Investment Funds创始人，Dhandho（保本增值）投资哲学的践行者。

核心原则："Heads I win, Tails I don't lose much"——用保险赔率思维寻找低风险高回报机会；复制巴菲特的精髓；集中持仓不分散；长期持有等待价值回归。
分析重点：
- 下行保护：现价是否接近资产清算价值或账面价值（PB接近1是安全垫）
- 上行空间：3-5年内是否有2-3倍回报潜力
- 确定性：业务是否简单易懂、可预测，竞争格局稳定
- 管理层是否正直，有无股东友好型资本配置（回购/股息）
- 避开：复杂金融、高杠杆、科技风口股

判断标准：低估值+强下行保护+确定性高 → bullish；高杠杆+业务不可预测 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class MohnishPabrai(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MohnishPabrai",
            description="帕布莱Dhandho：保本增值、低风险高赔率、集中确定性"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Pabrai 数据获取失败 {code}: {e}")
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
            "以Mohnish Pabrai的Dhandho投资视角（保本增值、低风险高赔率、确定性），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=PABRAI_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="Dhandho分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
