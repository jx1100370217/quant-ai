from typing import Dict, List, Any
from .base import BaseAgent
from utils.indicators import TechnicalIndicators
import numpy as np

class TechnicalAnalyst(BaseAgent):
    """技术分析Agent - 计算技术指标，给出技术面信号"""
    
    def __init__(self):
        super().__init__(
            name="TechnicalAnalyst", 
            description="计算MACD/RSI/KDJ/布林带等技术指标，给出技术面信号"
        )
        self.indicators = TechnicalIndicators()
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """技术分析"""
        
        # 获取目标股票列表（从持仓或关注列表获取）
        target_stocks = data.get("target_stocks", ["000001", "399001", "399006"])  # 默认分析指数
        
        analysis_results = {}
        
        for stock_code in target_stocks:
            stock_analysis = await self._analyze_stock(stock_code)
            if stock_analysis:
                analysis_results[stock_code] = stock_analysis
                
        # 整体技术面总结
        overall_signal = self._calculate_overall_signal(analysis_results)
        
        return {
            "stock_analysis": analysis_results,
            "overall_signal": overall_signal,
            "analysis_timestamp": self._get_timestamp(),
            "analyzed_stocks": list(analysis_results.keys())
        }
        
    async def _analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        """分析单只股票的技术面"""
        from data.eastmoney import eastmoney_api
        
        try:
            # 获取K线数据
            klines = await eastmoney_api.get_kline_data(stock_code, "101", 100)  # 100天数据
            if len(klines) < 20:
                return None
                
            # 准备价格数据
            closes = np.array([k["close"] for k in klines])
            highs = np.array([k["high"] for k in klines])
            lows = np.array([k["low"] for k in klines])
            volumes = np.array([k["volume"] for k in klines])
            
            # 计算技术指标
            indicators = {}
            
            # 移动平均线
            ma5 = self.indicators.sma(closes, 5)
            ma10 = self.indicators.sma(closes, 10) 
            ma20 = self.indicators.sma(closes, 20)
            ma60 = self.indicators.sma(closes, 60) if len(closes) >= 60 else None
            
            indicators["ma"] = {
                "ma5": ma5[-1] if len(ma5) > 0 else 0,
                "ma10": ma10[-1] if len(ma10) > 0 else 0,
                "ma20": ma20[-1] if len(ma20) > 0 else 0,
                "ma60": ma60[-1] if ma60 is not None and len(ma60) > 0 else 0
            }
            
            # MACD
            macd_line, signal_line, histogram = self.indicators.macd(closes)
            indicators["macd"] = {
                "macd": macd_line[-1] if len(macd_line) > 0 else 0,
                "signal": signal_line[-1] if len(signal_line) > 0 else 0,
                "histogram": histogram[-1] if len(histogram) > 0 else 0
            }
            
            # RSI
            rsi = self.indicators.rsi(closes, 14)
            indicators["rsi"] = {
                "rsi": rsi[-1] if len(rsi) > 0 else 50,
                "rsi_6": self.indicators.rsi(closes, 6)[-1] if len(closes) >= 6 else 50
            }
            
            # KDJ
            k, d, j = self.indicators.kdj(highs, lows, closes)
            indicators["kdj"] = {
                "k": k[-1] if len(k) > 0 else 50,
                "d": d[-1] if len(d) > 0 else 50,
                "j": j[-1] if len(j) > 0 else 50
            }
            
            # 布林带
            bb_upper, bb_middle, bb_lower = self.indicators.bollinger_bands(closes, 20, 2)
            indicators["bollinger"] = {
                "upper": bb_upper[-1] if len(bb_upper) > 0 else 0,
                "middle": bb_middle[-1] if len(bb_middle) > 0 else 0,
                "lower": bb_lower[-1] if len(bb_lower) > 0 else 0,
                "position": self._calculate_bb_position(closes[-1], bb_upper[-1], bb_lower[-1]) if len(bb_upper) > 0 else 0.5
            }
            
            # 成交量指标
            volume_ma5 = self.indicators.sma(volumes, 5)
            indicators["volume"] = {
                "current": volumes[-1],
                "ma5": volume_ma5[-1] if len(volume_ma5) > 0 else 0,
                "volume_ratio": volumes[-1] / volume_ma5[-1] if len(volume_ma5) > 0 and volume_ma5[-1] > 0 else 1
            }
            
            # 支撑阻力位
            support_resistance = self._calculate_support_resistance(highs, lows, closes)
            
            # 趋势分析
            trend_analysis = self._analyze_trend(closes, ma5, ma20, ma60)
            
            # 技术信号汇总
            technical_signals = self._generate_technical_signals(indicators, trend_analysis)
            
            return {
                "stock_code": stock_code,
                "indicators": indicators,
                "support_resistance": support_resistance,
                "trend_analysis": trend_analysis,
                "technical_signals": technical_signals,
                "latest_price": closes[-1],
                "latest_volume": volumes[-1]
            }
            
        except Exception as e:
            return {"error": str(e), "stock_code": stock_code}
            
    def _calculate_bb_position(self, price: float, upper: float, lower: float) -> float:
        """计算价格在布林带中的位置（0-1）"""
        if upper == lower:
            return 0.5
        return (price - lower) / (upper - lower)
        
    def _calculate_support_resistance(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict[str, Any]:
        """计算支撑阻力位"""
        recent_highs = highs[-20:]  # 最近20天
        recent_lows = lows[-20:]
        
        # 阻力位：近期高点
        resistance_levels = []
        for i in range(1, len(recent_highs) - 1):
            if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i+1]:
                resistance_levels.append(recent_highs[i])
                
        # 支撑位：近期低点  
        support_levels = []
        for i in range(1, len(recent_lows) - 1):
            if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
                support_levels.append(recent_lows[i])
                
        current_price = closes[-1]
        
        # 最近的支撑阻力位
        nearby_resistance = min([r for r in resistance_levels if r > current_price], default=None)
        nearby_support = max([s for s in support_levels if s < current_price], default=None)
        
        return {
            "resistance_levels": sorted(resistance_levels, reverse=True)[:3],  # 前3个阻力位
            "support_levels": sorted(support_levels, reverse=True)[:3],       # 前3个支撑位
            "nearby_resistance": nearby_resistance,
            "nearby_support": nearby_support
        }
        
    def _analyze_trend(self, closes: np.ndarray, ma5: np.ndarray, ma20: np.ndarray, ma60: np.ndarray = None) -> Dict[str, Any]:
        """趋势分析"""
        current_price = closes[-1]
        
        # 短期趋势（5日均线）
        if len(ma5) >= 2:
            short_trend = "上升" if ma5[-1] > ma5[-2] else "下降"
        else:
            short_trend = "不明确"
            
        # 中期趋势（20日均线）
        if len(ma20) >= 2:
            medium_trend = "上升" if ma20[-1] > ma20[-2] else "下降" 
        else:
            medium_trend = "不明确"
            
        # 长期趋势（60日均线）
        long_trend = "不明确"
        if ma60 is not None and len(ma60) >= 2:
            long_trend = "上升" if ma60[-1] > ma60[-2] else "下降"
            
        # 均线排列
        ma_arrangement = self._analyze_ma_arrangement(current_price, ma5, ma20, ma60)
        
        # 趋势强度
        trend_strength = self._calculate_trend_strength(closes)
        
        return {
            "short_trend": short_trend,
            "medium_trend": medium_trend, 
            "long_trend": long_trend,
            "ma_arrangement": ma_arrangement,
            "trend_strength": trend_strength
        }
        
    def _analyze_ma_arrangement(self, price: float, ma5: np.ndarray, ma20: np.ndarray, ma60: np.ndarray = None) -> str:
        """分析均线排列"""
        if len(ma5) == 0 or len(ma20) == 0:
            return "数据不足"
            
        ma5_val = ma5[-1]
        ma20_val = ma20[-1] 
        ma60_val = ma60[-1] if ma60 is not None and len(ma60) > 0 else None
        
        if ma60_val is not None:
            if price > ma5_val > ma20_val > ma60_val:
                return "多头排列"
            elif price < ma5_val < ma20_val < ma60_val:
                return "空头排列"
            else:
                return "无序排列"
        else:
            if price > ma5_val > ma20_val:
                return "短期多头"
            elif price < ma5_val < ma20_val:
                return "短期空头"
            else:
                return "震荡整理"
                
    def _calculate_trend_strength(self, closes: np.ndarray) -> float:
        """计算趋势强度（0-1）"""
        if len(closes) < 10:
            return 0.5
            
        # 使用线性回归斜率
        x = np.arange(len(closes[-20:]))  # 最近20天
        y = closes[-20:]
        slope = np.polyfit(x, y, 1)[0]
        
        # 标准化斜率为强度值
        price_range = np.max(y) - np.min(y)
        if price_range > 0:
            strength = abs(slope) / (price_range / len(x))
            return min(strength, 1.0)
        return 0.5
        
    def _generate_technical_signals(self, indicators: Dict, trend: Dict) -> Dict[str, Any]:
        """生成技术信号"""
        signals = []
        signal_strength = 0
        
        # MACD信号
        macd = indicators.get("macd", {})
        if macd.get("macd", 0) > macd.get("signal", 0) and macd.get("histogram", 0) > 0:
            signals.append("MACD金叉")
            signal_strength += 0.2
        elif macd.get("macd", 0) < macd.get("signal", 0) and macd.get("histogram", 0) < 0:
            signals.append("MACD死叉")
            signal_strength -= 0.2
            
        # RSI信号
        rsi = indicators.get("rsi", {}).get("rsi", 50)
        if rsi > 80:
            signals.append("RSI超买")
            signal_strength -= 0.15
        elif rsi < 20:
            signals.append("RSI超卖")
            signal_strength += 0.15
            
        # KDJ信号
        kdj = indicators.get("kdj", {})
        k, d, j = kdj.get("k", 50), kdj.get("d", 50), kdj.get("j", 50)
        if k > d and k < 80 and j > 0:
            signals.append("KDJ金叉")
            signal_strength += 0.1
        elif k < d and k > 20 and j < 100:
            signals.append("KDJ死叉")
            signal_strength -= 0.1
            
        # 布林带信号
        bb = indicators.get("bollinger", {})
        bb_pos = bb.get("position", 0.5)
        if bb_pos > 0.8:
            signals.append("接近布林上轨")
            signal_strength -= 0.1
        elif bb_pos < 0.2:
            signals.append("接近布林下轨")
            signal_strength += 0.1
            
        # 均线信号
        ma_arrangement = trend.get("ma_arrangement", "")
        if ma_arrangement == "多头排列":
            signals.append("均线多头排列")
            signal_strength += 0.25
        elif ma_arrangement == "空头排列":
            signals.append("均线空头排列")
            signal_strength -= 0.25
            
        # 成交量信号
        volume = indicators.get("volume", {})
        volume_ratio = volume.get("volume_ratio", 1)
        if volume_ratio > 2:
            signals.append("放量突破")
            signal_strength += 0.1
        elif volume_ratio < 0.5:
            signals.append("缩量整理")
            signal_strength -= 0.05
            
        return {
            "signals": signals,
            "signal_strength": signal_strength,
            "signal_count": len(signals)
        }
        
    def _calculate_overall_signal(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """计算整体技术信号"""
        if not analysis_results:
            return {"signal": "HOLD", "confidence": 0, "reason": "无技术分析数据"}
            
        total_strength = 0
        valid_count = 0
        all_signals = []
        
        for stock_code, analysis in analysis_results.items():
            if "technical_signals" in analysis:
                signals = analysis["technical_signals"]
                strength = signals.get("signal_strength", 0)
                total_strength += strength
                valid_count += 1
                all_signals.extend(signals.get("signals", []))
                
        if valid_count == 0:
            return {"signal": "HOLD", "confidence": 0, "reason": "无有效技术信号"}
            
        avg_strength = total_strength / valid_count
        
        # 生成信号
        if avg_strength > 0.3:
            signal = "BUY"
            confidence = min(avg_strength, 1.0)
        elif avg_strength < -0.3:
            signal = "SELL"  
            confidence = min(abs(avg_strength), 1.0)
        else:
            signal = "HOLD"
            confidence = 0.5
            
        return {
            "signal": signal,
            "confidence": confidence,
            "signal_strength": avg_strength,
            "analyzed_stocks": valid_count,
            "key_signals": list(set(all_signals))[:5],  # 去重后取前5个
            "reason": f"技术面综合强度{avg_strength:.2f}"
        }
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终交易信号"""
        overall_signal = analysis.get("overall_signal", {})
        
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "技术分析数据获取失败"
            }
            
        return overall_signal
        
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()