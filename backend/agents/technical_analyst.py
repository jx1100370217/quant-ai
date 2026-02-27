"""
技术分析 Agent - 规则计算指标，LLM 批量解读所有股票信号（1次LLM调用）
"""
from typing import Dict, Any
import json
import logging
import numpy as np

from .base import BaseAgent
from models.agent_models import AgentSignal, BatchSignals
from utils.indicators import TechnicalIndicators
from llm.client import acall_llm

logger = logging.getLogger(__name__)


class TechnicalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            name="TechnicalAnalyst",
            description="计算 MACD/RSI/KDJ/布林带等技术指标，由 LLM 解读生成信号"
        )
        self.indicators = TechnicalIndicators()

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        target_stocks = data.get("target_stocks", ["000001"])

        # 1. 规则计算所有股票指标
        all_indicators = {}
        for code in target_stocks:
            try:
                ind = await self._compute_indicators(code)
                if ind:
                    all_indicators[code] = ind
                else:
                    all_indicators[code] = {"error": "K线数据不足"}
            except Exception as e:
                logger.warning(f"获取 {code} 技术指标失败: {e}")
                all_indicators[code] = {"error": str(e)}

        # 2. 一次 LLM 调用解读所有股票
        return await self._llm_batch_interpret(all_indicators)

    async def _compute_indicators(self, stock_code: str) -> Dict[str, Any] | None:
        from data.eastmoney import eastmoney_api
        try:
            klines = await eastmoney_api.get_kline_data(stock_code, "101", 100)
        except Exception as e:
            logger.warning(f"K线获取失败 {stock_code}: {e}")
            return None

        if not klines or len(klines) < 20:
            return None

        closes = np.array([k["close"] for k in klines], dtype=float)
        highs  = np.array([k["high"]  for k in klines], dtype=float)
        lows   = np.array([k["low"]   for k in klines], dtype=float)
        vols   = np.array([k["volume"] for k in klines], dtype=float)

        def sl(arr):  # safe last
            return round(float(arr[-1]), 4) if arr is not None and len(arr) > 0 else None

        macd_l, macd_s, macd_h = self.indicators.macd(closes)
        rsi = self.indicators.rsi(closes, 14)
        k_val, d_val, j_val = self.indicators.kdj(highs, lows, closes)
        bb_u, bb_m, bb_l = self.indicators.bollinger_bands(closes, 20, 2)
        ma5  = self.indicators.sma(closes, 5)
        ma20 = self.indicators.sma(closes, 20)
        vol_ma5 = self.indicators.sma(vols, 5)

        return {
            "price": round(float(closes[-1]), 2),
            "macd": sl(macd_l), "macd_signal": sl(macd_s), "macd_hist": sl(macd_h),
            "rsi14": sl(rsi),
            "kdj_k": sl(k_val), "kdj_d": sl(d_val), "kdj_j": sl(j_val),
            "bb_upper": sl(bb_u), "bb_mid": sl(bb_m), "bb_lower": sl(bb_l),
            "ma5": sl(ma5), "ma20": sl(ma20),
            "vol_ratio": round(float(vols[-1] / vol_ma5[-1]), 2) if vol_ma5 is not None and vol_ma5[-1] > 0 else 1.0,
            "chg5d": round(float((closes[-1]/closes[-6]-1)*100), 2) if len(closes) >= 6 else 0,
        }

    async def _llm_batch_interpret(self, all_indicators: Dict[str, Any]) -> Dict[str, AgentSignal]:
        system_prompt = (
            "你是专业A股技术分析师。对每只股票的技术指标进行综合分析，"
            "给出 bullish/bearish/neutral 信号、置信度(0-100)和简短中文推理(≤80字)。"
            "必须对所有给定的股票代码都返回信号。"
        )
        prompt = (
            f"请分析以下股票的技术指标并批量返回信号：\n\n"
            f"{json.dumps(all_indicators, ensure_ascii=False, indent=2)}"
        )

        result = await acall_llm(
            prompt=prompt,
            pydantic_model=BatchSignals,
            system_prompt=system_prompt,
            max_tokens=1500,
            default_factory=lambda: BatchSignals(signals={
                code: AgentSignal(signal="neutral", confidence=30, reasoning="技术分析暂时不可用")
                for code in all_indicators
            }),
        )
        return result.signals
