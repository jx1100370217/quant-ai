"""
均值回归策略 - Mean Reversion Strategy
基于价格偏离均值的回归特性进行交易
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncio

from models.signal import Signal, SignalType
from utils.indicators import (
    calculate_sma, calculate_ema, calculate_std, calculate_z_score,
    calculate_bollinger_bands, calculate_rsi
)


class MeanReversionStrategy:
    """均值回归策略实现"""
    
    def __init__(self):
        self.name = "均值回归策略"
        self.description = "基于价格偏离均值的回归特性的交易策略"
        
        # 策略参数
        self.lookback_period = 20
        self.z_score_threshold = 2.0  # Z-Score阈值
        self.bollinger_std = 2.0      # 布林带标准差倍数
        self.rsi_period = 14
        self.volume_period = 20
        
        # 信号确认参数
        self.min_reversal_confidence = 0.6
        self.max_holding_period = 10  # 最大持仓天数
        
    async def generate_signals(self, market_data: Dict[str, Any]) -> List[Signal]:
        """
        生成均值回归交易信号
        
        Args:
            market_data: 市场数据字典
            
        Returns:
            List[Signal]: 交易信号列表
        """
        signals = []
        
        try:
            stocks_data = market_data.get('stocks', {})
            
            for stock_code, stock_data in stocks_data.items():
                signal = await self._analyze_stock(stock_code, stock_data)
                if signal:
                    signals.append(signal)
                    
        except Exception as e:
            print(f"均值回归策略信号生成失败: {e}")
            
        return signals
    
    async def _analyze_stock(self, stock_code: str, stock_data: Dict) -> Signal:
        """
        分析单只股票并生成均值回归信号
        
        Args:
            stock_code: 股票代码
            stock_data: 股票数据
            
        Returns:
            Signal: 交易信号，如果没有信号则返回None
        """
        try:
            # 获取K线数据
            kline_data = stock_data.get('kline', [])
            if len(kline_data) < self.lookback_period + 10:
                return None
                
            # 转换为DataFrame
            df = pd.DataFrame(kline_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # 计算技术指标
            prices = df['close'].astype(float)
            volumes = df['volume'].astype(float)
            highs = df['high'].astype(float)
            lows = df['low'].astype(float)
            
            # 移动平均线
            sma_short = calculate_sma(prices, 10)
            sma_long = calculate_sma(prices, self.lookback_period)
            ema = calculate_ema(prices, self.lookback_period)
            
            # 价格偏离度分析
            current_price = prices.iloc[-1]
            mean_price = sma_long.iloc[-1] if len(sma_long) > 0 else current_price
            price_std = calculate_std(prices, self.lookback_period).iloc[-1]
            
            # Z-Score计算
            z_score = (current_price - mean_price) / price_std if price_std > 0 else 0
            
            # 布林带
            bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(
                prices, self.lookback_period, self.bollinger_std
            )
            
            # 布林带位置
            if len(bb_upper) > 0 and len(bb_lower) > 0:
                bb_width = bb_upper.iloc[-1] - bb_lower.iloc[-1]
                bb_position = (current_price - bb_lower.iloc[-1]) / bb_width if bb_width > 0 else 0.5
            else:
                bb_position = 0.5
            
            # RSI
            rsi = calculate_rsi(prices, self.rsi_period)
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # 价格趋势分析（用于确认回归信号）
            recent_trend = self._analyze_price_trend(prices)
            
            # 成交量分析
            volume_ratio = self._analyze_volume(volumes)
            
            # 波动率分析
            volatility = self._calculate_volatility(prices)
            
            # 生成信号
            signal_type, confidence = self._determine_mean_reversion_signal(
                z_score, bb_position, current_rsi, recent_trend, volume_ratio, volatility
            )
            
            if signal_type != SignalType.HOLD:
                return Signal(
                    stock_code=stock_code,
                    signal_type=signal_type,
                    confidence=confidence,
                    price=current_price,
                    timestamp=datetime.now(),
                    strategy="mean_reversion",
                    reason=self._generate_reason(
                        z_score, bb_position, current_rsi, recent_trend
                    ),
                    metadata={
                        'z_score': z_score,
                        'bb_position': bb_position,
                        'rsi': current_rsi,
                        'mean_price': mean_price,
                        'volatility': volatility,
                        'volume_ratio': volume_ratio,
                        'trend': recent_trend
                    }
                )
                
        except Exception as e:
            print(f"均值回归分析股票{stock_code}失败: {e}")
            
        return None
    
    def _analyze_price_trend(self, prices: pd.Series) -> str:
        """
        分析最近价格趋势
        
        Args:
            prices: 价格序列
            
        Returns:
            str: 趋势描述 ('up', 'down', 'sideways')
        """
        if len(prices) < 5:
            return 'sideways'
            
        recent_prices = prices.tail(5)
        first_price = recent_prices.iloc[0]
        last_price = recent_prices.iloc[-1]
        
        price_change = (last_price - first_price) / first_price
        
        if price_change > 0.02:
            return 'up'
        elif price_change < -0.02:
            return 'down'
        else:
            return 'sideways'
    
    def _analyze_volume(self, volumes: pd.Series) -> float:
        """
        分析成交量变化
        
        Args:
            volumes: 成交量序列
            
        Returns:
            float: 成交量比率
        """
        if len(volumes) < self.volume_period:
            return 1.0
            
        recent_volume = volumes.tail(3).mean()
        avg_volume = volumes.tail(self.volume_period).mean()
        
        return recent_volume / avg_volume if avg_volume > 0 else 1.0
    
    def _calculate_volatility(self, prices: pd.Series) -> float:
        """
        计算价格波动率
        
        Args:
            prices: 价格序列
            
        Returns:
            float: 波动率
        """
        if len(prices) < 10:
            return 0.0
            
        returns = prices.pct_change().dropna()
        return returns.std() * np.sqrt(252)  # 年化波动率
    
    def _determine_mean_reversion_signal(self, z_score: float, bb_position: float,
                                       rsi: float, trend: str, volume_ratio: float,
                                       volatility: float) -> tuple:
        """
        基于均值回归指标确定交易信号
        
        Args:
            z_score: Z分数
            bb_position: 布林带位置
            rsi: RSI值
            trend: 价格趋势
            volume_ratio: 成交量比率
            volatility: 波动率
            
        Returns:
            tuple: (信号类型, 置信度)
        """
        buy_score = 0
        sell_score = 0
        
        # Z-Score信号（核心逻辑）
        if z_score < -self.z_score_threshold:
            buy_score += 4  # 价格显著低于均值
        elif z_score > self.z_score_threshold:
            sell_score += 4  # 价格显著高于均值
        elif z_score < -1:
            buy_score += 2
        elif z_score > 1:
            sell_score += 2
            
        # 布林带信号
        if bb_position < 0.1:  # 触及或接近下轨
            buy_score += 3
        elif bb_position > 0.9:  # 触及或接近上轨
            sell_score += 3
        elif bb_position < 0.3:
            buy_score += 1
        elif bb_position > 0.7:
            sell_score += 1
            
        # RSI确认信号
        if rsi < 30:  # 超卖
            buy_score += 2
        elif rsi > 70:  # 超买
            sell_score += 2
        elif rsi < 40:
            buy_score += 1
        elif rsi > 60:
            sell_score += 1
            
        # 趋势确认（反向逻辑）
        if trend == 'down' and buy_score > 0:
            buy_score += 1  # 下跌趋势中的买入信号更可靠
        elif trend == 'up' and sell_score > 0:
            sell_score += 1  # 上涨趋势中的卖出信号更可靠
            
        # 成交量确认
        if volume_ratio > 1.2:  # 成交量放大
            if buy_score > sell_score:
                buy_score += 1
            else:
                sell_score += 1
                
        # 波动率调整
        if volatility > 0.3:  # 高波动率时提高阈值
            min_score = 6
        else:
            min_score = 5
            
        # 确定最终信号
        total_score = max(buy_score, sell_score)
        if total_score < min_score:
            return SignalType.HOLD, 0.3
            
        if buy_score > sell_score:
            confidence = min(0.95, 0.6 + (buy_score - min_score) * 0.1)
            return SignalType.BUY, confidence
        else:
            confidence = min(0.95, 0.6 + (sell_score - min_score) * 0.1)
            return SignalType.SELL, confidence
    
    def _generate_reason(self, z_score: float, bb_position: float, rsi: float, trend: str) -> str:
        """
        生成信号原因描述
        
        Args:
            z_score: Z分数
            bb_position: 布林带位置
            rsi: RSI值
            trend: 价格趋势
            
        Returns:
            str: 信号原因
        """
        reasons = []
        
        if abs(z_score) > self.z_score_threshold:
            direction = "低于" if z_score < 0 else "高于"
            reasons.append(f"价格显著{direction}均值(Z={z_score:.2f})")
        
        if bb_position < 0.2:
            reasons.append("接近布林带下轨")
        elif bb_position > 0.8:
            reasons.append("接近布林带上轨")
            
        if rsi < 30:
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi > 70:
            reasons.append(f"RSI超买({rsi:.1f})")
            
        if trend != 'sideways':
            reasons.append(f"价格趋势{trend}")
            
        return "，".join(reasons) if reasons else "均值回归信号"
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取策略参数"""
        return {
            'lookback_period': self.lookback_period,
            'z_score_threshold': self.z_score_threshold,
            'bollinger_std': self.bollinger_std,
            'rsi_period': self.rsi_period,
            'volume_period': self.volume_period,
            'min_reversal_confidence': self.min_reversal_confidence,
            'max_holding_period': self.max_holding_period
        }
    
    def update_parameters(self, **kwargs):
        """更新策略参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)