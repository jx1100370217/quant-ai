"""
风险管理 Agent - 纯规则计算风险指标，输出仓位限制（不用 LLM）
参考 ai-hedge-fund 的 risk_manager.py
"""
from typing import Dict, Any
import logging
import numpy as np
import pandas as pd

from .base import BaseAgent
from models.agent_models import AgentSignal

logger = logging.getLogger(__name__)


class RiskManager(BaseAgent):
    """风险管理 Agent：纯规则计算波动率、相关性等风险指标，输出仓位限制"""
    
    def __init__(self):
        super().__init__(
            name="RiskManager",
            description="评估持仓风险、波动率、相关性，给出仓位控制建议"
        )
        self.max_single_position = 0.20
        self.stop_loss_threshold = 0.08
        self.max_drawdown_limit = 0.15
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        """
        风险分析。对每只目标股票，计算波动率相关风险指标，
        输出 AgentSignal（bearish = 高风险，bullish = 低风险可加仓）。
        同时在 data["risk_limits"] 中写入每只股票的仓位限制。
        """
        target_stocks = data.get("target_stocks", ["000001"])
        portfolio = data.get("portfolio", {})
        results = {}
        risk_limits = {}
        
        for stock_code in target_stocks:
            try:
                vol_data = await self._calculate_volatility(stock_code)
                
                # 波动率调整的仓位限制
                ann_vol = vol_data.get("annualized_volatility", 0.25)
                limit_pct = self._volatility_adjusted_limit(ann_vol)
                
                risk_limits[stock_code] = {
                    "position_limit_pct": limit_pct,
                    "annualized_volatility": ann_vol,
                    "daily_volatility": vol_data.get("daily_volatility", 0.02),
                }
                
                # 风险信号
                if ann_vol > 0.50:
                    signal = "bearish"
                    confidence = min(int(ann_vol * 100), 90)
                    reasoning = f"波动率极高({ann_vol:.1%})，建议大幅降低仓位，仓位上限{limit_pct:.1%}"
                elif ann_vol > 0.30:
                    signal = "bearish"
                    confidence = int(50 + (ann_vol - 0.30) * 200)
                    reasoning = f"波动率偏高({ann_vol:.1%})，建议控制仓位，上限{limit_pct:.1%}"
                elif ann_vol > 0.15:
                    signal = "neutral"
                    confidence = 50
                    reasoning = f"波动率适中({ann_vol:.1%})，仓位上限{limit_pct:.1%}"
                else:
                    signal = "bullish"
                    confidence = int(60 + (0.15 - ann_vol) * 200)
                    reasoning = f"波动率较低({ann_vol:.1%})，风险可控，仓位上限{limit_pct:.1%}"
                
                results[stock_code] = AgentSignal(
                    signal=signal,
                    confidence=min(confidence, 95),
                    reasoning=reasoning,
                )
                
            except Exception as e:
                logger.error(f"Risk analysis failed for {stock_code}: {e}")
                risk_limits[stock_code] = {"position_limit_pct": 0.10}
                results[stock_code] = AgentSignal(
                    signal="bearish", confidence=50,
                    reasoning=f"风险数据获取失败，保守限仓10%: {e}"
                )
        
        # 将风险限制写入 data，供 PortfolioManager 使用
        data["risk_limits"] = risk_limits
        
        return results
        
    async def _calculate_volatility(self, stock_code: str) -> Dict[str, float]:
        """计算波动率指标"""
        from data.eastmoney import eastmoney_api
        
        klines = await eastmoney_api.get_kline_data(stock_code, "101", 60)
        
        if not klines or len(klines) < 10:
            return {
                "daily_volatility": 0.03,
                "annualized_volatility": 0.03 * np.sqrt(252),
            }
        
        closes = np.array([k["close"] for k in klines])
        returns = np.diff(closes) / closes[:-1]
        
        daily_vol = float(np.std(returns))
        ann_vol = daily_vol * np.sqrt(252)
        
        return {
            "daily_volatility": daily_vol,
            "annualized_volatility": ann_vol,
            "data_points": len(returns),
        }
    
    def _volatility_adjusted_limit(self, annualized_volatility: float) -> float:
        """根据波动率计算仓位上限百分比"""
        base = 0.20
        
        if annualized_volatility < 0.15:
            return base * 1.25  # 25%
        elif annualized_volatility < 0.30:
            factor = 1.0 - (annualized_volatility - 0.15) * 0.5
            return base * max(factor, 0.50)
        elif annualized_volatility < 0.50:
            factor = 0.75 - (annualized_volatility - 0.30) * 0.5
            return base * max(factor, 0.25)
        else:
            return base * 0.25  # 5%
