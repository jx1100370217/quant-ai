from typing import Dict, List, Any
from .base import BaseAgent
import numpy as np
from datetime import datetime, timedelta

class RiskManager(BaseAgent):
    """风险管理Agent - 评估持仓风险、最大回撤、仓位控制建议"""
    
    def __init__(self):
        super().__init__(
            name="RiskManager",
            description="评估持仓风险、最大回撤、仓位控制建议"
        )
        self.max_single_position = 0.2  # 单只股票最大仓位20%
        self.stop_loss_threshold = 0.08  # 止损线8%
        self.max_drawdown_limit = 0.15   # 最大回撤限制15%
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """风险分析"""
        
        # 获取当前持仓
        portfolio = data.get("portfolio", {})
        
        # 获取历史净值数据
        nav_history = data.get("nav_history", [])
        
        # 获取市场数据
        market_data = data.get("market_data", {})
        
        # 仓位风险分析
        position_risk = self._analyze_position_risk(portfolio)
        
        # 集中度风险分析
        concentration_risk = self._analyze_concentration_risk(portfolio)
        
        # 回撤风险分析
        drawdown_analysis = self._analyze_drawdown_risk(nav_history)
        
        # 相关性风险分析
        correlation_risk = await self._analyze_correlation_risk(portfolio)
        
        # VaR风险度量
        var_analysis = self._calculate_var(nav_history, portfolio)
        
        # 流动性风险分析
        liquidity_risk = self._analyze_liquidity_risk(portfolio)
        
        # 市场风险分析
        market_risk = self._analyze_market_risk(market_data, portfolio)
        
        # 综合风险评级
        overall_risk = self._calculate_overall_risk(
            position_risk, concentration_risk, drawdown_analysis, 
            correlation_risk, var_analysis, liquidity_risk, market_risk
        )
        
        # 风险预警
        risk_alerts = self._generate_risk_alerts(overall_risk, position_risk, drawdown_analysis)
        
        # 仓位建议
        position_recommendations = self._generate_position_recommendations(overall_risk, portfolio)
        
        return {
            "position_risk": position_risk,
            "concentration_risk": concentration_risk,
            "drawdown_analysis": drawdown_analysis,
            "correlation_risk": correlation_risk,
            "var_analysis": var_analysis,
            "liquidity_risk": liquidity_risk,
            "market_risk": market_risk,
            "overall_risk": overall_risk,
            "risk_alerts": risk_alerts,
            "position_recommendations": position_recommendations,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    def _analyze_position_risk(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """仓位风险分析"""
        if not portfolio or not portfolio.get("positions"):
            return {
                "risk_level": "低",
                "cash_ratio": 1.0,
                "position_count": 0,
                "largest_position": 0,
                "position_sizes": []
            }
            
        positions = portfolio["positions"]
        total_value = portfolio.get("total_value", 1000000)
        cash = portfolio.get("cash", 0)
        
        # 计算各个仓位占比
        position_sizes = []
        for position in positions:
            position_value = position.get("market_value", 0)
            position_ratio = position_value / total_value if total_value > 0 else 0
            position_sizes.append({
                "symbol": position.get("symbol"),
                "ratio": position_ratio,
                "value": position_value
            })
            
        # 最大单一仓位
        largest_position = max([p["ratio"] for p in position_sizes], default=0)
        
        # 现金比例
        cash_ratio = cash / total_value if total_value > 0 else 0
        
        # 风险等级判断
        if largest_position > 0.3:
            risk_level = "高"
        elif largest_position > 0.2:
            risk_level = "中"
        else:
            risk_level = "低"
            
        # 风险因子
        risk_factors = []
        if largest_position > self.max_single_position:
            risk_factors.append(f"单只股票仓位过重({largest_position:.1%})")
        if cash_ratio < 0.1:
            risk_factors.append("现金储备不足")
        if len(positions) < 3:
            risk_factors.append("持股过少，分散不够")
            
        return {
            "risk_level": risk_level,
            "cash_ratio": cash_ratio,
            "position_count": len(positions),
            "largest_position": largest_position,
            "position_sizes": position_sizes,
            "risk_factors": risk_factors
        }
        
    def _analyze_concentration_risk(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """集中度风险分析"""
        if not portfolio or not portfolio.get("positions"):
            return {"concentration_level": "无", "herfindahl_index": 0}
            
        positions = portfolio["positions"]
        total_value = portfolio.get("total_value", 1)
        
        # 计算赫芬达尔指数（HHI）
        position_ratios = []
        for position in positions:
            ratio = position.get("market_value", 0) / total_value
            position_ratios.append(ratio)
            
        hhi = sum(ratio ** 2 for ratio in position_ratios)
        
        # 集中度判断
        if hhi > 0.25:  # 相当于4只股票平均分配
            concentration_level = "高集中"
        elif hhi > 0.15:
            concentration_level = "中等集中"
        else:
            concentration_level = "低集中"
            
        # Top 3持仓占比
        top3_ratio = sum(sorted(position_ratios, reverse=True)[:3])
        
        return {
            "concentration_level": concentration_level,
            "herfindahl_index": hhi,
            "top3_ratio": top3_ratio,
            "diversification_score": 1 - hhi  # 分散化得分
        }
        
    def _analyze_drawdown_risk(self, nav_history: List[Dict]) -> Dict[str, Any]:
        """回撤风险分析"""
        if not nav_history or len(nav_history) < 2:
            return {
                "current_drawdown": 0,
                "max_drawdown": 0,
                "drawdown_duration": 0,
                "risk_level": "低"
            }
            
        # 计算净值序列
        nav_values = [record.get("nav", 1.0) for record in nav_history]
        
        # 计算回撤
        peak = nav_values[0]
        max_drawdown = 0
        current_drawdown = 0
        drawdown_duration = 0
        current_duration = 0
        
        for nav in nav_values:
            if nav > peak:
                peak = nav
                current_duration = 0
            else:
                current_duration += 1
                drawdown = (peak - nav) / peak
                current_drawdown = drawdown if nav == nav_values[-1] else 0
                max_drawdown = max(max_drawdown, drawdown)
                drawdown_duration = max(drawdown_duration, current_duration)
                
        # 风险等级
        if max_drawdown > 0.2:
            risk_level = "高"
        elif max_drawdown > 0.1:
            risk_level = "中"
        else:
            risk_level = "低"
            
        # 回撤预警
        drawdown_alerts = []
        if current_drawdown > self.max_drawdown_limit:
            drawdown_alerts.append("当前回撤超过限制")
        if max_drawdown > 0.25:
            drawdown_alerts.append("历史最大回撤过大")
        if drawdown_duration > 30:
            drawdown_alerts.append("回撤持续时间过长")
            
        return {
            "current_drawdown": current_drawdown,
            "max_drawdown": max_drawdown,
            "drawdown_duration": drawdown_duration,
            "risk_level": risk_level,
            "alerts": drawdown_alerts
        }
        
    async def _analyze_correlation_risk(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """相关性风险分析"""
        if not portfolio or not portfolio.get("positions"):
            return {"correlation_risk": "低", "avg_correlation": 0}
            
        positions = portfolio["positions"]
        stock_codes = [pos.get("symbol") for pos in positions if pos.get("symbol")]
        
        if len(stock_codes) < 2:
            return {"correlation_risk": "无", "avg_correlation": 0}
            
        try:
            # 获取股票历史价格数据计算相关性
            from data.eastmoney import eastmoney_api
            
            price_data = {}
            for code in stock_codes[:10]:  # 最多分析10只股票
                klines = await eastmoney_api.get_kline_data(code, "101", 30)
                if klines:
                    price_data[code] = [k["close"] for k in klines]
                    
            if len(price_data) < 2:
                return {"correlation_risk": "无法计算", "avg_correlation": 0}
                
            # 计算相关系数矩阵
            correlations = []
            codes = list(price_data.keys())
            
            for i in range(len(codes)):
                for j in range(i + 1, len(codes)):
                    prices1 = price_data[codes[i]]
                    prices2 = price_data[codes[j]]
                    
                    # 计算收益率
                    returns1 = [(prices1[k] - prices1[k-1]) / prices1[k-1] 
                               for k in range(1, len(prices1))]
                    returns2 = [(prices2[k] - prices2[k-1]) / prices2[k-1] 
                               for k in range(1, len(prices2))]
                    
                    # 确保长度一致
                    min_len = min(len(returns1), len(returns2))
                    returns1 = returns1[:min_len]
                    returns2 = returns2[:min_len]
                    
                    if min_len > 5:
                        correlation = np.corrcoef(returns1, returns2)[0, 1]
                        if not np.isnan(correlation):
                            correlations.append(correlation)
                            
            avg_correlation = np.mean(correlations) if correlations else 0
            
            # 相关性风险评级
            if avg_correlation > 0.7:
                correlation_risk = "高"
            elif avg_correlation > 0.5:
                correlation_risk = "中"
            else:
                correlation_risk = "低"
                
            return {
                "correlation_risk": correlation_risk,
                "avg_correlation": avg_correlation,
                "correlation_count": len(correlations)
            }
            
        except Exception as e:
            return {"correlation_risk": "计算失败", "error": str(e)}
            
    def _calculate_var(self, nav_history: List[Dict], portfolio: Dict[str, Any], confidence: float = 0.95) -> Dict[str, Any]:
        """计算风险价值VaR"""
        if not nav_history or len(nav_history) < 10:
            return {"var_1day": 0, "var_5day": 0, "var_10day": 0}
            
        # 计算收益率序列
        nav_values = [record.get("nav", 1.0) for record in nav_history]
        returns = [(nav_values[i] - nav_values[i-1]) / nav_values[i-1] 
                  for i in range(1, len(nav_values))]
        
        if not returns:
            return {"var_1day": 0, "var_5day": 0, "var_10day": 0}
            
        # 计算分位数
        alpha = 1 - confidence
        var_1day = -np.percentile(returns, alpha * 100)
        
        # 多天VaR（假设独立性）
        volatility = np.std(returns) if len(returns) > 1 else 0
        var_5day = var_1day * np.sqrt(5) if volatility > 0 else 0
        var_10day = var_1day * np.sqrt(10) if volatility > 0 else 0
        
        total_value = portfolio.get("total_value", 1000000)
        
        return {
            "var_1day": var_1day,
            "var_5day": var_5day,
            "var_10day": var_10day,
            "var_1day_amount": var_1day * total_value,
            "var_5day_amount": var_5day * total_value,
            "var_10day_amount": var_10day * total_value,
            "confidence": confidence
        }
        
    def _analyze_liquidity_risk(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """流动性风险分析"""
        if not portfolio or not portfolio.get("positions"):
            return {"liquidity_risk": "低", "illiquid_positions": []}
            
        positions = portfolio["positions"]
        illiquid_positions = []
        liquidity_scores = []
        
        for position in positions:
            # 简单的流动性评估（基于市值和换手率）
            market_cap = position.get("market_cap", 0)
            turnover = position.get("turnover_rate", 0)
            position_value = position.get("market_value", 0)
            
            # 流动性评分
            liquidity_score = 0
            if market_cap > 10000000000:  # 100亿以上大盘股
                liquidity_score += 0.4
            elif market_cap > 5000000000:   # 50-100亿中盘股
                liquidity_score += 0.3
            elif market_cap > 1000000000:   # 10-50亿小盘股
                liquidity_score += 0.2
            else:
                liquidity_score += 0.1
                
            if turnover > 0.05:  # 换手率5%以上
                liquidity_score += 0.3
            elif turnover > 0.02:  # 2-5%
                liquidity_score += 0.2
            elif turnover > 0.01:  # 1-2%
                liquidity_score += 0.1
                
            # 仓位大小影响流动性
            if position_value > 5000000:  # 500万以上大仓位
                liquidity_score -= 0.1
                
            liquidity_scores.append(liquidity_score)
            
            if liquidity_score < 0.3:
                illiquid_positions.append({
                    "symbol": position.get("symbol"),
                    "liquidity_score": liquidity_score,
                    "reason": "市值小或换手率低"
                })
                
        avg_liquidity = np.mean(liquidity_scores) if liquidity_scores else 0.5
        
        if avg_liquidity < 0.3:
            liquidity_risk = "高"
        elif avg_liquidity < 0.5:
            liquidity_risk = "中"
        else:
            liquidity_risk = "低"
            
        return {
            "liquidity_risk": liquidity_risk,
            "avg_liquidity_score": avg_liquidity,
            "illiquid_positions": illiquid_positions,
            "illiquid_count": len(illiquid_positions)
        }
        
    def _analyze_market_risk(self, market_data: Dict[str, Any], portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """市场风险分析"""
        market_risk = "中"
        risk_factors = []
        
        # 大盘走势风险
        indices_data = market_data.get("indices", {})
        if indices_data:
            # 计算大盘平均跌幅
            total_change = 0
            count = 0
            for index_data in indices_data.values():
                if isinstance(index_data, dict) and "current" in index_data:
                    change = index_data["current"].get("change_pct", 0)
                    total_change += change
                    count += 1
                    
            if count > 0:
                avg_change = total_change / count
                if avg_change < -0.03:  # 大盘跌3%以上
                    risk_factors.append("大盘大幅下跌")
                    market_risk = "高"
                elif avg_change < -0.01:
                    risk_factors.append("大盘下跌")
                    
        # 板块风险
        sectors_data = market_data.get("sectors", [])
        if sectors_data:
            declining_sectors = len([s for s in sectors_data if s.get("change_pct", 0) < -0.02])
            total_sectors = len(sectors_data)
            
            if declining_sectors / total_sectors > 0.7:
                risk_factors.append("板块普跌")
                market_risk = "高"
                
        # 资金流向风险
        fund_flow = market_data.get("fund_flow", {})
        if fund_flow:
            main_outflow = fund_flow.get("main_net", 0)
            if main_outflow < -1000000000:  # 主力资金大幅流出
                risk_factors.append("主力资金大幅流出")
                market_risk = "高"
                
        # 情绪风险
        sentiment = market_data.get("sentiment", {})
        if sentiment:
            sentiment_score = sentiment.get("score", 0)
            if sentiment_score < -0.6:
                risk_factors.append("市场情绪极度悲观")
                market_risk = "高"
            elif sentiment_score > 0.8:
                risk_factors.append("市场情绪过热")
                
        return {
            "market_risk": market_risk,
            "risk_factors": risk_factors
        }
        
    def _calculate_overall_risk(self, *risk_components) -> Dict[str, Any]:
        """计算综合风险评级"""
        risk_score = 0
        risk_factors = []
        
        # 各组件权重
        weights = [0.25, 0.15, 0.2, 0.1, 0.1, 0.1, 0.1]  # 仓位、集中度、回撤、相关性、VaR、流动性、市场
        
        component_names = [
            "仓位风险", "集中度风险", "回撤风险", "相关性风险", 
            "VaR风险", "流动性风险", "市场风险"
        ]
        
        for i, component in enumerate(risk_components):
            if isinstance(component, dict):
                level = component.get("risk_level", "中")
                if level == "高":
                    risk_score += weights[i] * 3
                elif level == "中":
                    risk_score += weights[i] * 2
                else:
                    risk_score += weights[i] * 1
                    
                # 收集风险因子
                if "risk_factors" in component:
                    risk_factors.extend(component["risk_factors"])
                elif "alerts" in component:
                    risk_factors.extend(component["alerts"])
                    
        # 标准化风险评分
        normalized_score = risk_score / 3  # 最大值为3
        
        # 综合风险等级
        if normalized_score > 2.5:
            overall_risk = "极高"
        elif normalized_score > 2:
            overall_risk = "高"
        elif normalized_score > 1.5:
            overall_risk = "中"
        else:
            overall_risk = "低"
            
        return {
            "risk_level": overall_risk,
            "risk_score": normalized_score,
            "risk_factors": list(set(risk_factors)),  # 去重
            "risk_components": dict(zip(component_names, risk_components))
        }
        
    def _generate_risk_alerts(self, overall_risk: Dict, position_risk: Dict, drawdown_analysis: Dict) -> List[str]:
        """生成风险预警"""
        alerts = []
        
        # 综合风险预警
        risk_level = overall_risk.get("risk_level", "低")
        if risk_level in ["高", "极高"]:
            alerts.append(f"⚠️ 整体风险等级{risk_level}，建议降低仓位")
            
        # 单一仓位预警
        largest_position = position_risk.get("largest_position", 0)
        if largest_position > self.max_single_position:
            alerts.append(f"⚠️ 单只股票仓位过重({largest_position:.1%})，超过{self.max_single_position:.1%}限制")
            
        # 回撤预警
        current_drawdown = drawdown_analysis.get("current_drawdown", 0)
        if current_drawdown > self.max_drawdown_limit:
            alerts.append(f"⚠️ 当前回撤{current_drawdown:.1%}，超过{self.max_drawdown_limit:.1%}限制")
            
        # 现金预警
        cash_ratio = position_risk.get("cash_ratio", 1.0)
        if cash_ratio < 0.05:
            alerts.append("⚠️ 现金储备不足5%，流动性风险较高")
            
        return alerts
        
    def _generate_position_recommendations(self, overall_risk: Dict, portfolio: Dict) -> Dict[str, Any]:
        """生成仓位建议"""
        risk_level = overall_risk.get("risk_level", "低")
        current_positions = portfolio.get("positions", [])
        total_value = portfolio.get("total_value", 1000000)
        
        recommendations = {
            "action": "保持",
            "target_position_ratio": 0.8,  # 默认80%仓位
            "max_single_position": self.max_single_position,
            "adjustments": []
        }
        
        # 根据风险等级调整建议仓位
        if risk_level == "极高":
            recommendations["action"] = "大幅减仓"
            recommendations["target_position_ratio"] = 0.3
        elif risk_level == "高":
            recommendations["action"] = "减仓"
            recommendations["target_position_ratio"] = 0.5
        elif risk_level == "中":
            recommendations["action"] = "小幅调整"
            recommendations["target_position_ratio"] = 0.7
        elif risk_level == "低":
            recommendations["action"] = "可适当加仓"
            recommendations["target_position_ratio"] = 0.9
            
        # 具体调整建议
        for position in current_positions:
            symbol = position.get("symbol")
            current_ratio = position.get("market_value", 0) / total_value
            
            if current_ratio > self.max_single_position:
                recommendations["adjustments"].append({
                    "symbol": symbol,
                    "action": "减仓",
                    "reason": f"仓位过重({current_ratio:.1%})",
                    "target_ratio": self.max_single_position
                })
                
        return recommendations
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成风险管理信号"""
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "风险分析数据获取失败"
            }
            
        overall_risk = analysis.get("overall_risk", {})
        risk_level = overall_risk.get("risk_level", "中")
        risk_score = overall_risk.get("risk_score", 1.5)
        risk_alerts = analysis.get("risk_alerts", [])
        
        # 风险管理信号
        if risk_level in ["极高", "高"]:
            signal = "SELL"
            confidence = min(risk_score / 2, 1.0)
            reason = f"风险等级{risk_level}，建议减仓规避风险"
        elif risk_level == "中":
            signal = "HOLD"
            confidence = 0.5
            reason = f"风险等级{risk_level}，维持当前仓位"
        else:
            signal = "HOLD"  # 低风险时不主动建议加仓，由其他Agent决定
            confidence = 0.3
            reason = f"风险等级{risk_level}，风险可控"
            
        # 如果有紧急预警，强制减仓信号
        if any("⚠️" in alert for alert in risk_alerts):
            signal = "SELL"
            confidence = max(confidence, 0.8)
            reason += "；有风险预警"
            
        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "alerts_count": len(risk_alerts)
        }