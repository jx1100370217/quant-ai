from typing import Dict, List, Any
from .base import BaseAgent
from datetime import datetime, timedelta
import asyncio

class SentimentAnalyst(BaseAgent):
    """情绪分析Agent - 分析龙虎榜、涨跌停数据、市场情绪温度"""
    
    def __init__(self):
        super().__init__(
            name="SentimentAnalyst",
            description="分析龙虎榜、涨跌停数据、市场情绪温度"
        )
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """市场情绪分析"""
        
        # 获取今日日期
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 龙虎榜分析
        dragon_tiger_analysis = await self._analyze_dragon_tiger_board(today)
        
        # 涨跌停分析
        limit_analysis = await self._analyze_limit_movements()
        
        # 板块情绪分析
        sector_sentiment = await self._analyze_sector_sentiment()
        
        # 资金情绪分析
        fund_sentiment = await self._analyze_fund_sentiment()
        
        # 综合情绪指数
        sentiment_index = self._calculate_sentiment_index(
            dragon_tiger_analysis, limit_analysis, sector_sentiment, fund_sentiment
        )
        
        # 情绪预警
        sentiment_alerts = self._generate_sentiment_alerts(sentiment_index, limit_analysis)
        
        return {
            "dragon_tiger_analysis": dragon_tiger_analysis,
            "limit_analysis": limit_analysis,
            "sector_sentiment": sector_sentiment,
            "fund_sentiment": fund_sentiment,
            "sentiment_index": sentiment_index,
            "sentiment_alerts": sentiment_alerts,
            "analysis_date": today
        }
        
    async def _analyze_dragon_tiger_board(self, date: str) -> Dict[str, Any]:
        """龙虎榜分析"""
        from data.eastmoney import eastmoney_api
        
        try:
            dragon_tiger_data = await eastmoney_api.get_dragon_tiger(date)
            
            if not dragon_tiger_data:
                return {
                    "status": "暂无数据",
                    "hot_money_activity": "低",
                    "net_buy_amount": 0,
                    "active_stocks": 0
                }
            
            # 统计分析
            total_net_amount = sum(item.get("net_amount", 0) for item in dragon_tiger_data)
            net_buy_stocks = len([item for item in dragon_tiger_data if item.get("net_amount", 0) > 0])
            total_stocks = len(dragon_tiger_data)
            
            # 大单净买入比例
            net_buy_ratio = net_buy_stocks / total_stocks if total_stocks > 0 else 0
            
            # 热门股票（净买入前5）
            hot_stocks = sorted(dragon_tiger_data, key=lambda x: x.get("net_amount", 0), reverse=True)[:5]
            
            # 游资活跃度判断
            if total_net_amount > 1000000000:  # 10亿以上
                hot_money_activity = "极高"
            elif total_net_amount > 500000000:  # 5-10亿
                hot_money_activity = "高"
            elif total_net_amount > 0:
                hot_money_activity = "中等"
            else:
                hot_money_activity = "低"
                
            # 市场偏好分析
            market_preference = "投机" if net_buy_ratio > 0.6 else "谨慎" if net_buy_ratio < 0.4 else "中性"
            
            return {
                "status": "正常",
                "hot_money_activity": hot_money_activity,
                "net_buy_amount": total_net_amount,
                "active_stocks": total_stocks,
                "net_buy_ratio": net_buy_ratio,
                "market_preference": market_preference,
                "hot_stocks": [
                    {
                        "code": stock.get("code"),
                        "name": stock.get("name"),
                        "net_amount": stock.get("net_amount", 0),
                        "reason": stock.get("reason", "")
                    } 
                    for stock in hot_stocks
                ]
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "获取失败",
                "hot_money_activity": "未知"
            }
            
    async def _analyze_limit_movements(self) -> Dict[str, Any]:
        """涨跌停分析"""
        from data.eastmoney import eastmoney_api
        
        try:
            # 获取板块数据来估算涨跌情况
            sectors = await eastmoney_api.get_sector_ranking("industry")
            
            if not sectors:
                return {"status": "数据获取失败"}
                
            # 统计涨跌幅分布
            limit_up_count = 0      # 涨停
            strong_up_count = 0     # 强势上涨(>7%)
            moderate_up_count = 0   # 温和上涨(3-7%)
            flat_count = 0          # 平盘(-3% to 3%)
            moderate_down_count = 0 # 温和下跌(-7% to -3%)
            strong_down_count = 0   # 强势下跌(<-7%)
            limit_down_count = 0    # 跌停
            
            for sector in sectors:
                change_pct = sector.get("change_pct", 0)
                if change_pct >= 0.095:  # 接近涨停
                    limit_up_count += 1
                elif change_pct >= 0.07:
                    strong_up_count += 1
                elif change_pct >= 0.03:
                    moderate_up_count += 1
                elif change_pct >= -0.03:
                    flat_count += 1
                elif change_pct >= -0.07:
                    moderate_down_count += 1
                elif change_pct >= -0.095:
                    strong_down_count += 1
                else:
                    limit_down_count += 1
                    
            total_count = len(sectors)
            
            # 计算情绪指标
            up_ratio = (limit_up_count + strong_up_count + moderate_up_count) / total_count if total_count > 0 else 0
            down_ratio = (limit_down_count + strong_down_count + moderate_down_count) / total_count if total_count > 0 else 0
            
            # 市场情绪判断
            if up_ratio > 0.7:
                market_mood = "狂热"
            elif up_ratio > 0.5:
                market_mood = "乐观"
            elif up_ratio > 0.4:
                market_mood = "中性偏乐观"
            elif down_ratio > 0.6:
                market_mood = "恐慌"
            elif down_ratio > 0.4:
                market_mood = "悲观"
            else:
                market_mood = "中性"
                
            # 强弱指数
            strength_index = (limit_up_count * 2 + strong_up_count - strong_down_count - limit_down_count * 2) / total_count if total_count > 0 else 0
            
            return {
                "status": "正常",
                "market_mood": market_mood,
                "up_ratio": up_ratio,
                "down_ratio": down_ratio,
                "strength_index": strength_index,
                "distribution": {
                    "limit_up": limit_up_count,
                    "strong_up": strong_up_count,
                    "moderate_up": moderate_up_count,
                    "flat": flat_count,
                    "moderate_down": moderate_down_count,
                    "strong_down": strong_down_count,
                    "limit_down": limit_down_count
                },
                "total_analyzed": total_count
            }
            
        except Exception as e:
            return {"error": str(e), "status": "分析失败"}
            
    async def _analyze_sector_sentiment(self) -> Dict[str, Any]:
        """板块情绪分析"""
        from data.eastmoney import eastmoney_api
        
        try:
            # 获取行业和概念板块数据
            industry_sectors = await eastmoney_api.get_sector_ranking("industry")
            concept_sectors = await eastmoney_api.get_sector_ranking("concept")
            
            # 行业板块情绪
            industry_sentiment = self._calculate_sector_sentiment(industry_sectors, "行业")
            
            # 概念板块情绪
            concept_sentiment = self._calculate_sector_sentiment(concept_sectors, "概念")
            
            # 资金流向偏好
            all_sectors = industry_sectors + concept_sectors
            inflow_sectors = [s for s in all_sectors if s.get("net_inflow", 0) > 0]
            outflow_sectors = [s for s in all_sectors if s.get("net_inflow", 0) < 0]
            
            fund_preference = {
                "inflow_count": len(inflow_sectors),
                "outflow_count": len(outflow_sectors),
                "net_inflow_ratio": len(inflow_sectors) / len(all_sectors) if all_sectors else 0
            }
            
            # 热门主题识别
            hot_themes = self._identify_hot_themes(concept_sectors)
            
            return {
                "industry_sentiment": industry_sentiment,
                "concept_sentiment": concept_sentiment,
                "fund_preference": fund_preference,
                "hot_themes": hot_themes,
                "sector_rotation_active": self._assess_sector_rotation(all_sectors)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def _calculate_sector_sentiment(self, sectors: List[Dict], sector_type: str) -> Dict[str, Any]:
        """计算板块情绪"""
        if not sectors:
            return {"sentiment": "无数据", "score": 0}
            
        # 统计涨跌分布
        rising = len([s for s in sectors if s.get("change_pct", 0) > 0])
        falling = len([s for s in sectors if s.get("change_pct", 0) < 0])
        total = len(sectors)
        
        rising_ratio = rising / total if total > 0 else 0
        
        # 平均涨跌幅
        avg_change = sum(s.get("change_pct", 0) for s in sectors) / total if total > 0 else 0
        
        # 情绪评分
        sentiment_score = rising_ratio * 2 - 1  # 转换为-1到1的评分
        
        # 情绪等级
        if sentiment_score > 0.6:
            sentiment_level = "极度乐观"
        elif sentiment_score > 0.2:
            sentiment_level = "乐观"
        elif sentiment_score > -0.2:
            sentiment_level = "中性"
        elif sentiment_score > -0.6:
            sentiment_level = "悲观"
        else:
            sentiment_level = "极度悲观"
            
        return {
            "sentiment": sentiment_level,
            "score": sentiment_score,
            "rising_ratio": rising_ratio,
            "avg_change": avg_change,
            "rising_count": rising,
            "falling_count": falling,
            "total_count": total
        }
        
    def _identify_hot_themes(self, concept_sectors: List[Dict]) -> List[Dict]:
        """识别热门主题"""
        if not concept_sectors:
            return []
            
        # 按资金净流入和涨跌幅综合排序
        def theme_score(sector):
            change_pct = sector.get("change_pct", 0)
            net_inflow = sector.get("net_inflow", 0)
            # 综合评分：涨跌幅权重0.6，资金流入权重0.4
            return change_pct * 0.6 + (net_inflow / 1000000000) * 0.4
            
        hot_themes = sorted(concept_sectors, key=theme_score, reverse=True)[:10]
        
        return [
            {
                "name": theme.get("name"),
                "change_pct": theme.get("change_pct", 0),
                "net_inflow": theme.get("net_inflow", 0),
                "score": theme_score(theme)
            }
            for theme in hot_themes
        ]
        
    def _assess_sector_rotation(self, all_sectors: List[Dict]) -> bool:
        """评估板块轮动是否活跃"""
        if not all_sectors:
            return False
            
        # 计算板块间的差异程度
        changes = [s.get("change_pct", 0) for s in all_sectors]
        if not changes:
            return False
            
        import numpy as np
        std_dev = np.std(changes)
        
        # 标准差大于3%认为轮动活跃
        return std_dev > 0.03
        
    async def _analyze_fund_sentiment(self) -> Dict[str, Any]:
        """资金情绪分析"""
        from data.eastmoney import eastmoney_api
        
        try:
            # 获取大盘资金流向
            market_flow = await eastmoney_api.get_market_flow()
            
            if not market_flow:
                return {"sentiment": "无数据", "confidence": "低"}
                
            main_net = market_flow.get("main_net", 0)
            retail_net = market_flow.get("retail_net", 0)
            
            # 主力资金情绪
            if main_net > 1000000000:  # 10亿以上
                main_sentiment = "极度乐观"
                main_confidence = "极高"
            elif main_net > 500000000:  # 5-10亿
                main_sentiment = "乐观"
                main_confidence = "高"
            elif main_net > 0:
                main_sentiment = "谨慎乐观"
                main_confidence = "中等"
            elif main_net > -500000000:
                main_sentiment = "谨慎悲观"
                main_confidence = "中等"
            elif main_net > -1000000000:
                main_sentiment = "悲观"
                main_confidence = "高"
            else:
                main_sentiment = "极度悲观"
                main_confidence = "极高"
                
            # 散户资金情绪
            retail_sentiment = "乐观" if retail_net > 0 else "悲观"
            
            # 资金分歧度
            divergence_level = self._calculate_fund_divergence(main_net, retail_net)
            
            # 整体资金情绪
            overall_sentiment = self._calculate_overall_fund_sentiment(main_net, retail_net)
            
            return {
                "main_sentiment": main_sentiment,
                "main_confidence": main_confidence,
                "retail_sentiment": retail_sentiment,
                "divergence_level": divergence_level,
                "overall_sentiment": overall_sentiment,
                "main_net_flow": main_net,
                "retail_net_flow": retail_net
            }
            
        except Exception as e:
            return {"error": str(e), "sentiment": "未知"}
            
    def _calculate_fund_divergence(self, main_net: float, retail_net: float) -> str:
        """计算资金分歧度"""
        # 主力和散户方向相同
        if (main_net > 0 and retail_net > 0) or (main_net < 0 and retail_net < 0):
            return "低分歧"
        else:
            # 计算分歧程度
            total_amount = abs(main_net) + abs(retail_net)
            if total_amount > 2000000000:  # 20亿以上
                return "高分歧"
            elif total_amount > 1000000000:  # 10-20亿
                return "中等分歧"
            else:
                return "轻微分歧"
                
    def _calculate_overall_fund_sentiment(self, main_net: float, retail_net: float) -> str:
        """计算整体资金情绪"""
        # 主力资金权重更高
        weighted_sentiment = main_net * 0.7 + retail_net * 0.3
        
        if weighted_sentiment > 500000000:
            return "乐观"
        elif weighted_sentiment > 0:
            return "中性偏乐观"
        elif weighted_sentiment > -500000000:
            return "中性偏谨慎"
        else:
            return "悲观"
            
    def _calculate_sentiment_index(self, dragon_tiger: Dict, limit: Dict, sector: Dict, fund: Dict) -> Dict[str, Any]:
        """计算综合情绪指数"""
        sentiment_score = 0
        components = []
        
        # 龙虎榜情绪 (权重20%)
        dt_activity = dragon_tiger.get("hot_money_activity", "低")
        if dt_activity == "极高":
            sentiment_score += 0.8 * 0.2
            components.append("游资极度活跃")
        elif dt_activity == "高":
            sentiment_score += 0.5 * 0.2
            components.append("游资活跃")
        elif dt_activity == "中等":
            sentiment_score += 0.2 * 0.2
        elif dt_activity == "低":
            sentiment_score -= 0.2 * 0.2
            components.append("游资冷淡")
            
        # 涨跌分布情绪 (权重30%)
        if "strength_index" in limit:
            strength = limit["strength_index"]
            sentiment_score += strength * 0.3
            if strength > 0.5:
                components.append("涨停效应强")
            elif strength < -0.5:
                components.append("跌停压力大")
                
        # 板块情绪 (权重25%)
        industry_score = sector.get("industry_sentiment", {}).get("score", 0)
        concept_score = sector.get("concept_sentiment", {}).get("score", 0)
        avg_sector_score = (industry_score + concept_score) / 2
        sentiment_score += avg_sector_score * 0.25
        
        if avg_sector_score > 0.5:
            components.append("板块普涨")
        elif avg_sector_score < -0.5:
            components.append("板块普跌")
            
        # 资金情绪 (权重25%)
        fund_sentiment = fund.get("overall_sentiment", "中性")
        if fund_sentiment == "乐观":
            sentiment_score += 0.6 * 0.25
            components.append("资金乐观")
        elif fund_sentiment == "中性偏乐观":
            sentiment_score += 0.3 * 0.25
        elif fund_sentiment == "中性偏谨慎":
            sentiment_score -= 0.3 * 0.25
        elif fund_sentiment == "悲观":
            sentiment_score -= 0.6 * 0.25
            components.append("资金悲观")
            
        # 情绪等级
        if sentiment_score > 0.6:
            sentiment_level = "极度乐观"
            temperature = "过热"
        elif sentiment_score > 0.3:
            sentiment_level = "乐观"
            temperature = "偏热"
        elif sentiment_score > 0:
            sentiment_level = "中性偏乐观"
            temperature = "温和"
        elif sentiment_score > -0.3:
            sentiment_level = "中性偏谨慎"
            temperature = "偏冷"
        elif sentiment_score > -0.6:
            sentiment_level = "悲观"
            temperature = "较冷"
        else:
            sentiment_level = "极度悲观"
            temperature = "冰冷"
            
        return {
            "score": sentiment_score,
            "level": sentiment_level,
            "temperature": temperature,
            "components": components,
            "confidence": min(abs(sentiment_score) + 0.3, 1.0)
        }
        
    def _generate_sentiment_alerts(self, sentiment_index: Dict, limit_analysis: Dict) -> List[str]:
        """生成情绪预警"""
        alerts = []
        
        sentiment_score = sentiment_index.get("score", 0)
        temperature = sentiment_index.get("temperature", "温和")
        
        # 过热预警
        if sentiment_score > 0.7:
            alerts.append("⚠️ 市场情绪过热，谨防回调风险")
            
        # 过冷预警
        if sentiment_score < -0.7:
            alerts.append("⚠️ 市场情绪冰冷，关注反弹机会")
            
        # 涨跌停异常预警
        if "distribution" in limit_analysis:
            dist = limit_analysis["distribution"]
            limit_up = dist.get("limit_up", 0)
            limit_down = dist.get("limit_down", 0)
            
            if limit_up > 20:
                alerts.append("🔥 涨停潮出现，市场情绪高涨")
            if limit_down > 20:
                alerts.append("❄️ 跌停潮出现，市场恐慌加剧")
                
        # 资金流向预警
        if temperature == "过热" and "资金乐观" in sentiment_index.get("components", []):
            alerts.append("💰 资金情绪亢奋，注意获利了结")
            
        return alerts
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成情绪面交易信号"""
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "情绪数据获取失败"
            }
            
        sentiment_index = analysis.get("sentiment_index", {})
        score = sentiment_index.get("score", 0)
        level = sentiment_index.get("level", "中性")
        confidence = sentiment_index.get("confidence", 0.5)
        
        # 情绪反转策略：极度情绪时反向操作
        if score > 0.6:  # 极度乐观时谨慎
            signal = "SELL"
            reason = f"市场情绪{level}，建议获利了结"
        elif score > 0.2:  # 乐观时可以持有
            signal = "HOLD"
            reason = f"市场情绪{level}，保持观望"
        elif score < -0.6:  # 极度悲观时抄底
            signal = "BUY"
            reason = f"市场情绪{level}，关注抄底机会"
        elif score < -0.2:  # 悲观时继续观望
            signal = "HOLD"
            reason = f"市场情绪{level}，暂时观望"
        else:  # 中性情绪
            signal = "HOLD"
            reason = f"市场情绪{level}，维持现状"
            
        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "sentiment_score": score,
            "sentiment_level": level
        }