"""
交易信号模型
"""
from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json


class SignalType(Enum):
    """信号类型枚举"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalPriority(Enum):
    """信号优先级枚举"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Signal:
    """交易信号模型"""
    stock_code: str                    # 股票代码
    signal_type: SignalType           # 信号类型
    confidence: float                 # 置信度 (0-1)
    price: float                      # 信号价格
    timestamp: datetime               # 信号时间
    strategy: str                     # 策略名称
    reason: str                       # 信号原因
    metadata: Optional[Dict[str, Any]] = None  # 附加元数据
    priority: SignalPriority = SignalPriority.MEDIUM  # 信号优先级
    target_price: Optional[float] = None  # 目标价格
    stop_loss: Optional[float] = None     # 止损价格
    valid_until: Optional[datetime] = None # 信号有效期
    executed: bool = False                # 是否已执行
    execution_price: Optional[float] = None # 执行价格
    execution_time: Optional[datetime] = None # 执行时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        
        # 处理枚举类型
        result['signal_type'] = self.signal_type.value
        result['priority'] = self.priority.value
        
        # 处理日期时间
        result['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        result['valid_until'] = self.valid_until.isoformat() if self.valid_until else None
        result['execution_time'] = self.execution_time.isoformat() if self.execution_time else None
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """从字典创建信号对象"""
        # 处理枚举类型
        if 'signal_type' in data and isinstance(data['signal_type'], str):
            data['signal_type'] = SignalType(data['signal_type'])
        
        if 'priority' in data and isinstance(data['priority'], (int, str)):
            data['priority'] = SignalPriority(data['priority'])
        
        # 处理日期时间
        datetime_fields = ['timestamp', 'valid_until', 'execution_time']
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
        
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Signal':
        """从JSON字符串创建信号对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def is_valid(self) -> bool:
        """检查信号是否仍然有效"""
        if self.executed:
            return False
        
        if self.valid_until and datetime.now() > self.valid_until:
            return False
        
        return True
    
    def execute(self, execution_price: float, execution_time: Optional[datetime] = None):
        """标记信号为已执行"""
        self.executed = True
        self.execution_price = execution_price
        self.execution_time = execution_time or datetime.now()
    
    def calculate_profit_loss(self, current_price: float) -> Optional[float]:
        """计算盈亏"""
        if not self.executed or not self.execution_price:
            return None
        
        if self.signal_type == SignalType.BUY:
            return (current_price - self.execution_price) / self.execution_price
        elif self.signal_type == SignalType.SELL:
            return (self.execution_price - current_price) / self.execution_price
        
        return None
    
    def should_stop_loss(self, current_price: float) -> bool:
        """检查是否触发止损"""
        if not self.stop_loss or not self.executed:
            return False
        
        if self.signal_type == SignalType.BUY and current_price <= self.stop_loss:
            return True
        elif self.signal_type == SignalType.SELL and current_price >= self.stop_loss:
            return True
        
        return False
    
    def should_take_profit(self, current_price: float) -> bool:
        """检查是否触发止盈"""
        if not self.target_price or not self.executed:
            return False
        
        if self.signal_type == SignalType.BUY and current_price >= self.target_price:
            return True
        elif self.signal_type == SignalType.SELL and current_price <= self.target_price:
            return True
        
        return False
    
    def get_confidence_level(self) -> str:
        """获取置信度级别"""
        if self.confidence >= 0.8:
            return "高"
        elif self.confidence >= 0.6:
            return "中"
        elif self.confidence >= 0.4:
            return "低"
        else:
            return "极低"
    
    def get_risk_level(self) -> str:
        """获取风险级别"""
        risk_score = self.metadata.get('risk_score', 0.5) if self.metadata else 0.5
        
        if risk_score >= 0.8:
            return "高风险"
        elif risk_score >= 0.6:
            return "中高风险"
        elif risk_score >= 0.4:
            return "中等风险"
        elif risk_score >= 0.2:
            return "低风险"
        else:
            return "极低风险"
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"Signal({self.stock_code}, {self.signal_type.value}, "
                f"confidence={self.confidence:.2f}, price={self.price:.2f}, "
                f"strategy={self.strategy})")
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return self.__str__()


class SignalManager:
    """信号管理器"""
    
    def __init__(self):
        self.signals: Dict[str, List[Signal]] = {}  # 按股票代码分组的信号
        self.signal_history: List[Signal] = []      # 历史信号记录
    
    def add_signal(self, signal: Signal):
        """添加信号"""
        stock_code = signal.stock_code
        
        if stock_code not in self.signals:
            self.signals[stock_code] = []
        
        self.signals[stock_code].append(signal)
        self.signal_history.append(signal)
    
    def get_active_signals(self, stock_code: Optional[str] = None) -> List[Signal]:
        """获取活跃信号"""
        if stock_code:
            return [s for s in self.signals.get(stock_code, []) if s.is_valid()]
        else:
            active_signals = []
            for signals in self.signals.values():
                active_signals.extend([s for s in signals if s.is_valid()])
            return active_signals
    
    def get_signals_by_strategy(self, strategy: str) -> List[Signal]:
        """按策略获取信号"""
        return [s for s in self.signal_history if s.strategy == strategy]
    
    def get_signals_by_type(self, signal_type: SignalType) -> List[Signal]:
        """按类型获取信号"""
        return [s for s in self.signal_history if s.signal_type == signal_type]
    
    def get_high_confidence_signals(self, min_confidence: float = 0.8) -> List[Signal]:
        """获取高置信度信号"""
        return [s for s in self.get_active_signals() if s.confidence >= min_confidence]
    
    def execute_signal(self, signal: Signal, execution_price: float):
        """执行信号"""
        signal.execute(execution_price)
    
    def cleanup_expired_signals(self):
        """清理过期信号"""
        for stock_code in self.signals:
            self.signals[stock_code] = [
                s for s in self.signals[stock_code] if s.is_valid()
            ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取信号统计"""
        all_signals = self.signal_history
        active_signals = self.get_active_signals()
        executed_signals = [s for s in all_signals if s.executed]
        
        # 按策略统计
        strategy_stats = {}
        for signal in all_signals:
            strategy = signal.strategy
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'total': 0,
                    'buy': 0,
                    'sell': 0,
                    'executed': 0,
                    'avg_confidence': 0
                }
            
            stats = strategy_stats[strategy]
            stats['total'] += 1
            stats['avg_confidence'] += signal.confidence
            
            if signal.signal_type == SignalType.BUY:
                stats['buy'] += 1
            elif signal.signal_type == SignalType.SELL:
                stats['sell'] += 1
            
            if signal.executed:
                stats['executed'] += 1
        
        # 计算平均置信度
        for stats in strategy_stats.values():
            if stats['total'] > 0:
                stats['avg_confidence'] /= stats['total']
        
        return {
            'total_signals': len(all_signals),
            'active_signals': len(active_signals),
            'executed_signals': len(executed_signals),
            'execution_rate': len(executed_signals) / len(all_signals) if all_signals else 0,
            'strategy_breakdown': strategy_stats,
            'signal_types': {
                'buy': len([s for s in all_signals if s.signal_type == SignalType.BUY]),
                'sell': len([s for s in all_signals if s.signal_type == SignalType.SELL]),
                'hold': len([s for s in all_signals if s.signal_type == SignalType.HOLD])
            }
        }