"""
QuantAI - 量化交易AI系统 FastAPI主应用
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
from typing import Dict, List, Any
import json
from datetime import datetime, timedelta
import uvicorn

from agents.portfolio_manager import PortfolioManager
from agents.market_analyst import MarketAnalyst
from agents.technical_analyst import TechnicalAnalyst
from agents.fundamental_analyst import FundamentalAnalyst
from agents.sentiment_analyst import SentimentAnalyst
from agents.risk_manager import RiskManager
from data.eastmoney import EastmoneyAPI, eastmoney_api
from data.sina import SinaAPI
from data.xueqiu import XueqiuAPI, xueqiu_api
from models.portfolio import Portfolio
from models.signal import Signal, SignalType
from models.analysis import Analysis
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.sector_rotation import SectorRotationStrategy
from strategies.multi_factor import MultiFactorStrategy
from utils.helpers import format_number, calculate_returns, get_trading_dates

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="QuantAI API",
    description="量化交易AI系统接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据源和AI代理
eastmoney = EastmoneyAPI()
sina = SinaAPI()
xueqiu = XueqiuAPI()

portfolio_manager = PortfolioManager()
market_analyst = MarketAnalyst()
technical_analyst = TechnicalAnalyst()
fundamental_analyst = FundamentalAnalyst()
sentiment_analyst = SentimentAnalyst()
risk_manager = RiskManager()

# 初始化策略
momentum_strategy = MomentumStrategy()
mean_reversion_strategy = MeanReversionStrategy()
sector_rotation_strategy = SectorRotationStrategy()
multi_factor_strategy = MultiFactorStrategy()

# 全局状态
websocket_connections: List[WebSocket] = []
analysis_history: List[Analysis] = []
signal_history: List[Signal] = []
portfolio = Portfolio(portfolio_id="default")


class ConnectionManager:
    """WebSocket连接管理器"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                self.disconnect(connection)

manager = ConnectionManager()


@app.get("/")
async def root():
    """根路径健康检查"""
    return {"message": "QuantAI API is running", "timestamp": datetime.now()}


@app.get("/api/market/overview")
async def get_market_overview():
    """大盘概览 - 调用eastmoney批量行情"""
    try:
        # 获取主要指数行情
        indices = ["000001.SH", "399001.SZ", "399006.SZ"]  # 上证指数、深证成指、创业板指
        overview_data = {}
        
        for index_code in indices:
            quote = await eastmoney.get_quote(index_code)
            overview_data[index_code] = quote
        
        # 获取涨跌家数
        market_stats = await eastmoney.get_market_stats()
        
        return {
            "success": True,
            "data": {
                "indices": overview_data,
                "market_stats": market_stats,
                "timestamp": datetime.now()
            }
        }
    except Exception as e:
        logger.error(f"获取大盘概览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market/sectors")
async def get_sector_ranking():
    """板块排行 - 调用eastmoney clist"""
    try:
        sectors = await eastmoney.get_sector_list()
        return {
            "success": True,
            "data": sectors,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取板块排行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}/quote")
async def get_stock_quote(code: str):
    """个股行情"""
    try:
        quote = await eastmoney.get_quote(code)
        return {
            "success": True,
            "data": quote,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取股票{code}行情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}/kline")
