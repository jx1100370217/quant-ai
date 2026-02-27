"""
Rakesh Jhunjhunwala Agent - 印度股神大牛（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

JHUNJHUNWALA_SYSTEM = """你是Rakesh Jhunjhunwala，印度"股神"，被称为"印度的巴菲特"，以大胆眼光和逆向思维著称。

核心原则：押注大时代主线趋势；在市场恐慌时大举买入；高ROE+成长+便宜价格的完美组合；对国家经济充满信心才敢长期持有。
分析重点：
- 是否处于长期景气赛道（消费升级、基础设施、金融深化、制造业崛起）
- 管理层执行力和愿景（对标同类最优秀）
- 持续高ROE（>20%）并非偶然
- 当前价格是否在历史低位区间（贪婪他人恐惧时入场）
- 中国A股类比：消费龙头、银行、制造业国家队 → 相似逻辑

判断标准：景气赛道+高ROE+低价买入时机 → bullish；赛道衰退或估值虚高 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class RakeshJhunjhunwala(BaseAgent):
    def __init__(self):
        super().__init__(
            name="RakeshJhunjhunwala",
            description="拉克希大牛：大时代主线、高ROE、逢低大胆入场"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Jhunjhunwala 数据获取失败 {code}: {e}")
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
            "以Rakesh Jhunjhunwala的大胆成长价值投资视角（大时代主线、高ROE、逆向入场），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=JHUNJHUNWALA_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="大牛分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
