"""
工具函数集合
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import re
import hashlib
from decimal import Decimal, ROUND_HALF_UP


def format_number(num: float, precision: int = 2, percentage: bool = False) -> str:
    """
    格式化数字显示
    
    Args:
        num: 数字
        precision: 精度
        percentage: 是否为百分比
        
    Returns:
        str: 格式化后的字符串
    """
    if num is None or pd.isna(num):
        return "N/A"
    
    try:
        if percentage:
            return f"{num * 100:.{precision}f}%"
        
        if abs(num) >= 1e8:  # 亿
            return f"{num / 1e8:.{precision}f}亿"
        elif abs(num) >= 1e4:  # 万
            return f"{num / 1e4:.{precision}f}万"
        else:
            return f"{num:.{precision}f}"
    except:
        return str(num)


def format_currency(amount: float, currency: str = "¥") -> str:
    """
    格式化货币显示
    
    Args:
        amount: 金额
        currency: 货币符号
        
    Returns:
        str: 格式化后的货币字符串
    """
    if amount is None or pd.isna(amount):
        return f"{currency}0.00"
    
    try:
        formatted_amount = format_number(amount, 2)
        return f"{currency}{formatted_amount}"
    except:
        return f"{currency}{amount}"


def calculate_returns(prices: Union[List[float], pd.Series], periods: int = 1) -> pd.Series:
    """
    计算收益率
    
    Args:
        prices: 价格序列
        periods: 计算周期
        
    Returns:
        pd.Series: 收益率序列
    """
    if isinstance(prices, list):
        prices = pd.Series(prices)
    
    if len(prices) < periods + 1:
        return pd.Series(dtype=float)
    
    return prices.pct_change(periods=periods)


def calculate_cumulative_returns(returns: Union[List[float], pd.Series]) -> pd.Series:
    """
    计算累计收益率
    
    Args:
        returns: 收益率序列
        
    Returns:
        pd.Series: 累计收益率序列
    """
    if isinstance(returns, list):
        returns = pd.Series(returns)
    
    return (1 + returns).cumprod() - 1


def calculate_sharpe_ratio(returns: Union[List[float], pd.Series], 
                          risk_free_rate: float = 0.03) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率
        
    Returns:
        float: 夏普比率
    """
    if isinstance(returns, list):
        returns = pd.Series(returns)
    
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252  # 日收益率
    
    if excess_returns.std() == 0:
        return 0.0
    
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)


def calculate_max_drawdown(returns: Union[List[float], pd.Series]) -> float:
    """
    计算最大回撤
    
    Args:
        returns: 收益率序列
        
    Returns:
        float: 最大回撤
    """
    if isinstance(returns, list):
        returns = pd.Series(returns)
    
    if len(returns) == 0:
        return 0.0
    
    cumulative = calculate_cumulative_returns(returns)
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / (1 + running_max)
    
    return drawdown.min()


def get_trading_dates(start_date: datetime, end_date: datetime, 
                     exclude_weekends: bool = True) -> List[datetime]:
    """
    获取交易日期列表
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        exclude_weekends: 是否排除周末
        
    Returns:
        List[datetime]: 交易日期列表
    """
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        if exclude_weekends and current_date.weekday() >= 5:  # 周六、周日
            current_date += timedelta(days=1)
            continue
        
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    return dates


def is_trading_time(check_time: Optional[datetime] = None) -> bool:
    """
    检查是否为交易时间
    
    Args:
        check_time: 检查时间，默认为当前时间
        
    Returns:
        bool: 是否为交易时间
    """
    if check_time is None:
        check_time = datetime.now()
    
    # 排除周末
    if check_time.weekday() >= 5:
        return False
    
    current_time = check_time.time()
    
    # A股交易时间：9:30-11:30, 13:00-15:00
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    
    return (morning_start <= current_time <= morning_end or 
            afternoon_start <= current_time <= afternoon_end)


def parse_stock_code(code: str) -> Dict[str, str]:
    """
    解析股票代码
    
    Args:
        code: 股票代码
        
    Returns:
        Dict[str, str]: 解析结果
    """
    # 清理代码
    code = code.upper().strip()
    
    # 提取数字部分和后缀
    match = re.match(r'(\d{6})\.?([A-Z]{0,2})', code)
    if not match:
        return {'code': code, 'market': 'unknown', 'type': 'unknown'}
    
    number, suffix = match.groups()
    
    # 判断市场
    if suffix in ['SH', 'SS']:
        market = '上交所'
    elif suffix in ['SZ']:
        market = '深交所'
    elif code.startswith('688'):
        market = '科创板'
    elif code.startswith('300'):
        market = '创业板'
    elif code.startswith(('000', '002')):
        market = '深主板'
    elif code.startswith(('600', '601', '603')):
        market = '沪主板'
    else:
        market = '未知'
    
    # 判断类型
    if code.startswith('688'):
        stock_type = '科创板'
    elif code.startswith('300'):
        stock_type = '创业板'
    elif code.startswith(('000', '002', '600', '601', '603')):
        stock_type = 'A股'
    elif code.startswith('4'):
        stock_type = '新三板'
    else:
        stock_type = '其他'
    
    return {
        'code': f"{number}.{suffix}" if suffix else number,
        'number': number,
        'suffix': suffix,
        'market': market,
        'type': stock_type
    }


