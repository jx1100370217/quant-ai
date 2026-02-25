from typing import Dict, List, Any
from .base import BaseAgent
from data.eastmoney import eastmoney_api
import asyncio

class MarketAnalyst(BaseAgent):
    """市场分析Agent - 分析大盘走势、板块轮动、资金流向"""
    
    def __init__(self):
        super().__init__(
            name="MarketAnalyst",
            description="分析大盘走势、板块轮动、资金流向，判断市场整体方向"
        )
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析市场整体情况"""
        
        # 获取大盘指数数据
        indices = await self._get_major_indices()
        
        # 获取板块排行
        sectors = await eastmoney_api.get_sector_ranking("industry")
        concept_sectors = await eastmoney_api.get_sector_ranking("concept")
        
        # 获取资金流向
        market_flow = await eastmoney_api.get_market_flow()
        
        # 分析市场趋势
        market_trend = self._analyze_market_trend(indices)
        
        # 分析板块轮动
        sector_rotation = self._analyze_sector_rotation(sectors, concept_sectors)
        
        # 分析资金流向
        fund_flow_analysis = self._analyze_fund_flow(market_flow, sectors[:10])
        
        # 综合市场情绪
        market_sentiment = self._calculate_market_sentiment(indices, sectors, market_flow)
        
        return {
            "indices": indices,
            "sectors": sectors[:20],  # 前20个板块
            "concept_sectors": concept_sectors[:20],
            "market_flow": market_flow,
            "market_trend": market_trend,
            "sector_rotation": sector_rotation,
            "fund_flow_analysis": fund_flow_analysis,
            "market_sentiment": market_sentiment,
            "summary": self._generate_summary(market_trend, sector_rotation, fund_flow_analysis, market_sentiment)
        }
        
    async def _get_major_indices(self) -> Dict[str, Any]:
        """获取主要指数数据"""
        index_codes = ["000001", "399001", "399006"]  # 上证指数、深证成指、创业板指
        
        try:
            quotes = await eastmoney_api.get_batch_quotes(index_codes)
            
            # 获取K线数据计算技术指标
            indices_data = {}
            for code in index_codes:
                if code in quotes:
                    # 获取近期K线数据
                    klines = await eastmoney_api.get_kline_data(code, "101", 20)
                    
                    indices_data[code] = {
                        "name": quotes[code]["name"],
                        "current": quotes[code],
                        "klines": klines,
                        "ma5": self._calculate_ma(klines, 5) if len(klines) >= 5 else 0,
                        "ma10": self._calculate_ma(klines, 10) if len(klines) >= 10 else 0,
                        "ma20": self._calculate_ma(klines, 20) if len(klines) >= 20 else 0
                    }
                    
            return indices_data
        except Exception as e:
            return {"error": str(e)}
            
    def _calculate_ma(self, klines: List[Dict], period: int) -> float:
        """计算移动平均线"""
        if len(klines) < period:
            return 0
        return sum(k["close"] for k in klines[-period:]) / period
        
    def _analyze_market_trend(self, indices: Dict[str, Any]) -> Dict[str, Any]:
        """分析市场趋势"""
        if not indices or "error" in indices:
            return {"trend": "不明确", "strength": 0, "reason": "数据获取失败"}
            
        # 计算主要指数的综合表现
        total_change = 0
        valid_count = 0
        
        trend_signals = []
        
        for code, data in indices.items():
            if isinstance(data, dict) and "current" in data:
                current = data["current"]
                change_pct = current.get("change_pct", 0)
                total_change += change_pct
                valid_count += 1
                
                # 均线趋势分析
                price = current.get("price", 0)
                ma5 = data.get("ma5", 0)
                ma10 = data.get("ma10", 0)
                ma20 = data.get("ma20", 0)
                
                if price > ma5 > ma10 > ma20:
                    trend_signals.append("强势上升")
                elif price < ma5 < ma10 < ma20:
                    trend_signals.append("弱势下降")
                elif price > ma20:
                    trend_signals.append("相对强势")
                else:
                    trend_signals.append("相对弱势")
                    
        if valid_count == 0:
            return {"trend": "不明确", "strength": 0, "reason": "无有效数据"}
            
        avg_change = total_change / valid_count
        
        # 判断趋势
        if avg_change > 1:
            trend = "强势上涨"
            strength = min(abs(avg_change) / 3, 1.0)  # 标准化强度
        elif avg_change > 0:
            trend = "温和上涨"
            strength = min(abs(avg_change) / 2, 1.0)
        elif avg_change > -1:
            trend = "温和下跌"
            strength = min(abs(avg_change) / 2, 1.0)
        else:
            trend = "强势下跌"
            strength = min(abs(avg_change) / 3, 1.0)
            
        return {
            "trend": trend,
            "strength": strength,
            "avg_change": avg_change,
            "signals": trend_signals,
            "reason": f"三大指数平均涨跌幅{avg_change:.2%}"
        }
        
    def _analyze_sector_rotation(self, sectors: List[Dict], concept_sectors: List[Dict]) -> Dict[str, Any]:
        """分析板块轮动"""
        if not sectors:
            return {"rotation": "无明显轮动", "hot_sectors": [], "cold_sectors": []}
            
        # 按资金净流入排序
        sectors_by_flow = sorted(sectors, key=lambda x: x.get("net_inflow", 0), reverse=True)
        
        # 热门板块（资金净流入前5）
        hot_sectors = sectors_by_flow[:5]
        # 冷门板块（资金净流出前5）
        cold_sectors = sorted(sectors_by_flow, key=lambda x: x.get("net_inflow", 0))[:5]
        
        # 计算轮动强度
        total_inflow = sum(s.get("net_inflow", 0) for s in hot_sectors if s.get("net_inflow", 0) > 0)
        total_outflow = abs(sum(s.get("net_inflow", 0) for s in cold_sectors if s.get("net_inflow", 0) < 0))
        
        rotation_strength = min((total_inflow + total_outflow) / 10000000000, 1.0)  # 标准化
        
        # 判断轮动类型
        if rotation_strength > 0.7:
            rotation_type = "强烈轮动"
        elif rotation_strength > 0.4:
            rotation_type = "中等轮动"
        elif rotation_strength > 0.2:
            rotation_type = "温和轮动"
        else:
            rotation_type = "无明显轮动"
            
        return {
            "rotation": rotation_type,
            "strength": rotation_strength,
            "hot_sectors": [{"name": s["name"], "net_inflow": s.get("net_inflow", 0)} for s in hot_sectors],
            "cold_sectors": [{"name": s["name"], "net_inflow": s.get("net_inflow", 0)} for s in cold_sectors],
            "total_inflow": total_inflow,
            "total_outflow": total_outflow
        }
        
    def _analyze_fund_flow(self, market_flow: Dict, top_sectors: List[Dict]) -> Dict[str, Any]:
        """分析资金流向"""
        if not market_flow:
            return {"flow_direction": "不明确", "strength": 0}
            
        main_net = market_flow.get("main_net", 0)
        retail_net = market_flow.get("retail_net", 0)
        
        # 主力资金流向分析
        if main_net > 500000000:  # 5亿
            main_direction = "大幅流入"
        elif main_net > 0:
            main_direction = "净流入"
        elif main_net > -500000000:
            main_direction = "净流出"
        else:
            main_direction = "大幅流出"
            
        # 散户资金分析
        if retail_net > 0:
            retail_direction = "净流入"
        else:
            retail_direction = "净流出"
            
        # 资金分歧度（主力和散户方向相反程度）
        divergence = abs((main_net > 0) - (retail_net > 0))
        
        return {
            "main_direction": main_direction,
            "retail_direction": retail_direction,
            "main_net": main_net,
            "retail_net": retail_net,
            "divergence": divergence,
            "sector_concentration": len([s for s in top_sectors if s.get("net_inflow", 0) > 0])
        }
        
    def _calculate_market_sentiment(self, indices: Dict, sectors: List[Dict], market_flow: Dict) -> Dict[str, Any]:
        """计算市场情绪"""
        sentiment_score = 0
        factors = []
        
        # 指数表现因子 (权重30%)
        if indices and "error" not in indices:
            avg_change = 0
            count = 0
            for data in indices.values():
                if isinstance(data, dict) and "current" in data:
                    avg_change += data["current"].get("change_pct", 0)
                    count += 1
            if count > 0:
                index_sentiment = (avg_change / count) * 10  # 放大10倍
                sentiment_score += index_sentiment * 0.3
                factors.append(f"指数表现: {avg_change/count:.2%}")
                
        # 板块活跃度因子 (权重25%)
        if sectors:
            rising_sectors = len([s for s in sectors if s.get("change_pct", 0) > 0])
            sector_sentiment = (rising_sectors / len(sectors) - 0.5) * 2  # 标准化到[-1, 1]
            sentiment_score += sector_sentiment * 0.25
            factors.append(f"上涨板块占比: {rising_sectors/len(sectors):.1%}")
            
        # 资金流向因子 (权重25%)
        if market_flow:
            main_net = market_flow.get("main_net", 0)
            flow_sentiment = max(-1, min(1, main_net / 1000000000))  # 以10亿为基准标准化
            sentiment_score += flow_sentiment * 0.25
            factors.append(f"主力资金: {main_net/100000000:.1f}亿")
            
        # 板块资金集中度因子 (权重20%)
        if sectors:
            inflow_sectors = [s for s in sectors if s.get("net_inflow", 0) > 0]
            if len(sectors) > 0:
                concentration_sentiment = (len(inflow_sectors) / len(sectors) - 0.5) * 2
                sentiment_score += concentration_sentiment * 0.2
                factors.append(f"资金流入板块: {len(inflow_sectors)}")
                
        # 情绪等级
        if sentiment_score > 0.6:
            sentiment_level = "极度乐观"
        elif sentiment_score > 0.3:
            sentiment_level = "乐观"
        elif sentiment_score > -0.3:
            sentiment_level = "中性"
        elif sentiment_score > -0.6:
            sentiment_level = "悲观"
        else:
            sentiment_level = "极度悲观"
            
        return {
            "score": sentiment_score,
            "level": sentiment_level,
            "factors": factors
        }
        
    def _generate_summary(self, trend: Dict, rotation: Dict, flow: Dict, sentiment: Dict) -> str:
        """生成分析摘要"""
        return (f"市场趋势: {trend.get('trend', '不明确')}，"
                f"板块轮动: {rotation.get('rotation', '无')}，"
                f"主力资金: {flow.get('main_direction', '不明确')}，"
                f"市场情绪: {sentiment.get('level', '中性')}")
                
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成交易信号"""
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "数据获取失败，保持观望"
            }
            
        # 获取分析结果
        trend = analysis.get("market_trend", {})
        sentiment = analysis.get("market_sentiment", {})
        flow = analysis.get("fund_flow_analysis", {})
        
        # 信号强度计算
        signal_strength = 0
        reasons = []
        
        # 趋势因子
        trend_name = trend.get("trend", "")
        if "强势上涨" in trend_name:
            signal_strength += 0.4
            reasons.append("大盘强势上涨")
        elif "温和上涨" in trend_name:
            signal_strength += 0.2
            reasons.append("大盘温和上涨")
        elif "温和下跌" in trend_name:
            signal_strength -= 0.2
            reasons.append("大盘温和下跌")
        elif "强势下跌" in trend_name:
            signal_strength -= 0.4
            reasons.append("大盘强势下跌")
            
        # 情绪因子
        sentiment_score = sentiment.get("score", 0)
        signal_strength += sentiment_score * 0.3
        
        # 资金流向因子
        main_direction = flow.get("main_direction", "")
        if "大幅流入" in main_direction:
            signal_strength += 0.3
            reasons.append("主力资金大幅流入")
        elif "净流入" in main_direction:
            signal_strength += 0.15
            reasons.append("主力资金净流入")
        elif "净流出" in main_direction:
            signal_strength -= 0.15
            reasons.append("主力资金净流出")
        elif "大幅流出" in main_direction:
            signal_strength -= 0.3
            reasons.append("主力资金大幅流出")
            
        # 生成最终信号
        if signal_strength > 0.5:
            signal = "BUY"
            confidence = min(signal_strength, 1.0)
        elif signal_strength < -0.5:
            signal = "SELL"
            confidence = min(abs(signal_strength), 1.0)
        else:
            signal = "HOLD"
            confidence = 0.5
            reasons.append("市场信号不明确")
            
        return {
            "signal": signal,
            "confidence": confidence,
            "reason": "; ".join(reasons),
            "signal_strength": signal_strength
        }