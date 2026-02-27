"""
基本面分析 Agent - 获取财务数据，LLM 批量分析（1次LLM调用）
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from llm.client import acall_llm

logger = logging.getLogger(__name__)


class FundamentalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            name="FundamentalAnalyst",
            description="分析财务数据、估值水平、盈利能力和成长性"
        )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])

        all_fundamentals = {}
        for code in target_stocks:
            try:
                fd = await self._fetch_fundamentals(code)
                all_fundamentals[code] = fd if fd else {"error": "数据获取失败"}
            except Exception as e:
                logger.warning(f"基本面数据获取失败 {code}: {e}")
                all_fundamentals[code] = {"error": str(e)}

        return await self._llm_batch_analyze(all_fundamentals)

    async def _fetch_fundamentals(self, stock_code: str) -> Dict[str, Any] | None:
        from data.eastmoney import eastmoney_api
        try:
            quote = await eastmoney_api.get_quote(stock_code)
            if not quote:
                return None
            return {
                "name": quote.get("name", ""),
                "price": quote.get("price", 0),
                "pe_ttm": quote.get("pe_ttm") or quote.get("pe", 0),
                "pb": quote.get("pb", 0),
                "market_cap_b": round((quote.get("market_cap", 0) or 0) / 1e8, 2),
                "change_pct": quote.get("change_pct", 0),
            }
        except Exception as e:
            logger.warning(f"行情获取失败 {stock_code}: {e}")
            return None

    async def _llm_batch_analyze(self, all_fundamentals: Dict) -> Dict[str, AgentSignal]:
        system_prompt = (
            "你是专业A股基本面分析师。根据各股票的财务数据，"
            "从估值（PE/PB）、市值、涨跌幅等维度综合判断，"
            "给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。"
        )
        prompt = (
            f"请对以下股票的基本面数据批量分析并返回信号：\n\n"
            f"{json.dumps(all_fundamentals, ensure_ascii=False, indent=2)}"
        )

        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=system_prompt,
            max_tokens=1200,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="基本面分析暂时不可用")
                for code in all_fundamentals
            }),
        )
        return result.signals
