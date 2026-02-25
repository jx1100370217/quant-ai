"""
多因子策略 - Multi-Factor Strategy
基于多个量化因子的综合评分策略
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import asyncio

from models.signal import Signal, SignalType
from utils.indicators import (
    calculate_rsi, calculate_macd, calculate_sma, calculate_ema,
    calculate_bollinger_bands, calculate_momentum, calculate_atr,
    calculate_volume_sma, calculate_std
)


class MultiFactorStrategy:
    """多因子策略实现"""
    
    def __init__(self):
        self.name = "多因子策略"
        self.description = "基于技术、基本面、情绪等多因子的综合量化策略"
        
        # 因子权重配置
        self.factor_weights = {
            'technical': 0.4,      # 技术因子权重
            'momentum': 0.25,      # 动量因子权重
            'value': 0.15,         # 价值因子权重
            'quality': 0.1,        # 质量因子权重
            'sentiment': 0.1       # 情绪因子权重
        }
        
        # 策略参数
        self.lookback_periods = {
            'short': 5,
            'medium': 20,
            'long': 60
        }
        
        self.signal_threshold = {
            'strong_buy': 80,
            'buy': 60,
            'hold': 40,
            'sell': 20
        }
        
        # 风险控制参数
        self.max_position_weight = 0.1  # 单股最大权重
        self.volatility_threshold = 0.5  # 波动率阈值
        
    async def generate_signals(self, market_data: Dict[str, Any]) -> List[Signal]:
        """
        生成多因子交易信号
        
        Args:
            market_data: 市场数据字典
            
        Returns:
            List[Signal]: 交易信号列表
        """
        signals = []
        
        try:
            stocks_data = market_data.get('stocks', {})
            
            # 计算所有股票的因子得分
            stock_scores = {}
            
            for stock_code, stock_data in stocks_data.items():
                score_info = await self._calculate_multi_factor_score(stock_code, stock_data, market_data)
                if score_info:
                    stock_scores[stock_code] = score_info
            
            # 基于因子得分生成信号
            signals = self._generate_signals_from_scores(stock_scores)
            
        except Exception as e:
            print(f"多因子策略信号生成失败: {e}")
            
        return signals
    
    async def _calculate_multi_factor_score(self, stock_code: str, stock_data: Dict,
                                          market_data: Dict) -> Dict:
        """
        计算股票的多因子综合得分
        
        Args:
            stock_code: 股票代码
            stock_data: 股票数据
            market_data: 市场数据
            
        Returns:
            Dict: 因子得分信息
        """
        try:
            kline_data = stock_data.get('kline', [])
            if len(kline_data) < self.lookback_periods['long']:
                return None
                
            df = pd.DataFrame(kline_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            prices = df['close'].astype(float)
            volumes = df['volume'].astype(float)
            highs = df['high'].astype(float)
            lows = df['low'].astype(float)
            opens = df['open'].astype(float)
            
            # 计算各类因子得分
            factor_scores = {}
            
            # 1. 技术因子
            factor_scores['technical'] = self._calculate_technical_factors(
                prices, volumes, highs, lows, opens
            )
            
            # 2. 动量因子
            factor_scores['momentum'] = self._calculate_momentum_factors(prices, volumes)
            
            # 3. 价值因子 (简化版，实际需要财务数据)
            factor_scores['value'] = self._calculate_value_factors(stock_data)
            
            # 4. 质量因子 (简化版)
            factor_scores['quality'] = self._calculate_quality_factors(prices, volumes)
            
            # 5. 情绪因子
            factor_scores['sentiment'] = self._calculate_sentiment_factors(stock_data, market_data)
            
            # 计算综合得分
            total_score = sum(
                factor_scores[factor] * weight 
                for factor, weight in self.factor_weights.items()
                if factor in factor_scores
            )
            
            # 风险调整
            risk_score = self._calculate_risk_score(prices, volumes)
            adjusted_score = total_score * (1 - risk_score * 0.3)  # 风险折扣
            
            return {
                'total_score': adjusted_score,
                'factor_scores': factor_scores,
                'risk_score': risk_score,
                'current_price': prices.iloc[-1],
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"计算股票{stock_code}多因子得分失败: {e}")
            return None
    
    def _calculate_technical_factors(self, prices: pd.Series, volumes: pd.Series,
                                   highs: pd.Series, lows: pd.Series, opens: pd.Series) -> float:
        """
        计算技术因子得分
        
        Args:
            prices: 收盘价序列
            volumes: 成交量序列
            highs: 最高价序列
            lows: 最低价序列
            opens: 开盘价序列
            
        Returns:
            float: 技术因子得分 (0-100)
        """
        scores = []
        
        try:
            # RSI指标
            rsi = calculate_rsi(prices, 14)
            if len(rsi) > 0:
                current_rsi = rsi.iloc[-1]
                if 30 <= current_rsi <= 70:
                    rsi_score = 70 + (50 - abs(current_rsi - 50)) * 0.6
                else:
                    rsi_score = max(0, 100 - abs(current_rsi - 50) * 2)
                scores.append(rsi_score)
            
            # MACD指标
            macd_line, signal_line, histogram = calculate_macd(prices)
            if len(histogram) > 1:
                macd_cross = histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0
                macd_score = 80 if macd_cross else 50
                scores.append(macd_score)
            
            # 布林带位置
            bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices, 20)
            if len(bb_upper) > 0:
                current_price = prices.iloc[-1]
                bb_width = bb_upper.iloc[-1] - bb_lower.iloc[-1]
                if bb_width > 0:
                    bb_position = (current_price - bb_lower.iloc[-1]) / bb_width
                    bb_score = 50 + (0.5 - abs(bb_position - 0.5)) * 100
                    scores.append(bb_score)
            
            # 移动平均趋势
            sma_short = calculate_sma(prices, 10)
            sma_long = calculate_sma(prices, 20)
            if len(sma_short) > 0 and len(sma_long) > 0:
                ma_trend = (sma_short.iloc[-1] - sma_long.iloc[-1]) / sma_long.iloc[-1]
                ma_score = 50 + ma_trend * 1000
                scores.append(max(0, min(100, ma_score)))
            
            # ATR相对位置
            atr = calculate_atr(highs, lows, prices, 14)
            if len(atr) > 1:
                atr_ratio = atr.iloc[-1] / atr.mean()
                atr_score = 50 + (1 - atr_ratio) * 30  # ATR较低时得分较高
                scores.append(max(0, min(100, atr_score)))
                
        except Exception as e:
            print(f"计算技术因子失败: {e}")
        
        return np.mean(scores) if scores else 50
    
    def _calculate_momentum_factors(self, prices: pd.Series, volumes: pd.Series) -> float:
        """
        计算动量因子得分
        
        Args:
            prices: 价格序列
            volumes: 成交量序列
            
        Returns:
            float: 动量因子得分 (0-100)
        """
        scores = []
        
        try:
            # 短期动量
            short_momentum = calculate_momentum(prices, self.lookback_periods['short'])
            if len(short_momentum) > 0:
                short_mom_score = 50 + short_momentum.iloc[-1] * 2000
                scores.append(max(0, min(100, short_mom_score)))
            
            # 中期动量
            medium_momentum = calculate_momentum(prices, self.lookback_periods['medium'])
            if len(medium_momentum) > 0:
                med_mom_score = 50 + medium_momentum.iloc[-1] * 1000
                scores.append(max(0, min(100, med_mom_score)))
            
            # 长期动量
            long_momentum = calculate_momentum(prices, self.lookback_periods['long'])
            if len(long_momentum) > 0:
                long_mom_score = 50 + long_momentum.iloc[-1] * 500
                scores.append(max(0, min(100, long_mom_score)))
            
            # 成交量动量
            volume_sma = calculate_volume_sma(volumes, 20)
            if len(volume_sma) > 0:
                volume_momentum = (volumes.iloc[-1] - volume_sma.iloc[-1]) / volume_sma.iloc[-1]
                vol_mom_score = 50 + volume_momentum * 50
                scores.append(max(0, min(100, vol_mom_score)))
                
        except Exception as e:
            print(f"计算动量因子失败: {e}")
        
        return np.mean(scores) if scores else 50
    
    def _calculate_value_factors(self, stock_data: Dict) -> float:
        """
        计算价值因子得分（简化版）
        
        Args:
            stock_data: 股票数据
            
        Returns:
            float: 价值因子得分 (0-100)
        """
        try:
            # 在实际应用中，这里应该使用PE、PB、PS等估值指标
            # 现在用简化的价格相关指标代替
            
            quote_data = stock_data.get('quote', {})
            pe_ratio = quote_data.get('pe_ratio', 20)  # 默认PE为20
            pb_ratio = quote_data.get('pb_ratio', 2)   # 默认PB为2
            
            # PE评分 (越低越好)
            pe_score = max(0, 100 - pe_ratio * 2) if pe_ratio > 0 else 50
            
            # PB评分 (越低越好)  
            pb_score = max(0, 100 - pb_ratio * 20) if pb_ratio > 0 else 50
            
            return (pe_score + pb_score) / 2
            
        except Exception as e:
            print(f"计算价值因子失败: {e}")
            return 50
    
    def _calculate_quality_factors(self, prices: pd.Series, volumes: pd.Series) -> float:
        """
        计算质量因子得分（简化版）
        
        Args:
            prices: 价格序列
            volumes: 成交量序列
            
        Returns:
            float: 质量因子得分 (0-100)
        """
        scores = []
        
        try:
            # 价格稳定性（波动率的倒数）
            returns = prices.pct_change().dropna()
            if len(returns) > 10:
                volatility = returns.std()
                stability_score = max(0, 100 - volatility * 1000)
                scores.append(stability_score)
            
            # 流动性质量
            if len(volumes) > 20:
                volume_stability = 1 - (volumes.std() / volumes.mean())
                liquidity_score = volume_stability * 100
                scores.append(max(0, min(100, liquidity_score)))
            
            # 趋势一致性
            if len(prices) > 20:
                short_trend = calculate_sma(prices, 5)
                long_trend = calculate_sma(prices, 20)
                if len(short_trend) > 0 and len(long_trend) > 0:
                    trend_consistency = 1 - abs((short_trend.iloc[-1] - long_trend.iloc[-1]) / long_trend.iloc[-1])
                    consistency_score = trend_consistency * 100
                    scores.append(max(0, min(100, consistency_score)))
                    
        except Exception as e:
            print(f"计算质量因子失败: {e}")
        
        return np.mean(scores) if scores else 50
    
    def _calculate_sentiment_factors(self, stock_data: Dict, market_data: Dict) -> float:
        """
        计算情绪因子得分（简化版）
        
        Args:
            stock_data: 股票数据
            market_data: 市场数据
            
        Returns:
            float: 情绪因子得分 (0-100)
        """
        try:
            # 在实际应用中，这里应该使用新闻情绪、社交媒体情绪等数据
            # 现在用市场技术指标代替
            
            # 市场整体情绪
            market_sentiment = market_data.get('sentiment_score', 50)
            
            # 个股相对市场表现
            kline_data = stock_data.get('kline', [])
            if len(kline_data) > 5:
                df = pd.DataFrame(kline_data)
                prices = df['close'].astype(float)
                recent_return = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5]
                relative_performance = 50 + recent_return * 500
                relative_score = max(0, min(100, relative_performance))
            else:
                relative_score = 50
            
            # 综合情绪得分
            sentiment_score = (market_sentiment * 0.3 + relative_score * 0.7)
            
            return sentiment_score
            
        except Exception as e:
            print(f"计算情绪因子失败: {e}")
            return 50
    
    def _calculate_risk_score(self, prices: pd.Series, volumes: pd.Series) -> float:
        """
        计算风险得分
        
        Args:
            prices: 价格序列
            volumes: 成交量序列
            
        Returns:
            float: 风险得分 (0-1, 越高越有风险)
        """
        try:
            returns = prices.pct_change().dropna()
            if len(returns) < 10:
                return 0.5
                
            # 价格波动率风险
            volatility = returns.std() * np.sqrt(252)
            vol_risk = min(1, volatility / self.volatility_threshold)
            
            # 流动性风险
            volume_std = volumes.std()
            volume_mean = volumes.mean()
            liquidity_risk = volume_std / volume_mean if volume_mean > 0 else 1
            liquidity_risk = min(1, liquidity_risk)
            
            # 下行风险
            downside_returns = returns[returns < 0]
            downside_risk = downside_returns.std() if len(downside_returns) > 0 else 0
            downside_risk = min(1, downside_risk * 10)
            
            # 综合风险得分
            total_risk = (vol_risk * 0.4 + liquidity_risk * 0.3 + downside_risk * 0.3)
            
            return total_risk
            
        except Exception as e:
            print(f"计算风险得分失败: {e}")
            return 0.5
    
    def _generate_signals_from_scores(self, stock_scores: Dict[str, Dict]) -> List[Signal]:
        """
        基于因子得分生成交易信号
        
        Args:
            stock_scores: 股票得分字典
            
        Returns:
            List[Signal]: 交易信号列表
        """
        signals = []
        
        # 按得分排序
        sorted_stocks = sorted(
            stock_scores.items(),
            key=lambda x: x[1]['total_score'],
            reverse=True
        )
        
        for stock_code, score_info in sorted_stocks:
            total_score = score_info['total_score']
            risk_score = score_info['risk_score']
            current_price = score_info['current_price']
            
            # 确定信号类型和置信度
            if total_score >= self.signal_threshold['strong_buy']:
                signal_type = SignalType.BUY
                confidence = min(0.95, 0.8 + (total_score - 80) / 100)
            elif total_score >= self.signal_threshold['buy']:
                signal_type = SignalType.BUY
                confidence = min(0.8, 0.6 + (total_score - 60) / 100)
            elif total_score <= self.signal_threshold['sell']:
                signal_type = SignalType.SELL
                confidence = min(0.8, 0.6 + (40 - total_score) / 100)
            else:
                continue  # 持有信号暂时不生成
            
            # 风险调整置信度
            risk_adjusted_confidence = confidence * (1 - risk_score * 0.2)
            
            # 生成信号原因
            factor_scores = score_info['factor_scores']
            reason_parts = []
            for factor, score in factor_scores.items():
                if score > 70:
                    reason_parts.append(f"{factor}因子强({score:.0f})")
                elif score < 30:
                    reason_parts.append(f"{factor}因子弱({score:.0f})")
            
            reason = f"综合评分{total_score:.0f}分，" + "，".join(reason_parts[:3])
            
            signal = Signal(
                stock_code=stock_code,
                signal_type=signal_type,
                confidence=risk_adjusted_confidence,
                price=current_price,
                timestamp=datetime.now(),
                strategy="multi_factor",
                reason=reason,
                metadata={
                    'total_score': total_score,
                    'factor_scores': factor_scores,
                    'risk_score': risk_score,
                    'factor_weights': self.factor_weights
                }
            )
            
            signals.append(signal)
            
            # 限制信号数量
            if len(signals) >= 20:
                break
        
        return signals
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取策略参数"""
        return {
            'factor_weights': self.factor_weights,
            'lookback_periods': self.lookback_periods,
            'signal_threshold': self.signal_threshold,
            'max_position_weight': self.max_position_weight,
            'volatility_threshold': self.volatility_threshold
        }
    
    def update_parameters(self, **kwargs):
        """更新策略参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)