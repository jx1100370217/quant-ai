from typing import Dict, List, Any, Tuple
from .base import BaseAgent
import numpy as np
from datetime import datetime

class PortfolioManager(BaseAgent):
    """投资组合管理Agent - 综合所有Agent意见，生成最终的调仓建议"""
    
    def __init__(self):
        super().__init__(
            name="PortfolioManager",
            description="综合所有Agent意见，生成最终的调仓建议"
        )
        
        # Agent权重配置
        self.agent_weights = {
            "MarketAnalyst": 0.25,      # 市场分析权重25%
            "TechnicalAnalyst": 0.20,   # 技术分析权重20%
            "FundamentalAnalyst": 0.20, # 基本面分析权重20%
            "SentimentAnalyst": 0.15,   # 情绪分析权重15%
            "RiskManager": 0.20         # 风险管理权重20%（风险优先）
        }
        
        # 决策阈值
        self.buy_threshold = 0.6    # 买入阈值
        self.sell_threshold = -0.4  # 卖出阈值
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """综合分析所有Agent意见"""
        
        # 获取所有Agent的分析结果
        agent_results = data.get("agent_results", {})
        
        # 获取当前持仓
        current_portfolio = data.get("portfolio", {})
        
        # 综合信号分析
        signal_analysis = self._analyze_agent_signals(agent_results)
        
        # 一致性分析
        consensus_analysis = self._analyze_consensus(agent_results)
        
        # 组合优化建议
        optimization_recommendations = self._generate_optimization_recommendations(
            signal_analysis, current_portfolio, agent_results
        )
        
        # 执行计划生成
        execution_plan = self._generate_execution_plan(
            optimization_recommendations, current_portfolio
        )
        
        # 决策置信度评估
        decision_confidence = self._evaluate_decision_confidence(
            signal_analysis, consensus_analysis
        )
        
        # 风险调整
        risk_adjusted_plan = self._apply_risk_adjustments(
            execution_plan, agent_results.get("RiskManager", {})
        )
        
        return {
            "signal_analysis": signal_analysis,
            "consensus_analysis": consensus_analysis,
            "optimization_recommendations": optimization_recommendations,
            "execution_plan": execution_plan,
            "risk_adjusted_plan": risk_adjusted_plan,
            "decision_confidence": decision_confidence,
            "final_decision": self._make_final_decision(
                risk_adjusted_plan, decision_confidence
            ),
            "analysis_summary": self._generate_analysis_summary(agent_results)
        }
        
    def _analyze_agent_signals(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析各Agent信号"""
        signals = []
        weighted_score = 0
        agent_opinions = {}
        
        for agent_name, result in agent_results.items():
            if agent_name in self.agent_weights and "signal" in result:
                signal_info = result["signal"]
                signal_type = signal_info.get("signal", "HOLD")
                confidence = signal_info.get("confidence", 0.5)
                reason = signal_info.get("reason", "")
                
                # 信号数值化
                signal_value = 0
                if signal_type == "BUY":
                    signal_value = confidence
                elif signal_type == "SELL":
                    signal_value = -confidence
                # HOLD = 0
                
                weight = self.agent_weights[agent_name]
                weighted_score += signal_value * weight
                
                agent_opinions[agent_name] = {
                    "signal": signal_type,
                    "confidence": confidence,
                    "reason": reason,
                    "weight": weight,
                    "weighted_contribution": signal_value * weight
                }
                
                signals.append({
                    "agent": agent_name,
                    "signal": signal_type,
                    "confidence": confidence,
                    "weight": weight
                })
                
        # 信号统计
        buy_signals = len([s for s in signals if s["signal"] == "BUY"])
        sell_signals = len([s for s in signals if s["signal"] == "SELL"])
        hold_signals = len([s for s in signals if s["signal"] == "HOLD"])
        
        # 加权平均置信度
        total_confidence = sum(s["confidence"] * s["weight"] for s in signals)
        total_weight = sum(s["weight"] for s in signals)
        avg_confidence = total_confidence / total_weight if total_weight > 0 else 0
        
        return {
            "weighted_score": weighted_score,
            "avg_confidence": avg_confidence,
            "signal_distribution": {
                "buy": buy_signals,
                "sell": sell_signals,
                "hold": hold_signals
            },
            "agent_opinions": agent_opinions,
            "total_agents": len(signals)
        }
        
    def _analyze_consensus(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析Agent一致性"""
        signals = []
        confidences = []
        
        for agent_name, result in agent_results.items():
            if "signal" in result:
                signal_info = result["signal"]
                signals.append(signal_info.get("signal", "HOLD"))
                confidences.append(signal_info.get("confidence", 0.5))
                
        if not signals:
            return {"consensus_level": "无数据", "agreement_ratio": 0}
            
        # 计算一致性
        signal_counts = {}
        for signal in signals:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
            
        # 最多的信号
        dominant_signal = max(signal_counts.items(), key=lambda x: x[1])
        agreement_ratio = dominant_signal[1] / len(signals)
        
        # 一致性等级
        if agreement_ratio >= 0.8:
            consensus_level = "高度一致"
        elif agreement_ratio >= 0.6:
            consensus_level = "基本一致"
        elif agreement_ratio >= 0.4:
            consensus_level = "部分一致"
        else:
            consensus_level = "分歧较大"
            
        # 置信度一致性
        confidence_std = np.std(confidences) if len(confidences) > 1 else 0
        confidence_consistency = "高" if confidence_std < 0.2 else "中" if confidence_std < 0.4 else "低"
        
        return {
            "consensus_level": consensus_level,
            "agreement_ratio": agreement_ratio,
            "dominant_signal": dominant_signal[0],
            "signal_distribution": signal_counts,
            "confidence_consistency": confidence_consistency,
            "avg_confidence": np.mean(confidences)
        }
        
    def _generate_optimization_recommendations(self, signal_analysis: Dict, 
                                             current_portfolio: Dict, 
                                             agent_results: Dict) -> Dict[str, Any]:
        """生成组合优化建议"""
        weighted_score = signal_analysis.get("weighted_score", 0)
        
        recommendations = {
            "action_type": "HOLD",
            "urgency": "低",
            "target_positions": [],
            "cash_allocation": 0.2,  # 默认保留20%现金
            "rebalance_needed": False
        }
        
        # 根据综合信号确定主要动作
        if weighted_score > self.buy_threshold:
            recommendations["action_type"] = "BUY"
            recommendations["urgency"] = "高" if weighted_score > 0.8 else "中"
            recommendations["cash_allocation"] = 0.1  # 加仓时减少现金比例
        elif weighted_score < self.sell_threshold:
            recommendations["action_type"] = "SELL"
            recommendations["urgency"] = "高" if weighted_score < -0.6 else "中"
            recommendations["cash_allocation"] = 0.3  # 减仓时增加现金比例
        else:
            recommendations["action_type"] = "HOLD"
            recommendations["urgency"] = "低"
            
        # 获取目标股票建议
        target_stocks = self._identify_target_stocks(agent_results)
        
        # 生成具体持仓建议
        if recommendations["action_type"] == "BUY":
            recommendations["target_positions"] = self._generate_buy_targets(
                target_stocks, current_portfolio, weighted_score
            )
        elif recommendations["action_type"] == "SELL":
            recommendations["target_positions"] = self._generate_sell_targets(
                current_portfolio, weighted_score
            )
            
        # 检查是否需要再平衡
        recommendations["rebalance_needed"] = self._check_rebalance_needed(
            current_portfolio, recommendations
        )
        
        return recommendations
        
    def _identify_target_stocks(self, agent_results: Dict) -> List[str]:
        """识别目标股票"""
        # 这里应该根据各Agent的分析结果识别推荐股票
        # 简化实现，返回一些示例股票代码
        target_stocks = [
            "000001",  # 平安银行
            "000002",  # 万科A
            "600036",  # 招商银行
            "000858",  # 五粮液
            "600519",  # 贵州茅台
        ]
        
        # 根据基本面分析结果筛选
        fundamental_result = agent_results.get("FundamentalAnalyst", {})
        if "stock_fundamentals" in fundamental_result:
            fundamentals = fundamental_result["stock_fundamentals"]
            good_stocks = []
            for code, analysis in fundamentals.items():
                if "valuation_analysis" in analysis:
                    valuation = analysis["valuation_analysis"]
                    if valuation.get("valuation_score", 0) > 0.2:
                        good_stocks.append(code)
            if good_stocks:
                target_stocks = good_stocks[:5]  # 取前5只
                
        return target_stocks
        
    def _generate_buy_targets(self, target_stocks: List[str], 
                            current_portfolio: Dict, 
                            signal_strength: float) -> List[Dict]:
        """生成买入目标"""
        targets = []
        available_cash_ratio = 1.0 - 0.1  # 保留10%现金
        
        # 根据信号强度调整仓位大小
        base_position_size = min(0.15 * signal_strength, 0.2)  # 最大单仓位20%
        
        current_positions = {pos.get("symbol"): pos 
                           for pos in current_portfolio.get("positions", [])}
        
        for i, stock in enumerate(target_stocks[:5]):  # 最多5只股票
            current_position = current_positions.get(stock, {})
            current_ratio = current_position.get("ratio", 0)
            
            # 如果已持有，考虑加仓
            if current_ratio > 0:
                if current_ratio < base_position_size:
                    target_ratio = min(base_position_size, current_ratio + 0.05)
                    targets.append({
                        "symbol": stock,
                        "action": "增持",
                        "current_ratio": current_ratio,
                        "target_ratio": target_ratio,
                        "priority": i + 1
                    })
            else:
                # 新建仓
                targets.append({
                    "symbol": stock,
                    "action": "建仓",
                    "current_ratio": 0,
                    "target_ratio": base_position_size,
                    "priority": i + 1
                })
                
        return targets
        
    def _generate_sell_targets(self, current_portfolio: Dict, 
                              signal_strength: float) -> List[Dict]:
        """生成卖出目标"""
        targets = []
        current_positions = current_portfolio.get("positions", [])
        
        # 按持仓比例排序，优先减持大仓位
        sorted_positions = sorted(current_positions, 
                                key=lambda x: x.get("market_value", 0), 
                                reverse=True)
        
        # 减仓比例与信号强度成正比
        reduction_ratio = min(abs(signal_strength), 0.8)  # 最多减仓80%
        
        for position in sorted_positions:
            symbol = position.get("symbol")
            current_ratio = position.get("market_value", 0) / current_portfolio.get("total_value", 1)
            
            # 计算目标仓位
            target_ratio = current_ratio * (1 - reduction_ratio)
            
            if target_ratio < 0.02:  # 小于2%则清仓
                targets.append({
                    "symbol": symbol,
                    "action": "清仓",
                    "current_ratio": current_ratio,
                    "target_ratio": 0,
                    "reduction": current_ratio
                })
            else:
                targets.append({
                    "symbol": symbol,
                    "action": "减持",
                    "current_ratio": current_ratio,
                    "target_ratio": target_ratio,
                    "reduction": current_ratio - target_ratio
                })
                
        return targets
        
    def _check_rebalance_needed(self, current_portfolio: Dict, 
                               recommendations: Dict) -> bool:
        """检查是否需要再平衡"""
        positions = current_portfolio.get("positions", [])
        total_value = current_portfolio.get("total_value", 1)
        
        # 检查仓位偏离
        for position in positions:
            current_ratio = position.get("market_value", 0) / total_value
            if current_ratio > 0.25:  # 单只股票超过25%需要再平衡
                return True
                
        # 检查现金比例
        cash_ratio = current_portfolio.get("cash", 0) / total_value
        target_cash = recommendations.get("cash_allocation", 0.2)
        
        if abs(cash_ratio - target_cash) > 0.1:  # 现金偏离超过10%
            return True
            
        return False
        
    def _generate_execution_plan(self, recommendations: Dict, 
                                current_portfolio: Dict) -> Dict[str, Any]:
        """生成执行计划"""
        plan = {
            "execution_order": [],
            "estimated_trades": 0,
            "estimated_cost": 0,
            "execution_priority": recommendations.get("urgency", "低"),
            "batch_execution": True
        }
        
        target_positions = recommendations.get("target_positions", [])
        
        # 按优先级排序执行
        sorted_targets = sorted(target_positions, 
                               key=lambda x: x.get("priority", 99))
        
        for i, target in enumerate(sorted_targets):
            symbol = target.get("symbol")
            action = target.get("action")
            current_ratio = target.get("current_ratio", 0)
            target_ratio = target.get("target_ratio", 0)
            
            if action in ["建仓", "增持"]:
                plan["execution_order"].append({
                    "step": i + 1,
                    "symbol": symbol,
                    "action": "BUY",
                    "ratio_change": target_ratio - current_ratio,
                    "urgency": "高" if i < 2 else "中"
                })
            elif action in ["减持", "清仓"]:
                plan["execution_order"].append({
                    "step": i + 1,
                    "symbol": symbol,
                    "action": "SELL",
                    "ratio_change": current_ratio - target_ratio,
                    "urgency": "高" if action == "清仓" else "中"
                })
                
        plan["estimated_trades"] = len(plan["execution_order"])
        plan["estimated_cost"] = plan["estimated_trades"] * 0.0015  # 估算交易成本0.15%
        
        return plan
        
    def _apply_risk_adjustments(self, execution_plan: Dict, 
                               risk_analysis: Dict) -> Dict[str, Any]:
        """应用风险调整"""
        if not risk_analysis or "overall_risk" not in risk_analysis:
            return execution_plan
            
        risk_level = risk_analysis["overall_risk"].get("risk_level", "中")
        risk_alerts = risk_analysis.get("risk_alerts", [])
        
        adjusted_plan = execution_plan.copy()
        adjustments_made = []
        
        # 高风险情况下的调整
        if risk_level in ["高", "极高"]:
            # 降低仓位目标
            for order in adjusted_plan.get("execution_order", []):
                if order["action"] == "BUY":
                    original_change = order["ratio_change"]
                    order["ratio_change"] = original_change * 0.5  # 减半
                    adjustments_made.append(f"降低{order['symbol']}买入仓位")
                    
            # 提高执行优先级
            adjusted_plan["execution_priority"] = "高"
            
        # 有风险预警时的调整
        if risk_alerts:
            for alert in risk_alerts:
                if "回撤" in alert:
                    adjusted_plan["batch_execution"] = False  # 分批执行
                    adjustments_made.append("启用分批执行")
                elif "仓位过重" in alert:
                    # 限制单只股票仓位
                    for order in adjusted_plan.get("execution_order", []):
                        if order["ratio_change"] > 0.15:
                            order["ratio_change"] = 0.15
                            adjustments_made.append(f"限制{order['symbol']}仓位上限")
                            
        adjusted_plan["risk_adjustments"] = adjustments_made
        
        return adjusted_plan
        
    def _evaluate_decision_confidence(self, signal_analysis: Dict, 
                                    consensus_analysis: Dict) -> Dict[str, Any]:
        """评估决策置信度"""
        # 基础置信度来自信号分析
        base_confidence = signal_analysis.get("avg_confidence", 0.5)
        
        # 一致性加成
        consensus_bonus = 0
        agreement_ratio = consensus_analysis.get("agreement_ratio", 0)
        if agreement_ratio >= 0.8:
            consensus_bonus = 0.2
        elif agreement_ratio >= 0.6:
            consensus_bonus = 0.1
            
        # 信号强度影响
        weighted_score = abs(signal_analysis.get("weighted_score", 0))
        strength_bonus = min(weighted_score * 0.2, 0.3)
        
        # 综合置信度
        total_confidence = min(base_confidence + consensus_bonus + strength_bonus, 1.0)
        
        # 置信度等级
        if total_confidence >= 0.8:
            confidence_level = "极高"
        elif total_confidence >= 0.6:
            confidence_level = "高"
        elif total_confidence >= 0.4:
            confidence_level = "中等"
        else:
            confidence_level = "低"
            
        return {
            "total_confidence": total_confidence,
            "confidence_level": confidence_level,
            "base_confidence": base_confidence,
            "consensus_bonus": consensus_bonus,
            "strength_bonus": strength_bonus,
            "decision_quality": "可靠" if total_confidence >= 0.6 else "需谨慎"
        }
        
    def _make_final_decision(self, risk_adjusted_plan: Dict, 
                           decision_confidence: Dict) -> Dict[str, Any]:
        """做出最终决策"""
        confidence = decision_confidence.get("total_confidence", 0.5)
        execution_order = risk_adjusted_plan.get("execution_order", [])
        
        # 根据置信度决定是否执行
        if confidence < 0.3:
            decision_type = "暂停交易"
            execution_approval = False
            reason = "决策置信度过低，建议观望"
        elif confidence < 0.5:
            decision_type = "谨慎执行"
            execution_approval = True
            reason = "决策置信度一般，小仓位试探"
        elif confidence >= 0.7:
            decision_type = "积极执行"
            execution_approval = True
            reason = "决策置信度高，按计划执行"
        else:
            decision_type = "稳健执行"
            execution_approval = True
            reason = "决策置信度中等，稳健执行"
            
        # 生成最终指令
        final_instructions = []
        if execution_approval and execution_order:
            for order in execution_order[:3]:  # 最多执行前3个指令
                final_instructions.append({
                    "symbol": order.get("symbol"),
                    "action": order.get("action"),
                    "ratio": order.get("ratio_change"),
                    "urgency": order.get("urgency", "中")
                })
                
        return {
            "decision_type": decision_type,
            "execution_approval": execution_approval,
            "confidence": confidence,
            "reason": reason,
            "final_instructions": final_instructions,
            "max_instructions": len(final_instructions),
            "decision_timestamp": datetime.now().isoformat()
        }
        
    def _generate_analysis_summary(self, agent_results: Dict) -> Dict[str, str]:
        """生成分析摘要"""
        summary = {}
        
        for agent_name, result in agent_results.items():
            if "signal" in result:
                signal_info = result["signal"]
                signal = signal_info.get("signal", "HOLD")
                reason = signal_info.get("reason", "")
                confidence = signal_info.get("confidence", 0.5)
                
                summary[agent_name] = f"{signal} (置信度{confidence:.1%}) - {reason}"
            else:
                summary[agent_name] = "分析失败"
                
        return summary
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终交易信号"""
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "组合分析失败"
            }
            
        final_decision = analysis.get("final_decision", {})
        signal_analysis = analysis.get("signal_analysis", {})
        
        decision_type = final_decision.get("decision_type", "暂停交易")
        execution_approval = final_decision.get("execution_approval", False)
        confidence = final_decision.get("confidence", 0.5)
        reason = final_decision.get("reason", "")
        
        # 转换为标准信号格式
        if not execution_approval:
            signal = "HOLD"
        else:
            weighted_score = signal_analysis.get("weighted_score", 0)
            if weighted_score > 0.3:
                signal = "BUY"
            elif weighted_score < -0.3:
                signal = "SELL"
            else:
                signal = "HOLD"
                
        return {
            "signal": signal,
            "confidence": confidence,
            "reason": f"{decision_type} - {reason}",
            "decision_type": decision_type,
            "weighted_score": signal_analysis.get("weighted_score", 0),
            "final_instructions": final_decision.get("final_instructions", [])
        }