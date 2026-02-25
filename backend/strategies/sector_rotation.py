"""
板块轮动策略 - Sector Rotation Strategy
基于板块强弱轮动的交易策略
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

from models.signal import Signal, SignalType
from utils.indicators import calculate_sma, calculate_rsi, calculate_momentum


class SectorRotationStrategy:
    """板块轮动策略实现"""
    
    def __init__(self):
        self.name = "板块轮动策略"
        self.description = "基于板块强弱轮动和资金流向的交易策略"
        
        # 策略参数
        self.momentum_period = 20
        self.sector_comparison_period = 10
        self.min_sector_strength = 0.02  # 最小板块强度要求
        self.rotation_threshold = 0.05   # 轮动信号阈值
        
        # 板块映射 (股票代码前缀或行业分类)
        self.sector_mapping = self._init_sector_mapping()
        
        # 板块历史表现
        self.sector_performance = defaultdict(list)
        
    def _init_sector_mapping(self) -> Dict[str, str]:
        """
        初始化板块映射表
        
        Returns:
            Dict[str, str]: 股票代码到板块的映射
        """
        return {
            # 科技板块
            '000001': '银行',
            '000002': '地产',
            '000858': '科技',
            '300001': '科技',
            '300002': '科技',
            
            # 银行板块
            '000001': '银行',
            '600000': '银行',
            '600036': '银行',
            '601318': '银行',
            
            # 地产板块
            '000002': '地产',
            '600048': '地产',
            '600340': '地产',
            '000069': '地产',
            
            # 医药板块
            '000001': '医药',
            '600276': '医药',
            '000538': '医药',
            '300003': '医药',
            
            # 消费板块
            '000858': '消费',
            '600519': '消费',
            '000895': '消费',
            '002304': '消费',
            
            # 新能源板块
            '300014': '新能源',
            '002594': '新能源',
            '300750': '新能源',
            '688599': '新能源',
            
            # 军工板块
            '000625': '军工',
            '600893': '军工',
            '002465': '军工',
            '300397': '军工'
        }
    
    async def generate_signals(self, market_data: Dict[str, Any]) -> List[Signal]:
        """
        生成板块轮动交易信号
        
        Args:
            market_data: 市场数据字典
            
        Returns:
            List[Signal]: 交易信号列表
        """
        signals = []
        
        try:
            stocks_data = market_data.get('stocks', {})
            
            # 按板块分组股票数据
            sector_data = self._group_by_sector(stocks_data)
            
            # 计算板块强弱
            sector_strength = await self._calculate_sector_strength(sector_data)
            
            # 识别轮动机会
            rotation_signals = self._identify_rotation_opportunities(sector_strength)
            
            # 生成个股信号
            for sector, signal_info in rotation_signals.items():
                sector_signals = await self._generate_sector_signals(
                    sector, signal_info, sector_data.get(sector, {})
                )
                signals.extend(sector_signals)
                
        except Exception as e:
            print(f"板块轮动策略信号生成失败: {e}")
            
        return signals
    
    def _group_by_sector(self, stocks_data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        按板块分组股票数据
        
        Args:
            stocks_data: 股票数据字典
            
        Returns:
            Dict[str, Dict]: 按板块分组的股票数据
        """
        sector_data = defaultdict(dict)
        
        for stock_code, stock_info in stocks_data.items():
            # 简化的板块映射（实际应该从数据库或API获取）
            sector = self._get_stock_sector(stock_code)
            sector_data[sector][stock_code] = stock_info
            
        return dict(sector_data)
    
    def _get_stock_sector(self, stock_code: str) -> str:
        """
        获取股票所属板块
        
        Args:
            stock_code: 股票代码
            
        Returns:
            str: 板块名称
        """
        # 简化的板块判断逻辑
        if stock_code.startswith('688'):
            return '科创板'
        elif stock_code.startswith('300'):
            return '创业板'
        elif stock_code.startswith('000'):
            return '深主板'
        elif stock_code.startswith('600') or stock_code.startswith('601') or stock_code.startswith('603'):
            return '沪主板'
        else:
            return '其他'
    
    async def _calculate_sector_strength(self, sector_data: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        计算各板块强弱指标
        
        Args:
            sector_data: 板块分组数据
            
        Returns:
            Dict[str, Dict]: 板块强弱指标
        """
        sector_strength = {}
        
        for sector, stocks in sector_data.items():
            if not stocks:
                continue
                
            sector_metrics = {
                'momentum': 0,
                'volume_ratio': 0,
                'rsi': 0,
                'stock_count': len(stocks),
                'up_count': 0,
                'down_count': 0,
                'total_market_cap': 0
            }
            
            valid_stocks = 0
            
            for stock_code, stock_info in stocks.items():
                try:
                    kline_data = stock_info.get('kline', [])
                    if len(kline_data) < self.momentum_period:
                        continue
                        
                    df = pd.DataFrame(kline_data)
                    prices = df['close'].astype(float)
                    volumes = df['volume'].astype(float)
                    
                    # 计算个股指标
                    momentum = calculate_momentum(prices, self.momentum_period)
                    rsi = calculate_rsi(prices, 14)
                    volume_sma = calculate_sma(volumes, 10)
                    
                    if len(momentum) > 0 and len(rsi) > 0 and len(volume_sma) > 0:
                        current_momentum = momentum.iloc[-1]
                        current_rsi = rsi.iloc[-1]
                        current_volume_ratio = volumes.iloc[-1] / volume_sma.iloc[-1]
                        
                        sector_metrics['momentum'] += current_momentum
                        sector_metrics['rsi'] += current_rsi
                        sector_metrics['volume_ratio'] += current_volume_ratio
                        
                        if current_momentum > 0:
                            sector_metrics['up_count'] += 1
                        else:
                            sector_metrics['down_count'] += 1
                            
                        valid_stocks += 1
                        
                except Exception as e:
                    print(f"计算股票{stock_code}指标失败: {e}")
                    continue
            
            if valid_stocks > 0:
                # 计算板块平均指标
                sector_metrics['momentum'] /= valid_stocks
                sector_metrics['rsi'] /= valid_stocks
                sector_metrics['volume_ratio'] /= valid_stocks
                sector_metrics['up_ratio'] = sector_metrics['up_count'] / valid_stocks
                
                # 计算板块强度得分
                strength_score = self._calculate_strength_score(sector_metrics)
                sector_metrics['strength_score'] = strength_score
                
                sector_strength[sector] = sector_metrics
        
        return sector_strength
    
    def _calculate_strength_score(self, metrics: Dict) -> float:
        """
        计算板块强度得分
        
        Args:
            metrics: 板块指标字典
            
        Returns:
            float: 强度得分 (0-100)
        """
        score = 0
        
        # 动量得分 (40%)
        momentum_score = min(40, max(-40, metrics['momentum'] * 1000))
        score += momentum_score
        
        # 上涨股票比例得分 (30%)
        up_ratio_score = (metrics['up_ratio'] - 0.5) * 60
        score += up_ratio_score
        
        # RSI得分 (20%)
        rsi = metrics['rsi']
        if 40 <= rsi <= 60:
            rsi_score = 20
        elif 30 <= rsi < 40 or 60 < rsi <= 70:
            rsi_score = 10
        else:
            rsi_score = 0
        score += rsi_score
        
        # 成交量得分 (10%)
        volume_score = min(10, (metrics['volume_ratio'] - 1) * 20)
        score += volume_score
        
        return max(0, min(100, score + 50))  # 归一化到0-100
    
    def _identify_rotation_opportunities(self, sector_strength: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        识别板块轮动机会
        
        Args:
            sector_strength: 板块强弱指标
            
        Returns:
            Dict[str, Dict]: 轮动信号
        """
        rotation_signals = {}
        
        if len(sector_strength) < 2:
            return rotation_signals
        
        # 按强度得分排序
        sorted_sectors = sorted(
            sector_strength.items(),
            key=lambda x: x[1]['strength_score'],
            reverse=True
        )
        
        # 识别强势和弱势板块
        strong_sectors = []
        weak_sectors = []
        
        for i, (sector, metrics) in enumerate(sorted_sectors):
            strength_score = metrics['strength_score']
            
            # 前30%为强势板块
            if i < len(sorted_sectors) * 0.3 and strength_score > 60:
                strong_sectors.append((sector, metrics))
            # 后30%为弱势板块
            elif i >= len(sorted_sectors) * 0.7 and strength_score < 40:
                weak_sectors.append((sector, metrics))
        
        # 生成轮动信号
        for sector, metrics in strong_sectors:
            if metrics['momentum'] > self.min_sector_strength:
                rotation_signals[sector] = {
                    'signal': 'BUY',
                    'strength': metrics['strength_score'],
                    'reason': f"强势板块，动量{metrics['momentum']:.2%}",
                    'confidence': min(0.9, 0.6 + (metrics['strength_score'] - 60) / 100)
                }
        
        for sector, metrics in weak_sectors:
            if metrics['momentum'] < -self.min_sector_strength:
                rotation_signals[sector] = {
                    'signal': 'SELL',
                    'strength': metrics['strength_score'],
                    'reason': f"弱势板块，动量{metrics['momentum']:.2%}",
                    'confidence': min(0.9, 0.6 + (40 - metrics['strength_score']) / 100)
                }
        
        return rotation_signals
    
    async def _generate_sector_signals(self, sector: str, signal_info: Dict,
                                     sector_stocks: Dict) -> List[Signal]:
        """
        为板块内的股票生成具体信号
        
        Args:
            sector: 板块名称
            signal_info: 板块信号信息
            sector_stocks: 板块内股票数据
            
        Returns:
            List[Signal]: 股票交易信号列表
        """
        signals = []
        signal_type = SignalType.BUY if signal_info['signal'] == 'BUY' else SignalType.SELL
        base_confidence = signal_info['confidence']
        
        # 选择板块内的优质个股
        stock_scores = []
        
        for stock_code, stock_data in sector_stocks.items():
            try:
                kline_data = stock_data.get('kline', [])
                if len(kline_data) < 10:
                    continue
                    
                df = pd.DataFrame(kline_data)
                prices = df['close'].astype(float)
                volumes = df['volume'].astype(float)
                
                # 计算个股评分
                stock_score = self._calculate_stock_score(prices, volumes)
                stock_scores.append((stock_code, stock_score, prices.iloc[-1]))
                
            except Exception as e:
                print(f"计算股票{stock_code}评分失败: {e}")
                continue
        
        # 按评分排序，选择前几名
        stock_scores.sort(key=lambda x: x[1], reverse=(signal_type == SignalType.BUY))
        
        # 生成信号（最多选择板块内前5只股票）
        for i, (stock_code, stock_score, current_price) in enumerate(stock_scores[:5]):
            # 根据个股在板块内的排名调整置信度
            rank_bonus = (5 - i) * 0.02
            adjusted_confidence = min(0.95, base_confidence + rank_bonus)
            
            signal = Signal(
                stock_code=stock_code,
                signal_type=signal_type,
                confidence=adjusted_confidence,
                price=current_price,
                timestamp=datetime.now(),
                strategy="sector_rotation",
                reason=f"{signal_info['reason']}，{sector}板块轮动",
                metadata={
                    'sector': sector,
                    'sector_strength': signal_info['strength'],
                    'stock_score': stock_score,
                    'sector_rank': i + 1
                }
            )
            signals.append(signal)
        
        return signals
    
    def _calculate_stock_score(self, prices: pd.Series, volumes: pd.Series) -> float:
        """
        计算个股评分
        
        Args:
            prices: 价格序列
            volumes: 成交量序列
            
        Returns:
            float: 个股评分
        """
        try:
            if len(prices) < 10:
                return 0
            
            # 价格动量
            momentum = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10]
            
            # RSI
            rsi_values = calculate_rsi(prices, 14)
            rsi = rsi_values.iloc[-1] if len(rsi_values) > 0 else 50
            
            # 成交量比率
            volume_sma = calculate_sma(volumes, 10)
            volume_ratio = volumes.iloc[-1] / volume_sma.iloc[-1] if len(volume_sma) > 0 else 1
            
            # 综合评分
            score = (momentum * 50) + ((rsi - 50) / 50 * 20) + ((volume_ratio - 1) * 30)
            
            return score
            
        except Exception:
            return 0
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取策略参数"""
        return {
            'momentum_period': self.momentum_period,
            'sector_comparison_period': self.sector_comparison_period,
            'min_sector_strength': self.min_sector_strength,
            'rotation_threshold': self.rotation_threshold
        }
    
    def update_parameters(self, **kwargs):
        """更新策略参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)