async def get_stock_kline(code: str, period: str = "1d", count: int = 100):
    """K线数据"""
    try:
        kline_data = await eastmoney.get_kline(code, period, count)
        return {
            "success": True,
            "data": kline_data,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取股票{code}K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/run")
async def run_full_analysis():
    """触发全量分析 - 调用所有Agent"""
    try:
        logger.info("开始执行全量分析...")
        
        # 获取市场数据
        market_data = await eastmoney.get_market_overview()
        
        # 依次调用各个分析师
        analyses = {}
        
        # 市场分析师
        market_analysis = await market_analyst.analyze(market_data)
        analyses['market'] = market_analysis
        
        # 技术分析师
        technical_analysis = await technical_analyst.analyze(market_data)
        analyses['technical'] = technical_analysis
        
        # 基本面分析师
        fundamental_analysis = await fundamental_analyst.analyze(market_data)
        analyses['fundamental'] = fundamental_analysis
        
        # 情绪分析师
        sentiment_analysis = await sentiment_analyst.analyze(market_data)
        analyses['sentiment'] = sentiment_analysis
        
        # 风险管理师
        risk_analysis = await risk_manager.analyze(market_data)
        analyses['risk'] = risk_analysis
        
        # 投资组合管理师汇总决策
        portfolio_decision = await portfolio_manager.make_decision(analyses)
        analyses['portfolio'] = portfolio_decision
        
        # 生成交易信号
        signals = []
        strategies = [momentum_strategy, mean_reversion_strategy, sector_rotation_strategy, multi_factor_strategy]
        
        for strategy in strategies:
            strategy_signals = await strategy.generate_signals(market_data)
            signals.extend(strategy_signals)
        
        # 保存分析历史
        analysis = Analysis(
            timestamp=datetime.now(),
            analyses=analyses,
            signals=signals,
            market_data=market_data
        )
        analysis_history.append(analysis)
        signal_history.extend(signals)
        
        # 广播到WebSocket客户端
        await manager.broadcast(json.dumps({
            "type": "analysis_complete",
            "data": analysis.to_dict()
        }, default=str))
        
        return {
            "success": True,
            "data": {
                "analyses": analyses,
                "signals": [s.to_dict() for s in signals],
                "timestamp": datetime.now()
            }
        }
    except Exception as e:
        logger.error(f"全量分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio")
async def get_portfolio():
    """当前持仓"""
    try:
        return {
            "success": True,
            "data": portfolio.to_dict(),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/update")
async def update_portfolio(update_data: dict):
    """更新持仓"""
    try:
        portfolio.update(update_data)
        
        # 广播持仓变化
        await manager.broadcast(json.dumps({
            "type": "portfolio_updated",
            "data": portfolio.to_dict()
        }, default=str))
        
        return {
            "success": True,
            "data": portfolio.to_dict(),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/decisions")
async def get_agent_decisions(limit: int = 50):
    """Agent决策历史"""
    try:
        recent_analyses = analysis_history[-limit:] if analysis_history else []
        return {
            "success": True,
            "data": [analysis.to_dict() for analysis in recent_analyses],
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取决策历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals")
async def get_trade_signals(limit: int = 100):
    """交易信号"""
    try:
        recent_signals = signal_history[-limit:] if signal_history else []
        return {
            "success": True,
            "data": [signal.to_dict() for signal in recent_signals],
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取交易信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fund/{code}/estimate")
async def get_fund_estimate(code: str):
    """基金估值"""
    try:
        estimate = await eastmoney.get_fund_estimate(code)
        return {
            "success": True,
            "data": estimate,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"获取基金{code}估值失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """实时推送WebSocket"""
    await manager.connect(websocket)
    logger.info(f"新的WebSocket连接: {websocket.client}")
    
    try:
        # 发送欢迎消息
        await manager.send_personal_message(json.dumps({
            "type": "welcome",
            "message": "Connected to QuantAI realtime stream",
            "timestamp": datetime.now().isoformat()
        }, default=str), websocket)
        
        # 启动实时数据推送
        while True:
            # 每30秒推送一次市场概览
            try:
                market_overview = await get_market_overview()
                await manager.send_personal_message(json.dumps({
                    "type": "market_update",
                    "data": market_overview["data"]
                }, default=str), websocket)
            except Exception as e:
                logger.error(f"推送市场数据失败: {e}")
            
            await asyncio.sleep(30)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket连接断开: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        manager.disconnect(websocket)


# 定时任务 - 每分钟检查一次市场状态
@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    logger.info("QuantAI API启动完成")
    
    # 启动定时任务
    asyncio.create_task(periodic_market_check())


async def periodic_market_check():
    """定期市场检查"""
    while True:
        try:
            # 在交易时间才进行检查
            now = datetime.now()
            if 9 <= now.hour <= 15:  # 简化的交易时间判断
                logger.info("执行定期市场检查...")
                
                # 获取最新市场数据并广播
                market_overview = await get_market_overview()
                await manager.broadcast(json.dumps({
                    "type": "periodic_update",
                    "data": market_overview["data"]
                }, default=str))
                
        except Exception as e:
            logger.error(f"定期检查失败: {e}")
        
        # 每5分钟检查一次
        await asyncio.sleep(300)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )