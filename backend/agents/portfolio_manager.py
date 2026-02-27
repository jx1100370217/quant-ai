"""
Portfolio Manager Agent - 收集所有 Agent 信号，LLM 做最终决策
参考 ai-hedge-fund 的 portfolio_manager.py
"""
from typing import Dict, Any
import json
import logging

from .base import BaseAgent
from models.agent_models import AgentSignal, PortfolioDecision, PortfolioOutput
from llm.client import acall_llm

logger = logging.getLogger(__name__)


PORTFOLIO_SYSTEM_PROMPT = """你是一位专业的A股投资组合管理师。你的职责是：

1. 综合所有分析师（技术分析、基本面分析、情绪分析、风险管理、投资大师）的信号
2. 权衡各方意见，做出最终的投资决策（buy/sell/hold）
3. 决定每只股票的交易数量（以手为单位，1手=100股）
4. 给出决策的置信度和推理

决策原则：
- 风险优先：风险管理师的预警必须高度重视，高风险时降低仓位
- 信号一致性：多个分析师意见一致时，决策更有信心
- 仓位管理：单只股票仓位不超过总资金的20%，遵守风险限制
- 分散投资：避免过度集中
- 保留现金：至少保留10%现金

决策格式要求：
- action: "buy"（买入）/ "sell"（卖出）/ "hold"（持有）
- quantity: 交易股数（必须是100的倍数，hold时为0）
- confidence: 0-100
- reasoning: 简短推理说明（中文，150字以内）"""


class PortfolioManager(BaseAgent):
    """投资组合管理 Agent：汇总所有信号，LLM 做最终决策"""
    
    def __init__(self):
        super().__init__(
            name="PortfolioManager",
            description="综合所有Agent意见，生成最终的调仓决策"
        )
        
    async def make_decision(
        self,
        agent_signals: Dict[str, Dict[str, AgentSignal]],
        portfolio: Dict[str, Any] = None,
        risk_limits: Dict[str, Any] = None,
    ) -> Dict[str, PortfolioDecision]:
        """
        汇总所有 Agent 信号，由 LLM 做最终决策。
        
        Args:
            agent_signals: {agent_name: {stock_code: AgentSignal}}
            portfolio: 当前持仓信息
            risk_limits: 风险管理的仓位限制
            
        Returns:
            {stock_code: PortfolioDecision}
        """
        # 收集所有涉及的股票代码
        all_stocks = set()
        for signals in agent_signals.values():
            all_stocks.update(signals.keys())
        
        if not all_stocks:
            return {}
        
        # 为每只股票整理信号汇总
        stock_summaries = {}
        for stock_code in all_stocks:
            summary = {}
            for agent_name, signals in agent_signals.items():
                if stock_code in signals:
                    sig = signals[stock_code]
                    if isinstance(sig, AgentSignal):
                        summary[agent_name] = {
                            "signal": sig.signal,
                            "confidence": sig.confidence,
                            "reasoning": sig.reasoning,
                        }
                    elif isinstance(sig, dict):
                        summary[agent_name] = sig
            
            # 加入风险限制
            if risk_limits and stock_code in risk_limits:
                summary["risk_limits"] = risk_limits[stock_code]
            
            stock_summaries[stock_code] = summary
        
        # 构建 LLM prompt
        portfolio_info = json.dumps(portfolio or {"cash": 1000000, "positions": []}, 
                                     ensure_ascii=False, indent=2)
        signals_info = json.dumps(stock_summaries, ensure_ascii=False, indent=2)
        
        prompt = (
            f"当前持仓情况:\n{portfolio_info}\n\n"
            f"各分析师对每只股票的信号汇总:\n{signals_info}\n\n"
            "请为每只股票做出最终投资决策。"
        )
        
        try:
            result = await acall_llm(
                prompt=prompt,
                pydantic_model=PortfolioOutput,
                system_prompt=PORTFOLIO_SYSTEM_PROMPT,
                default_factory=lambda: PortfolioOutput(
                    decisions={
                        code: PortfolioDecision(
                            action="hold", quantity=0, confidence=30,
                            reasoning="LLM 决策超时，默认持有"
                        )
                        for code in all_stocks
                    }
                ),
            )
            return result.decisions
            
        except Exception as e:
            logger.error(f"Portfolio decision failed: {e}")
            return {
                code: PortfolioDecision(
                    action="hold", quantity=0, confidence=0,
                    reasoning=f"决策失败: {e}"
                )
                for code in all_stocks
            }
    
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, AgentSignal]:
        """
        兼容 BaseAgent 接口。
        实际决策通过 make_decision() 方法调用。
        """
        # PortfolioManager 的主要入口是 make_decision，
        # 这里提供一个简化的 analyze 方法供 AgentManager 调用
        return {}
