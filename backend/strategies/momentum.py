"""
动量策略 - Momentum Strategy
基于价格动量和成交量的交易信号生成
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncio

from models.signal import Signal, SignalType
from utils.indicators import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_volume_sma, calculate_atr
)


class MomentumStrategy:
    """动量策略实现"""
    
    def __init__(self):
        self.name = "动量策略"
        self.description = "基于价格动量和成交量突破的交易策略"
        self.lookback_period = 20
        self.rsi_period = 14
        self.volume_period = 20
        
        # 策略参数
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.momentum_threshold = 0.02  # 2%动量阈值
        self.volume_multiplier = 1.5   # 成交量放大倍数
        
    async def generate_signals(self, market_data: Dict[str, Any]) -> List[Signal]:
        """
        生成动量交易信号
        
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
            print(f"动量策略信号生成失败: {e}")
            
        return signals
    
    async def _analyze_stock(self, stock_code: str, stock_data: Dict) -> Signal:
        """
        分析单只股票并生成信号
        
        Args:
            stock_code: 股票代码
            stock_data: 股票数据
            
        Returns:
            Signal: 交易信号，如果没有信号则返回None
        """
        try:
            # 获取K线数据
            kline_data = stock_data.get('kline', [])
            if len(kline_data) < max(self.lookback_period, self.rsi_period):
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
            
            # RSI指标
            rsi = calculate_rsi(prices, self.rsi_period)
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # MACD指标
            macd_line, signal_line, histogram = calculate_macd(prices)
            macd_cross = len(histogram) > 1 and histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0
            
            # 价格动量
            price_momentum = (prices.iloc[-1] - prices.iloc[-self.lookback_period]) / prices.iloc[-self.lookback_period]
            
            # 成交量分析
            volume_sma = calculate_volume_sma(volumes, self.volume_period)
            current_volume = volumes.iloc[-1]
            avg_volume = volume_sma.iloc[-1] if len(volume_sma) > 0 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 布林带
            bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices, self.lookback_period)
            current_price = prices.iloc[-1]
            bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
            
            # 生成信号
            signal_type, confidence = self._determine_signal(
                current_rsi, macd_cross, price_momentum, volume_ratio, bb_position
            )
            
            if signal_type != SignalType.HOLD:
                return Signal(
                    stock_code=stock_code,
                    signal_type=signal_type,
                    confidence=confidence,
                    price=current_price,
                    timestamp=datetime.now(),
                    strategy="momentum",
                    reason=self._generate_reason(
                        current_rsi, price_momentum, volume_ratio, bb_position
                    ),
                    metadata={
                        'rsi': current_rsi,
                        'price_momentum': price_momentum,
                        'volume_ratio': volume_ratio,
                        'bb_position': bb_position,
                        'macd_cross': macd_cross
                    }
                )
                
        except Exception as e:
            print(f"分析股票{stock_code}失败: {e}")
            
        return None
    
    def _determine_signal(self, rsi: float, macd_cross: bool, momentum: float, 
                         volume_ratio: float, bb_position: float) -> tuple:
        """
        基于技术指标确定交易信号
        
        Args:
            rsi: RSI值
            macd_cross: MACD是否金叉
            momentum: 价格动量
            volume_ratio: 成交量比率
            bb_position: 布林带位置
            
        Returns:
            tuple: (信号类型, 置信度)
        """
        buy_score = 0
        sell_score = 0
        
        # RSI信号
        if rsi < self.rsi_oversold:
            buy_score += 2
        elif rsi > self.rsi_overbought:
            sell_score += 2
        elif 30 < rsi < 50:
            buy_score += 1
        elif 50 < rsi < 70:
            sell_score += 1
            
        # 动量信号
        if momentum > self.momentum_threshold:
            buy_score += 3
        elif momentum < -self.momentum_threshold:
            sell_score += 3
        elif momentum > 0:
            buy_score += 1
        else:
            sell_score += 1
            
        # MACD信号
        if macd_cross:
            buy_score += 2
            
        # 成交量确认
        if volume_ratio > self.volume_multiplier:
            if buy_score > sell_score:
                buy_score += 2
            else:
                sell_score += 2
                
        # 布林带信号
        if bb_position < 0.2:  # 接近下轨
            buy_score += 1
        elif bb_position > 0.8:  # 接近上轨
            sell_score += 1
            
        # 确定最终信号
        total_score = max(buy_score, sell_score)
        if total_score < 4:  # 信号不够强
            return SignalType.HOLD, 0.3
            
        if buy_score > sell_score:
            confidence = min(0.9, 0.5 + (buy_score - 4) * 0.1)
            return SignalType.BUY, confidence
        else:
            confidence = min(0.9, 0.5 + (sell_score - 4) * 0.1)
            return SignalType.SELL, confidence
    
    def _generate_reason(self, rsi: float, momentum: float, volume_ratio: float, 
                        bb_position: float) -> str:
        """
        生成信号原因描述
        
        Args:
            rsi: RSI值
            momentum: 价格动量
            volume_ratio: 成交量比率
            bb_position: 布林带位置
            
        Returns:
            str: 信号原因
        """
        reasons = []
        
        if momentum > self.momentum_threshold:
            reasons.append(f"价格动量强劲({momentum:.2%})")
        elif momentum < -self.momentum_threshold:
            reasons.append(f"价格动量疲弱({momentum:.2%})")
            
        if rsi < self.rsi_oversold:
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi > self.rsi_overbought:
            reasons.append(f"RSI超买({rsi:.1f})")
            
        if volume_ratio > self.volume_multiplier:
            reasons.append(f"成交量放大({volume_ratio:.1f}倍)")
            
        if bb_position < 0.2:
            reasons.append("接近布林带下轨")
        elif bb_position > 0.8:
            reasons.append("接近布林带上轨")
            
        return "，".join(reasons) if reasons else "技术指标综合判断"
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取策略参数"""
        return {
            'lookback_period': self.lookback_period,
            'rsi_period': self.rsi_period,
            'volume_period': self.volume_period,
            'rsi_oversold': self.rsi_oversold,
            'rsi_overbought': self.rsi_overbought,
            'momentum_threshold': self.momentum_threshold,
            'volume_multiplier': self.volume_multiplier
        }
    
    def update_parameters(self, **kwargs):
        """更新策略参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)