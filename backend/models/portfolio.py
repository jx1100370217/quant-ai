from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal

class Position(BaseModel):
    """持仓模型"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field("", description="股票名称")
    quantity: int = Field(0, description="持仓数量")
    avg_cost: float = Field(0.0, description="平均成本")
    current_price: float = Field(0.0, description="当前价格")
    market_value: float = Field(0.0, description="市值")
    pnl: float = Field(0.0, description="盈亏")
    pnl_pct: float = Field(0.0, description="盈亏百分比")
    weight: float = Field(0.0, description="权重")
    stop_loss: Optional[float] = Field(None, description="止损价")
    take_profit: Optional[float] = Field(None, description="止盈价")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)

class Portfolio(BaseModel):
    """投资组合模型"""
    portfolio_id: str = Field(..., description="组合ID")
    name: str = Field("默认组合", description="组合名称")
    initial_capital: float = Field(1000000.0, description="初始资金")
    cash: float = Field(1000000.0, description="现金余额")
    total_value: float = Field(1000000.0, description="总资产")
    market_value: float = Field(0.0, description="持仓市值")
    total_pnl: float = Field(0.0, description="总盈亏")
    total_pnl_pct: float = Field(0.0, description="总盈亏百分比")
    positions: List[Position] = Field(default_factory=list, description="持仓列表")
    max_drawdown: float = Field(0.0, description="最大回撤")
    sharpe_ratio: float = Field(0.0, description="夏普比率")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
    
    def add_position(self, symbol: str, quantity: int, price: float, name: str = ""):
        """添加持仓"""
        existing_position = None
        for pos in self.positions:
            if pos.symbol == symbol:
                existing_position = pos
                break
                
        if existing_position:
            # 更新现有持仓
            total_quantity = existing_position.quantity + quantity
            total_cost = existing_position.avg_cost * existing_position.quantity + price * quantity
            existing_position.avg_cost = total_cost / total_quantity if total_quantity != 0 else 0
            existing_position.quantity = total_quantity
            existing_position.update_time = datetime.now()
        else:
            # 添加新持仓
            new_position = Position(
                symbol=symbol,
                name=name,
                quantity=quantity,
                avg_cost=price,
                current_price=price
            )
            self.positions.append(new_position)
            
        # 更新现金
        self.cash -= price * quantity
        self.update_portfolio_stats()
        
    def reduce_position(self, symbol: str, quantity: int, price: float) -> bool:
        """减少持仓"""
        for pos in self.positions:
            if pos.symbol == symbol:
                if pos.quantity >= quantity:
                    pos.quantity -= quantity
                    pos.update_time = datetime.now()
                    
                    # 更新现金
                    self.cash += price * quantity
                    
                    # 如果持仓为0，移除
                    if pos.quantity == 0:
                        self.positions.remove(pos)
                        
                    self.update_portfolio_stats()
                    return True
                else:
                    return False
        return False
        
    def update_prices(self, price_data: Dict[str, float]):
        """更新持仓价格"""
        for pos in self.positions:
            if pos.symbol in price_data:
                pos.current_price = price_data[pos.symbol]
                pos.market_value = pos.quantity * pos.current_price
                pos.pnl = pos.market_value - (pos.quantity * pos.avg_cost)
                pos.pnl_pct = (pos.pnl / (pos.quantity * pos.avg_cost)) if pos.avg_cost > 0 else 0
                pos.update_time = datetime.now()
                
        self.update_portfolio_stats()
        
    def update_portfolio_stats(self):
        """更新组合统计"""
        self.market_value = sum(pos.market_value for pos in self.positions)
        self.total_value = self.cash + self.market_value
        
        # 计算权重
        for pos in self.positions:
            pos.weight = pos.market_value / self.total_value if self.total_value > 0 else 0
            
        # 计算总盈亏
        total_cost = sum(pos.quantity * pos.avg_cost for pos in self.positions)
        self.total_pnl = self.market_value - total_cost
        self.total_pnl_pct = (self.total_pnl / total_cost) if total_cost > 0 else 0
        
        self.update_time = datetime.now()
        
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定持仓"""
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None
        
    def get_cash_ratio(self) -> float:
        """获取现金比例"""
        return self.cash / self.total_value if self.total_value > 0 else 1.0
        
    def get_top_positions(self, n: int = 5) -> List[Position]:
        """获取前N大持仓"""
        return sorted(self.positions, key=lambda x: x.market_value, reverse=True)[:n]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump(mode="json")

    def update(self, data: Dict[str, Any]):
        """从字典更新组合数据"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.update_portfolio_stats()

class PortfolioHistory(BaseModel):
    """组合历史记录"""
    portfolio_id: str
    date: datetime
    nav: float = Field(..., description="净值")
    total_value: float
    cash: float
    market_value: float
    pnl: float
    pnl_pct: float
    positions_count: int
    
class TradeRecord(BaseModel):
    """交易记录"""
    trade_id: str = Field(..., description="交易ID")
    portfolio_id: str = Field(..., description="组合ID")
    symbol: str = Field(..., description="股票代码")
    name: str = Field("", description="股票名称")
    trade_type: str = Field(..., description="交易类型：BUY/SELL")
    quantity: int = Field(..., description="交易数量")
    price: float = Field(..., description="交易价格")
    amount: float = Field(..., description="交易金额")
    commission: float = Field(0.0, description="手续费")
    tax: float = Field(0.0, description="税费")
    net_amount: float = Field(..., description="净金额")
    trade_time: datetime = Field(default_factory=datetime.now)
    reason: str = Field("", description="交易原因")
    agent: str = Field("", description="执行的Agent")
    
    def calculate_net_amount(self):
        """计算净金额"""
        if self.trade_type == "BUY":
            self.net_amount = self.amount + self.commission + self.tax
        else:  # SELL
            self.net_amount = self.amount - self.commission - self.tax
            
class PerformanceMetrics(BaseModel):
    """绩效指标"""
    portfolio_id: str
    period_start: datetime
    period_end: datetime
    
    # 收益指标
    total_return: float = Field(0.0, description="总收益率")
    annual_return: float = Field(0.0, description="年化收益率")
    daily_return_avg: float = Field(0.0, description="日均收益率")
    
    # 风险指标
    volatility: float = Field(0.0, description="波动率")
    max_drawdown: float = Field(0.0, description="最大回撤")
    var_95: float = Field(0.0, description="95% VaR")
    
    # 风险调整收益
    sharpe_ratio: float = Field(0.0, description="夏普比率")
    sortino_ratio: float = Field(0.0, description="索提诺比率")
    calmar_ratio: float = Field(0.0, description="卡玛比率")
    
    # 基准比较
    benchmark_return: float = Field(0.0, description="基准收益率")
    alpha: float = Field(0.0, description="阿尔法")
    beta: float = Field(1.0, description="贝塔")
    information_ratio: float = Field(0.0, description="信息比率")
    
    # 交易统计
    total_trades: int = Field(0, description="总交易次数")
    win_rate: float = Field(0.0, description="胜率")
    avg_win: float = Field(0.0, description="平均盈利")
    avg_loss: float = Field(0.0, description="平均亏损")
    profit_factor: float = Field(0.0, description="盈利因子")
    
    def calculate_metrics(self, nav_history: List[float], benchmark_history: List[float] = None):
        """计算绩效指标"""
        if len(nav_history) < 2:
            return
            
        # 计算日收益率
        returns = [(nav_history[i] / nav_history[i-1] - 1) for i in range(1, len(nav_history))]
        
        # 基本收益指标
        self.total_return = nav_history[-1] / nav_history[0] - 1
        days = len(returns)
        self.annual_return = (1 + self.total_return) ** (252 / days) - 1 if days > 0 else 0
        self.daily_return_avg = sum(returns) / len(returns) if returns else 0
        
        # 风险指标
        import numpy as np
        if returns:
            self.volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
            self.var_95 = np.percentile(returns, 5)  # 95% VaR
            
            # 最大回撤
            peak = nav_history[0]
            max_dd = 0
            for nav in nav_history:
                if nav > peak:
                    peak = nav
                dd = (peak - nav) / peak
                max_dd = max(max_dd, dd)
            self.max_drawdown = max_dd
            
            # 夏普比率（假设无风险利率为3%）
            risk_free_rate = 0.03 / 252  # 日无风险利率
            excess_returns = [r - risk_free_rate for r in returns]
            if np.std(excess_returns) > 0:
                self.sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
                
            # 索提诺比率
            downside_returns = [r for r in excess_returns if r < 0]
            if downside_returns and np.std(downside_returns) > 0:
                self.sortino_ratio = np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
                
            # 卡玛比率
            if self.max_drawdown > 0:
                self.calmar_ratio = self.annual_return / self.max_drawdown
                
        # 基准比较
        if benchmark_history and len(benchmark_history) == len(nav_history):
            benchmark_returns = [(benchmark_history[i] / benchmark_history[i-1] - 1) 
                               for i in range(1, len(benchmark_history))]
            self.benchmark_return = benchmark_history[-1] / benchmark_history[0] - 1
            
            if benchmark_returns and returns:
                # 计算Alpha和Beta
                import numpy as np
                covariance = np.cov(returns, benchmark_returns)[0][1]
                benchmark_variance = np.var(benchmark_returns)
                
                if benchmark_variance > 0:
                    self.beta = covariance / benchmark_variance
                    self.alpha = self.daily_return_avg - (self.beta * np.mean(benchmark_returns))
                    
                # 信息比率
                active_returns = [returns[i] - benchmark_returns[i] for i in range(len(returns))]
                if active_returns and np.std(active_returns) > 0:
                    self.information_ratio = np.mean(active_returns) / np.std(active_returns) * np.sqrt(252)