def validate_price_data(data: Dict[str, Any]) -> bool:
    """
    验证价格数据完整性
    
    Args:
        data: 价格数据
        
    Returns:
        bool: 数据是否有效
    """
    required_fields = ['open', 'high', 'low', 'close', 'volume']
    
    for field in required_fields:
        if field not in data:
            return False
        
        value = data[field]
        if value is None or pd.isna(value) or value < 0:
            return False
        
        # 价格逻辑检查
        if field in ['open', 'high', 'low', 'close'] and value <= 0:
            return False
    
    # OHLC逻辑检查
    try:
        o, h, l, c = data['open'], data['high'], data['low'], data['close']
        if not (l <= o <= h and l <= c <= h):
            return False
    except:
        return False
    
    return True


def clean_financial_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理财务数据
    
    Args:
        data: 原始财务数据
        
    Returns:
        Dict[str, Any]: 清理后的数据
    """
    cleaned = {}
    
    for key, value in data.items():
        if value is None or value == '':
            cleaned[key] = None
            continue
        
        # 处理字符串数字
        if isinstance(value, str):
            try:
                # 移除常见的非数字字符
                clean_value = re.sub(r'[,\s%]', '', value)
                if clean_value.replace('.', '').replace('-', '').isdigit():
                    cleaned[key] = float(clean_value)
                else:
                    cleaned[key] = value
            except:
                cleaned[key] = value
        else:
            cleaned[key] = value
    
    return cleaned


def calculate_technical_indicator_signals(indicators: Dict[str, float]) -> Dict[str, str]:
    """
    基于技术指标计算信号
    
    Args:
        indicators: 技术指标字典
        
    Returns:
        Dict[str, str]: 信号字典
    """
    signals = {}
    
    # RSI信号
    rsi = indicators.get('rsi')
    if rsi:
        if rsi < 30:
            signals['rsi'] = 'buy'
        elif rsi > 70:
            signals['rsi'] = 'sell'
        else:
            signals['rsi'] = 'neutral'
    
    # MACD信号
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    if macd and macd_signal:
        if macd > macd_signal:
            signals['macd'] = 'buy'
        else:
            signals['macd'] = 'sell'
    
    # 布林带信号
    bb_position = indicators.get('bb_position')
    if bb_position:
        if bb_position < 0.2:
            signals['bollinger'] = 'buy'
        elif bb_position > 0.8:
            signals['bollinger'] = 'sell'
        else:
            signals['bollinger'] = 'neutral'
    
    return signals


def generate_hash(data: Any) -> str:
    """
    生成数据哈希值
    
    Args:
        data: 任意数据
        
    Returns:
        str: 哈希值
    """
    if isinstance(data, dict):
        data_str = json.dumps(data, sort_keys=True)
    else:
        data_str = str(data)
    
    return hashlib.md5(data_str.encode()).hexdigest()


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 默认值
        
    Returns:
        float: 除法结果
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except:
        return default


def round_to_tick(price: float, tick_size: float = 0.01) -> float:
    """
    按最小变动单位四舍五入
    
    Args:
        price: 价格
        tick_size: 最小变动单位
        
    Returns:
        float: 四舍五入后的价格
    """
    try:
        decimal_price = Decimal(str(price))
        decimal_tick = Decimal(str(tick_size))
        rounded = (decimal_price / decimal_tick).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        ) * decimal_tick
        return float(rounded)
    except:
        return price


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    深度合并字典
    
    Args:
        dict1: 字典1
        dict2: 字典2
        
    Returns:
        Dict: 合并后的字典
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def calculate_position_size(account_value: float, risk_per_trade: float, 
                          entry_price: float, stop_loss: float) -> int:
    """
    计算仓位大小
    
    Args:
        account_value: 账户价值
        risk_per_trade: 单次交易风险比例
        entry_price: 入场价格
        stop_loss: 止损价格
        
    Returns:
        int: 仓位大小（股数）
    """
    try:
        risk_amount = account_value * risk_per_trade
        price_diff = abs(entry_price - stop_loss)
        
        if price_diff == 0:
            return 0
        
        position_value = risk_amount / (price_diff / entry_price)
        shares = int(position_value / entry_price / 100) * 100  # 按手计算
        
        return max(0, shares)
    except:
        return 0


def format_timespan(seconds: int) -> str:
    """
    格式化时间跨度
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}天{hours}小时"


def get_color_by_value(value: float, positive_color: str = "green", 
                      negative_color: str = "red", neutral_color: str = "gray") -> str:
    """
    根据数值获取颜色
    
    Args:
        value: 数值
        positive_color: 正数颜色
        negative_color: 负数颜色
        neutral_color: 零值颜色
        
    Returns:
        str: 颜色名称
    """
    if value > 0:
        return positive_color
    elif value < 0:
        return negative_color
    else:
        return neutral_color