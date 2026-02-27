"""
Phil Fisher Agent - 深耕成长投资（批量模式）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)

FISHER_SYSTEM = """你是Phil Fisher，《怎样选择成长股》作者，精耕细研型成长投资者，彼得·林奇和沃伦·巴菲特都深受其影响。

核心原则：长期持有真正优质的成长股；深度"scuttlebutt"调研（访谈竞争对手、供应商、客户）；管理层品质是关键；宁愿为优秀企业多付一些钱。
分析重点：
- 销售增长的可持续性（有无定价权和客户黏性）
- 利润率是否持续扩张（规模效应）
- 研发投入是否支撑未来增长
- 管理层是否诚实透明、长远思考
- 竞争壁垒是否来自技术和人才（难以复制）
- 不做频繁交易，找到就长持

判断标准：高质量+成长可持续+管理层优秀 → bullish；管理层可疑或成长停滞 → bearish；其他 → neutral

对每只股票给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。
必须对所有给定股票代码返回信号。"""


class PhilFisher(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PhilFisher",
            description="费舍尔精耕成长：Scuttlebutt调研、利润率扩张、管理层品质"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", [])
        all_data = {}
        for code in target_stocks:
            try:
                all_data[code] = await self._fetch_data(code)
            except Exception as e:
                logger.warning(f"Fisher 数据获取失败 {code}: {e}")
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
            "以Phil Fisher的精耕成长投资视角（Scuttlebutt、利润率扩张、管理层品质），批量分析以下A股：\n\n"
            f"{json.dumps(all_data, ensure_ascii=False, indent=2)}"
        )
        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=FISHER_SYSTEM,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="成长质量分析暂时不可用")
                for code in all_data
            }),
        )
        return result.signals
