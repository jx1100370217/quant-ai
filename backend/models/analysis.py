"""
分析结果模型
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
import json
import numpy as np

from .signal import Signal, SignalType


@dataclass
class AnalysisResult:
    """单个分析师的分析结果"""
    agent_name: str                    # 分析师名称
    analysis_type: str                 # 分析类型
    summary: str                       # 分析摘要
    signal: SignalType                 # 推荐信号
    confidence: float                  # 置信度 (0-1)
    reasoning: List[str]               # 分析逻辑
    timestamp: datetime                # 分析时间
    metadata: Optional[Dict[str, Any]] = None  # 附加数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['signal'] = self.signal.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class MarketAnalysis:
    """市场分析结果"""
    market_trend: str                  # 市场趋势
    market_sentiment: float            # 市场情绪 (0-1)
    major_indices: Dict[str, Dict]     # 主要指数数据
    sector_performance: Dict[str, float] # 板块表现
    volatility_index: float            # 波动率指数
    risk_level: str                    # 风险等级
    key_factors: List[str]             # 关键因素
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class Analysis:
    """完整的分析结果"""
    timestamp: datetime                # 分析时间
    analyses: Dict[str, Any]           # 各分析师结果
    signals: List[Signal]              # 生成的信号
    market_data: Dict[str, Any]        # 市场数据快照
    portfolio_decision: Optional[Dict] = None  # 投资组合决策
    risk_assessment: Optional[Dict] = None     # 风险评估
    execution_plan: Optional[Dict] = None      # 执行计划
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'timestamp': self.timestamp.isoformat(),
            'analyses': self.analyses,
            'signals': [signal.to_dict() for signal in self.signals],
            'market_data': self.market_data,
            'portfolio_decision': self.portfolio_decision,
            'risk_assessment': self.risk_assessment,
            'execution_plan': self.execution_plan
        }
        return result
    
    def get_consensus_signal(self) -> tuple[SignalType, float]:
        """获取一致性信号"""
        buy_score = 0
        sell_score = 0
        total_confidence = 0
        
        for agent_result in self.analyses.values():
            if isinstance(agent_result, dict):
                signal = agent_result.get('signal', 'HOLD')
                confidence = agent_result.get('confidence', 0.5)
                
                total_confidence += confidence
                
                if signal == 'BUY':
                    buy_score += confidence
                elif signal == 'SELL':
                    sell_score += confidence
        
        if buy_score > sell_score and buy_score > 0.6:
            return SignalType.BUY, buy_score / len(self.analyses)
        elif sell_score > buy_score and sell_score > 0.6:
            return SignalType.SELL, sell_score / len(self.analyses)
        else:
            return SignalType.HOLD, total_confidence / len(self.analyses) if self.analyses else 0.5


class AnalysisManager:
    """分析管理器"""
    
    def __init__(self):
        self.analysis_history: List[Analysis] = []
        self.performance_metrics: Dict[str, Dict] = {}
    
    def add_analysis(self, analysis: Analysis):
        """添加分析结果"""
        self.analysis_history.append(analysis)
        self._update_performance_metrics(analysis)
    
    def get_latest_analysis(self) -> Optional[Analysis]:
        """获取最新分析"""
        return self.analysis_history[-1] if self.analysis_history else None
    
    def get_analysis_by_timeframe(self, hours: int) -> List[Analysis]:
        """获取指定时间范围内的分析"""
        cutoff_time = datetime.now().replace(microsecond=0) - timedelta(hours=hours)
        return [
            analysis for analysis in self.analysis_history 
            if analysis.timestamp >= cutoff_time
        ]
    
    def get_agent_performance(self, agent_name: str) -> Dict[str, Any]:
        """获取指定分析师的表现"""
        return self.performance_metrics.get(agent_name, {
            'total_analyses': 0,
            'accuracy': 0.0,
            'avg_confidence': 0.0,
            'signal_distribution': {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        })
    
    def _update_performance_metrics(self, analysis: Analysis):
        """更新表现指标"""
        for agent_name, agent_result in analysis.analyses.items():
            if agent_name not in self.performance_metrics:
                self.performance_metrics[agent_name] = {
                    'total_analyses': 0,
                    'correct_predictions': 0,
                    'total_confidence': 0.0,
                    'signal_distribution': {'BUY': 0, 'SELL': 0, 'HOLD': 0}
                }
            
            metrics = self.performance_metrics[agent_name]
            metrics['total_analyses'] += 1
            
            if isinstance(agent_result, dict):
                confidence = agent_result.get('confidence', 0.5)
                signal = agent_result.get('signal', 'HOLD')
                
                metrics['total_confidence'] += confidence
                metrics['signal_distribution'][signal] += 1
                
                # 计算准确率需要后续市场数据验证，这里暂时跳过
    
    def calculate_strategy_performance(self) -> Dict[str, Dict]:
        """计算策略表现"""
        strategy_performance = {}
        
        for analysis in self.analysis_history:
            for signal in analysis.signals:
                strategy = signal.strategy
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = {
                        'total_signals': 0,
                        'executed_signals': 0,
                        'avg_confidence': 0.0,
                        'signal_types': {'BUY': 0, 'SELL': 0, 'HOLD': 0}
                    }
                
                perf = strategy_performance[strategy]
                perf['total_signals'] += 1
                perf['avg_confidence'] += signal.confidence
                perf['signal_types'][signal.signal_type.value] += 1
                
                if signal.executed:
                    perf['executed_signals'] += 1
        
        # 计算平均值
        for perf in strategy_performance.values():
            if perf['total_signals'] > 0:
                perf['avg_confidence'] /= perf['total_signals']
                perf['execution_rate'] = perf['executed_signals'] / perf['total_signals']
        
        return strategy_performance
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """生成分析摘要报告"""
        if not self.analysis_history:
            return {"message": "没有分析数据"}
        
        latest = self.get_latest_analysis()
        recent_analyses = self.get_analysis_by_timeframe(24)  # 最近24小时
        
        # 信号统计
        recent_signals = []
        for analysis in recent_analyses:
            recent_signals.extend(analysis.signals)
        
        signal_stats = {
            'total': len(recent_signals),
            'by_type': {'BUY': 0, 'SELL': 0, 'HOLD': 0},
            'by_strategy': {},
            'avg_confidence': 0.0
        }
        
        total_confidence = 0
        for signal in recent_signals:
            signal_stats['by_type'][signal.signal_type.value] += 1
            
            if signal.strategy not in signal_stats['by_strategy']:
                signal_stats['by_strategy'][signal.strategy] = 0
            signal_stats['by_strategy'][signal.strategy] += 1
            
            total_confidence += signal.confidence
        
        if recent_signals:
            signal_stats['avg_confidence'] = total_confidence / len(recent_signals)
        
        # 市场趋势分析
        market_trend = "中性"
        if latest and 'market' in latest.analyses:
            market_analysis = latest.analyses['market']
            if isinstance(market_analysis, dict):
                market_trend = market_analysis.get('trend', '中性')
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_analyses': len(self.analysis_history),
            'recent_analyses_count': len(recent_analyses),
            'latest_analysis_time': latest.timestamp.isoformat() if latest else None,
            'market_trend': market_trend,
            'signal_statistics': signal_stats,
            'agent_performance': self.performance_metrics,
            'strategy_performance': self.calculate_strategy_performance()
        }
    
    def export_analysis_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """导出分析数据"""
        filtered_analyses = [
            analysis for analysis in self.analysis_history
            if start_date <= analysis.timestamp <= end_date
        ]
        
        return [analysis.to_dict() for analysis in filtered_analyses]
    
    def get_agent_consensus(self) -> Dict[str, Any]:
        """获取分析师一致性意见"""
        latest = self.get_latest_analysis()
        if not latest:
            return {"consensus": "无数据", "confidence": 0.0}
        
        consensus_signal, confidence = latest.get_consensus_signal()
        
        # 计算一致性程度
        signals = []
        confidences = []
        
        for agent_result in latest.analyses.values():
            if isinstance(agent_result, dict):
                signals.append(agent_result.get('signal', 'HOLD'))
                confidences.append(agent_result.get('confidence', 0.5))
        
        # 一致性得分
        signal_counts = {signal: signals.count(signal) for signal in set(signals)}
        max_count = max(signal_counts.values()) if signal_counts else 0
        consensus_ratio = max_count / len(signals) if signals else 0
        
        return {
            'consensus_signal': consensus_signal.value,
            'consensus_confidence': confidence,
            'consensus_ratio': consensus_ratio,
            'agent_count': len(latest.analyses),
            'signal_breakdown': signal_counts,
            'avg_confidence': np.mean(confidences) if confidences else 0.0,
            'confidence_std': np.std(confidences) if confidences else 0.0
        }