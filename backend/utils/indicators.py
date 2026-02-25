import numpy as np
import pandas as pd
from typing import Tuple, List

class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        """简单移动平均线"""
        if len(data) < period:
            return np.array([])
        return np.array(pd.Series(data).rolling(window=period).mean().dropna())
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均线"""
        if len(data) < period:
            return np.array([])
        return np.array(pd.Series(data).ewm(span=period, adjust=False).mean())
    
    @staticmethod
    def macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD指标"""
        if len(data) < slow:
            return np.array([]), np.array([]), np.array([])
            
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        if len(ema_fast) == 0 or len(ema_slow) == 0:
            return np.array([]), np.array([]), np.array([])
        
        # 对齐长度
        min_len = min(len(ema_fast), len(ema_slow))
        ema_fast = ema_fast[-min_len:]
        ema_slow = ema_slow[-min_len:]
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        
        if len(signal_line) == 0:
            return macd_line, np.array([]), np.array([])
            
        # 对齐MACD线和信号线
        min_len = min(len(macd_line), len(signal_line))
        macd_line = macd_line[-min_len:]
        signal_line = signal_line[-min_len:]
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        """相对强弱指标"""
        if len(data) < period + 1:
            return np.array([])
            
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = pd.Series(gains).rolling(window=period).mean()
        avg_losses = pd.Series(losses).rolling(window=period).mean()
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return np.array(rsi.dropna())
    
    @staticmethod
    def kdj(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
            k_period: int = 9, d_period: int = 3, j_period: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """KDJ指标"""
        if len(highs) < k_period or len(lows) < k_period or len(closes) < k_period:
            return np.array([]), np.array([]), np.array([])
            
        # 计算RSV（Raw Stochastic Value）
        lowest_lows = pd.Series(lows).rolling(window=k_period).min()
        highest_highs = pd.Series(highs).rolling(window=k_period).max()
        
        rsv = (closes - lowest_lows) / (highest_highs - lowest_lows) * 100
        rsv = rsv.fillna(50)  # 填充NaN值
        
        # 计算K值
        k_values = []
        k = 50  # K的初始值
        for rsv_val in rsv:
            if not np.isnan(rsv_val):
                k = (2/3) * k + (1/3) * rsv_val
                k_values.append(k)
            else:
                k_values.append(k)
                
        k_series = pd.Series(k_values)
        
        # 计算D值
        d_values = []
        d = 50  # D的初始值
        for k_val in k_values:
            d = (2/3) * d + (1/3) * k_val
            d_values.append(d)
            
        d_series = pd.Series(d_values)
        
        # 计算J值
        j_series = 3 * k_series - 2 * d_series
        
        # 截取有效数据
        valid_start = k_period - 1
        return (np.array(k_series[valid_start:]), 
                np.array(d_series[valid_start:]), 
                np.array(j_series[valid_start:]))
    
    @staticmethod
    def bollinger_bands(data: np.ndarray, period: int = 20, std_dev: float = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """布林带"""
        if len(data) < period:
            return np.array([]), np.array([]), np.array([])
            
        sma = TechnicalIndicators.sma(data, period)
        if len(sma) == 0:
            return np.array([]), np.array([]), np.array([])
            
        # 计算标准差
        rolling_std = pd.Series(data).rolling(window=period).std().dropna()
        
        # 对齐长度
        min_len = min(len(sma), len(rolling_std))
        sma = sma[-min_len:]
        rolling_std = np.array(rolling_std[-min_len:])
        
        upper_band = sma + (rolling_std * std_dev)
        lower_band = sma - (rolling_std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """平均真实范围"""
        if len(highs) < 2 or len(lows) < 2 or len(closes) < 2:
            return np.array([])
            
        # 计算真实范围
        true_ranges = []
        for i in range(1, len(closes)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
            
        if len(true_ranges) < period:
            return np.array([])
            
        # 计算ATR
        atr_values = pd.Series(true_ranges).rolling(window=period).mean().dropna()
        return np.array(atr_values)
    
    @staticmethod
    def cci(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
        """商品通道指数"""
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return np.array([])
            
        # 计算典型价格
        typical_prices = (highs + lows + closes) / 3
        
        # 计算移动平均
        sma_tp = TechnicalIndicators.sma(typical_prices, period)
        if len(sma_tp) == 0:
            return np.array([])
            
        # 计算平均绝对偏差
        mad_values = []
        for i in range(len(sma_tp)):
            start_idx = i + len(typical_prices) - len(sma_tp)
            end_idx = start_idx + period
            if end_idx <= len(typical_prices):
                period_data = typical_prices[start_idx:end_idx]
                mad = np.mean(np.abs(period_data - sma_tp[i]))
                mad_values.append(mad)
        
        mad_array = np.array(mad_values)
        
        # 计算CCI
        if len(mad_array) > 0:
            # 对齐数组长度
            min_len = min(len(sma_tp), len(mad_array))
            sma_tp = sma_tp[-min_len:]
            mad_array = mad_array[-min_len:]
            typical_prices_aligned = typical_prices[-(min_len):]
            
            cci = (typical_prices_aligned - sma_tp) / (0.015 * mad_array)
            return cci
        
        return np.array([])
    
    @staticmethod
    def stochastic(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
                   k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """随机指标"""
        if len(highs) < k_period or len(lows) < k_period or len(closes) < k_period:
            return np.array([]), np.array([])
            
        # 计算%K
        lowest_lows = pd.Series(lows).rolling(window=k_period).min()
        highest_highs = pd.Series(highs).rolling(window=k_period).max()
        
        k_percent = ((closes - lowest_lows) / (highest_highs - lowest_lows)) * 100
        k_percent = k_percent.dropna()
        
        if len(k_percent) < d_period:
            return np.array(k_percent), np.array([])
            
        # 计算%D
        d_percent = k_percent.rolling(window=d_period).mean().dropna()
        
        # 对齐长度
        min_len = min(len(k_percent), len(d_percent))
        k_percent = k_percent[-min_len:]
        d_percent = d_percent[-min_len:]
        
        return np.array(k_percent), np.array(d_percent)
    
    @staticmethod
    def williams_r(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """威廉指标"""
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return np.array([])
            
        highest_highs = pd.Series(highs).rolling(window=period).max()
        lowest_lows = pd.Series(lows).rolling(window=period).min()
        
        wr = ((highest_highs - closes) / (highest_highs - lowest_lows)) * -100
        
        return np.array(wr.dropna())
    
    @staticmethod
    def obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """能量潮指标"""
        if len(closes) != len(volumes) or len(closes) < 2:
            return np.array([])
            
        obv_values = [volumes[0]]  # 第一天的OBV等于成交量
        
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv_values.append(obv_values[-1] + volumes[i])
            elif closes[i] < closes[i-1]:
                obv_values.append(obv_values[-1] - volumes[i])
            else:
                obv_values.append(obv_values[-1])
                
        return np.array(obv_values)


# ============================================================
# 模块级便捷函数 - 供 strategies 等模块直接导入使用
# ============================================================

def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均线"""
    return TechnicalIndicators.sma(data, period)

def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均线"""
    return TechnicalIndicators.ema(data, period)

def calculate_macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD指标"""
    return TechnicalIndicators.macd(data, fast, slow, signal)

def calculate_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指标"""
    return TechnicalIndicators.rsi(data, period)

def calculate_bollinger_bands(data: np.ndarray, period: int = 20, std_dev: float = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """布林带"""
    return TechnicalIndicators.bollinger_bands(data, period, std_dev)

def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    """平均真实范围"""
    return TechnicalIndicators.atr(highs, lows, closes, period)

def calculate_std(data: np.ndarray, period: int) -> np.ndarray:
    """滚动标准差"""
    if len(data) < period:
        return np.array([])
    return np.array(pd.Series(data).rolling(window=period).std().dropna())

def calculate_z_score(data: np.ndarray, period: int) -> np.ndarray:
    """Z-Score 标准分"""
    sma = calculate_sma(data, period)
    std = calculate_std(data, period)
    if len(sma) == 0 or len(std) == 0:
        return np.array([])
    min_len = min(len(sma), len(std))
    sma = sma[-min_len:]
    std = std[-min_len:]
    data_aligned = data[-min_len:]
    # 避免除零
    std = np.where(std == 0, 1e-10, std)
    return (data_aligned - sma) / std

def calculate_momentum(data: np.ndarray, period: int = 10) -> np.ndarray:
    """动量指标 (当前价格 / N日前价格 - 1)"""
    if len(data) <= period:
        return np.array([])
    return (data[period:] / data[:-period]) - 1

def calculate_volume_sma(volumes: np.ndarray, period: int) -> np.ndarray:
    """成交量简单移动平均"""
    return calculate_sma(volumes, period)