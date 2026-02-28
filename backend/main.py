"""
QuantAI - 量化交易AI系统 FastAPI主应用（LLM Agent 驱动版）
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
import time
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
# 价值派
from agents.warren_buffett import WarrenBuffett
from agents.charlie_munger import CharlieMunger
from agents.ben_graham import BenGraham
from agents.michael_burry import MichaelBurry
from agents.mohnish_pabrai import MohnishPabrai
# 成长派
from agents.peter_lynch import PeterLynch
from agents.cathie_wood import CathieWood
from agents.phil_fisher import PhilFisher
from agents.rakesh_jhunjhunwala import RakeshJhunjhunwala
# 宏观/激进派
from agents.aswath_damodaran import AswathDamodaran
from agents.stanley_druckenmiller import StanleyDruckenmiller
from agents.bill_ackman import BillAckman
from agents.base import AgentManager
from data.eastmoney import EastmoneyAPI, eastmoney_api
from data.sina import SinaAPI
from data.xueqiu import XueqiuAPI, xueqiu_api
from models.portfolio import Portfolio
from models.signal import Signal, SignalType
from models.analysis import Analysis
from models.agent_models import AgentSignal, PortfolioDecision
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.sector_rotation import SectorRotationStrategy
from strategies.multi_factor import MultiFactorStrategy
from utils.helpers import format_number, calculate_returns, get_trading_dates
from utils.telegram import notify_full_analysis, notify_market_picks, notify_holdings_analysis

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="QuantAI API",
    description="量化交易AI系统接口（LLM Agent 驱动）",
    version="2.0.0",
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

# 初始化数据源
eastmoney = EastmoneyAPI()
sina = SinaAPI()
xueqiu = XueqiuAPI()

# 初始化 LLM 驱动的 Agent
market_analyst = MarketAnalyst()
technical_analyst = TechnicalAnalyst()
fundamental_analyst = FundamentalAnalyst()
sentiment_analyst = SentimentAnalyst()
risk_manager = RiskManager()
portfolio_manager = PortfolioManager()
# 价值派
warren_buffett = WarrenBuffett()
charlie_munger = CharlieMunger()
ben_graham = BenGraham()
michael_burry = MichaelBurry()
mohnish_pabrai = MohnishPabrai()
# 成长派
peter_lynch = PeterLynch()
cathie_wood = CathieWood()
phil_fisher = PhilFisher()
rakesh_jhunjhunwala = RakeshJhunjhunwala()
# 宏观/激进派
aswath_damodaran = AswathDamodaran()
stanley_druckenmiller = StanleyDruckenmiller()
bill_ackman = BillAckman()

# Agent 管理器（注意 PortfolioManager 不在轮询列表，它是最终决策层）
agent_mgr = AgentManager()
agent_mgr.register_agent(technical_analyst)
agent_mgr.register_agent(fundamental_analyst)
agent_mgr.register_agent(sentiment_analyst)
agent_mgr.register_agent(risk_manager)
# 价值派
agent_mgr.register_agent(warren_buffett)
agent_mgr.register_agent(charlie_munger)
agent_mgr.register_agent(ben_graham)
agent_mgr.register_agent(michael_burry)
agent_mgr.register_agent(mohnish_pabrai)
# 成长派
agent_mgr.register_agent(peter_lynch)
agent_mgr.register_agent(cathie_wood)
agent_mgr.register_agent(phil_fisher)
agent_mgr.register_agent(rakesh_jhunjhunwala)
# 宏观/激进派
agent_mgr.register_agent(aswath_damodaran)
agent_mgr.register_agent(stanley_druckenmiller)
agent_mgr.register_agent(bill_ackman)

# 初始化策略（保留，用于兼容）
momentum_strategy = MomentumStrategy()
mean_reversion_strategy = MeanReversionStrategy()
sector_rotation_strategy = SectorRotationStrategy()
multi_factor_strategy = MultiFactorStrategy()

# 全局状态
analysis_history: List[Dict] = []
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
    return {"message": "QuantAI API is running (LLM Agent v2)", "timestamp": datetime.now()}


@app.get("/api/market/overview")
async def get_market_overview():
    """大盘概览"""
    try:
        indices = ["000001.SH", "399001.SZ", "399006.SZ"]
        overview_data = {}
        
        for index_code in indices:
            quote = await eastmoney.get_quote(index_code)
            overview_data[index_code] = quote
        
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
    """板块排行"""
    try:
        sectors = await eastmoney.get_sector_list()
        return {"success": True, "data": sectors, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"获取板块排行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}/quote")
async def get_stock_quote(code: str):
    """个股行情"""
    try:
        quote = await eastmoney.get_quote(code)
        return {"success": True, "data": quote, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"获取股票{code}行情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}/kline")
async def get_stock_kline(code: str, period: str = "1d", count: int = 100):
    """K线数据"""
    try:
        kline_data = await eastmoney.get_kline(code, period, count)
        return {"success": True, "data": kline_data, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"获取股票{code}K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/run")
async def run_full_analysis():
    """
    触发全量 LLM Agent 分析：
    1. 所有分析 Agent 并发执行
    2. Portfolio Manager 汇总信号做最终决策
    """
    try:
        logger.info("开始执行 LLM Agent 全量分析...")
        
        # 准备分析数据
        market_data = {
            "target_stocks": ["000001", "600036", "000858", "600519", "000002"],
        }
        
        # Step 1: 并发运行所有分析 Agent（除 PortfolioManager）
        logger.info("Step 1: 运行所有分析 Agent...")
        agent_signals = await agent_mgr.run_all_agents(market_data)
        
        # Step 2: Portfolio Manager 汇总做决策
        logger.info("Step 2: Portfolio Manager 做最终决策...")
        risk_limits = market_data.get("risk_limits", {})
        
        decisions = await portfolio_manager.make_decision(
            agent_signals=agent_signals,
            portfolio=portfolio.model_dump(mode="json"),
            risk_limits=risk_limits,
        )
        
        # 序列化结果
        serialized_signals = {}
        for agent_name, signals in agent_signals.items():
            serialized_signals[agent_name] = {}
            for stock_code, signal in signals.items():
                if isinstance(signal, AgentSignal):
                    serialized_signals[agent_name][stock_code] = signal.model_dump()
                elif isinstance(signal, dict):
                    serialized_signals[agent_name][stock_code] = signal
        
        serialized_decisions = {}
        for stock_code, decision in decisions.items():
            if isinstance(decision, PortfolioDecision):
                serialized_decisions[stock_code] = decision.model_dump()
            elif isinstance(decision, dict):
                serialized_decisions[stock_code] = decision
        
        result = {
            "agent_signals": serialized_signals,
            "portfolio_decisions": serialized_decisions,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 保存到历史
        analysis_history.append(result)

        # 推送到 Telegram
        await notify_full_analysis(result)

        # 广播到 WebSocket
        await manager.broadcast(json.dumps({
            "type": "analysis_complete",
            "data": result,
        }, default=str))

        logger.info("全量分析完成！")
        
        return {
            "success": True,
            "data": result,
        }
        
    except Exception as e:
        logger.error(f"全量分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio")
async def get_portfolio():
    """当前持仓"""
    try:
        return {"success": True, "data": portfolio.to_dict(), "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/update")
async def update_portfolio(update_data: dict):
    """更新持仓"""
    try:
        portfolio.update(update_data)
        await manager.broadcast(json.dumps({
            "type": "portfolio_updated",
            "data": portfolio.to_dict()
        }, default=str))
        return {"success": True, "data": portfolio.to_dict(), "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/status")
async def get_agent_status():
    """获取所有 Agent 状态"""
    return {
        "success": True,
        "data": agent_mgr.get_agent_status(),
        "timestamp": datetime.now(),
    }


def _quant_prescore(stock: Dict[str, Any]) -> float:
    """
    两阶段筛选 Phase-1：纯量化预评分（无 LLM），用于快速缩小候选池。
    分数越高越值得 LLM 深入分析。
    """
    score = 0.0
    chg     = stock.get("change_pct", 0) or 0
    inflow  = stock.get("net_inflow", 0) or 0
    pe      = stock.get("pe_ttm") or stock.get("pe")
    pb      = stock.get("pb")
    mcap    = stock.get("market_cap_b") or 0

    # 涨幅适中 1-7%（不追高、有动量）
    if 1 <= chg <= 7:
        score += 2.0
    elif 0 < chg < 1:
        score += 0.5

    # 主力净流入（越大越好）
    if inflow > 5e8:   score += 3.0
    elif inflow > 1e8: score += 1.5
    elif inflow > 0:   score += 0.5

    # PE 合理区间（5-40x）
    if pe and 5 < pe < 40:
        score += 2.0
    elif pe and 0 < pe <= 5:
        score += 1.0  # 可能是银行/低估值

    # PB < 3 安全边际
    if pb and 0 < pb < 3:
        score += 1.5
    elif pb and 3 <= pb < 6:
        score += 0.5

    # 中等市值（20-500亿），流动性合理
    if 20 <= mcap <= 500:
        score += 1.0

    return round(score, 2)


# ── market-picks 并发锁 + 结果缓存（避免前端并发双调用重复跑16个LLM）──
_PICKS_LOCK = asyncio.Lock()
_PICKS_CACHE: Dict[str, Any] = {"ts": 0, "result": None}
_PICKS_CACHE_TTL = 180  # 3分钟内复用结果


@app.post("/api/agents/market-picks")
async def agents_market_picks(body: dict):
    """
    两阶段精选：
    Phase-1 量化预筛 → 只保留3只最佳候选（降低LLM调用量）
    Phase-2 全量16 Agent LLM分析 → 综合评分出 sector_pick + master_pick

    body: {"holdings": [{"code": "000852", ...}]}
    """
    # 缓存命中：3分钟内直接返回上次结果
    now_ts = time.time()
    if _PICKS_CACHE["result"] and now_ts - _PICKS_CACHE["ts"] < _PICKS_CACHE_TTL:
        logger.info("market-picks 命中缓存，直接返回")
        return _PICKS_CACHE["result"]

    # 并发锁：同时只允许一个 market-picks 请求执行，其余等待结果
    async with _PICKS_LOCK:
        # 再次检查缓存（等锁期间可能已有结果）
        now_ts = time.time()
        if _PICKS_CACHE["result"] and now_ts - _PICKS_CACHE["ts"] < _PICKS_CACHE_TTL:
            logger.info("market-picks 等锁后命中缓存，直接返回")
            return _PICKS_CACHE["result"]

        return await _do_market_picks(body)


async def _do_market_picks(body: dict):
    """
    market-picks 核心逻辑（在锁内执行）
    
    两路并行选股：
    - sector_pick：热门板块 Top1 → 板块成分股量化预筛 → 16大师分析
    - master_pick：全A股净流入 Top30 → 量化预筛 → 16大师分析
    
    合并去重后一次性跑 agents，再分别取最优
    """
    try:
        holdings = body.get("holdings", [])
        held_codes = {h["code"] for h in holdings if h.get("code")}

        # ════════════════════════════════════════════════════════════
        # Phase 1: 并行获取两路候选
        # ════════════════════════════════════════════════════════════
        import asyncio as _aio

        async def _get_sector_candidates():
            """热门板块路径：Top3板块 → 成分股"""
            sectors = await eastmoney_api.get_sector_ranking()
            if not sectors:
                return [], None
            for sector in sectors[:3]:
                raw = await eastmoney_api.get_sector_stocks(sector["code"], limit=8)
                eligible = [s for s in raw if s.get("code") and s["code"] not in held_codes]
                if eligible:
                    for s in eligible:
                        s["_source"] = "sector"
                        s["_sector_name"] = sector["name"]
                    return eligible, sector
            return [], sectors[0] if sectors else None

        async def _get_market_candidates():
            """全A股路径：净流入 Top30"""
            raw = await eastmoney_api.get_top_stocks_market_wide(limit=30)
            eligible = [s for s in raw if s.get("code") and s["code"] not in held_codes]
            for s in eligible:
                s["_source"] = "market_wide"
                s["_sector_name"] = "全A股"
            return eligible

        # 并行获取两路候选
        (sector_candidates, top_sector), market_candidates = await _aio.gather(
            _get_sector_candidates(),
            _get_market_candidates(),
        )

        if not top_sector:
            top_sector = {"name": "未知", "code": ""}

        # ════════════════════════════════════════════════════════════
        # Phase 2: 量化预筛 → 去重合并 → 选出最终候选
        # ════════════════════════════════════════════════════════════

        # 板块候选：量化预筛取前3
        for s in sector_candidates:
            s["_prescore"] = _quant_prescore(s)
        sector_candidates.sort(key=lambda x: x["_prescore"], reverse=True)
        sector_finalists = sector_candidates[:3]

        # 全A股候选：量化预筛取前5
        for s in market_candidates:
            s["_prescore"] = _quant_prescore(s)
        market_candidates.sort(key=lambda x: x["_prescore"], reverse=True)
        master_finalists = market_candidates[:5]

        # 合并去重（code 为 key，全A股路径优先保留更多信息）
        all_candidates_map: Dict[str, dict] = {}
        for s in sector_finalists:
            all_candidates_map[s["code"]] = s
        for s in master_finalists:
            if s["code"] not in all_candidates_map:
                all_candidates_map[s["code"]] = s

        all_finalists = list(all_candidates_map.values())
        if not all_finalists:
            raise HTTPException(status_code=503, detail="未找到符合条件的候选股票")

        candidate_codes = [s["code"] for s in all_finalists]
        sector_codes = {s["code"] for s in sector_finalists}
        master_codes = {s["code"] for s in master_finalists}

        logger.info(
            f"market-picks 候选合并: 板块({top_sector['name']})={[s['code'] for s in sector_finalists]} "
            f"全A股={[s['code'] for s in master_finalists]} → 总计{len(candidate_codes)}只"
        )

        # ════════════════════════════════════════════════════════════
        # Phase 3: 预热缓存 + 16大师分析（一次性跑所有候选）
        # ════════════════════════════════════════════════════════════
        warmup = []
        for code in candidate_codes:
            warmup.append(eastmoney_api.get_stock_quote(code))
            warmup.append(eastmoney_api.get_kline_data(code, "101", 100))
            warmup.append(eastmoney_api.get_kline_data(code, "101", 60))
        warmup.append(eastmoney_api.get_sector_ranking())
        warmup.append(eastmoney_api.get_market_stats())
        warm_results = await _aio.gather(*warmup, return_exceptions=True)
        warm_fail = sum(1 for r in warm_results if isinstance(r, Exception))
        if warm_fail:
            logger.warning(f"market-picks 缓存预热{warm_fail}个失败")
        else:
            logger.info(f"market-picks 缓存预热完成: {candidate_codes}")

        # 一次性跑16个大师分析所有候选股
        agent_signals = await agent_mgr.run_all_agents({"target_stocks": candidate_codes})

        # ════════════════════════════════════════════════════════════
        # Phase 4: 打分 + 分别选出 sector_pick 和 master_pick
        # ════════════════════════════════════════════════════════════
        def score_stock(code: str) -> Dict[str, Any]:
            bullish = bearish = neutral = 0
            total_conf = 0
            agent_detail: Dict[str, Any] = {}
            for agent_name, signals in agent_signals.items():
                sig = signals.get(code)
                if not sig:
                    continue
                sig_dict = sig.model_dump() if hasattr(sig, "model_dump") else sig
                agent_detail[agent_name] = sig_dict
                total_conf += sig_dict.get("confidence", 0)
                s = sig_dict.get("signal", "neutral")
                if s == "bullish":   bullish += 1
                elif s == "bearish": bearish += 1
                else:                neutral += 1
            n = bullish + bearish + neutral
            avg_conf = round(total_conf / n, 1) if n > 0 else 0
            score = round((bullish / n * avg_conf) if n > 0 else 0, 2)
            return {
                "bullish": bullish, "bearish": bearish, "neutral": neutral,
                "avg_confidence": avg_conf, "score": score,
                "agent_signals": agent_detail,
            }

        all_scored = []
        for s in all_finalists:
            code = s["code"]
            sc = score_stock(code)
            all_scored.append({
                "code":         code,
                "name":         s["name"],
                "price":        s.get("price", 0),
                "change_pct":   s.get("change_pct", 0),
                "pe_ttm":       s.get("pe_ttm"),
                "pb":           s.get("pb"),
                "market_cap_b": s.get("market_cap_b"),
                "net_inflow":   s.get("net_inflow", 0),
                "sector_name":  s.get("_sector_name", "全A股"),
                "prescore":     s.get("_prescore", 0),
                **sc,
            })

        if not all_scored:
            raise HTTPException(status_code=503, detail="所有候选股分析为空")

        # sector_pick：仅从板块候选中选 LLM 得分最高
        sector_scored = [s for s in all_scored if s["code"] in sector_codes]
        sector_pick = max(sector_scored, key=lambda x: x["score"]) if sector_scored else all_scored[0]

        # master_pick：从全A股候选中选综合得分最高
        #   综合得分 = LLM score × 0.6 + 量化预评分 × 0.2 + 净流入加分 × 0.2
        master_scored = [s for s in all_scored if s["code"] in master_codes]
        if not master_scored:
            master_scored = all_scored  # fallback

        max_prescore = max((s["prescore"] for s in master_scored), default=1) or 1
        max_inflow = max((s["net_inflow"] for s in master_scored), default=1) or 1
        for s in master_scored:
            inflow_score = (s["net_inflow"] / max_inflow * 100) if max_inflow > 0 else 0
            s["composite"] = round(
                s["score"] * 0.6
                + (s["prescore"] / max_prescore * 100) * 0.2
                + inflow_score * 0.2,
                2
            )
        master_pick = max(master_scored, key=lambda x: x["composite"])

        top_sector_names = list({s.get("_sector_name", "全A股") for s in all_finalists})

        result = {
            "success": True,
            "sector_pick": sector_pick,
            "master_pick": master_pick,
            "candidates_count": len(all_scored),
            "top_sectors": top_sector_names,
            "sector_name": top_sector.get("name", ""),
            "all_candidates": all_scored,
            "timestamp": datetime.now().isoformat(),
        }
        _PICKS_CACHE["ts"] = time.time()
        _PICKS_CACHE["result"] = result

        # 推送到 Telegram
        await notify_market_picks(result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"market-picks 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/analyze-holdings")
async def analyze_holdings(body: dict):
    """
    动态分析持仓股票（前端持仓驱动，调用全部 LLM Agent）
    
    body: {"holdings": [{"code": "000001", "name": "平安银行", "cost": 9.5}]}
    返回: {"success": true, "data": {"agentName": {"stockCode": {signal, confidence, reasoning}}}}
    """
    try:
        holdings = body.get("holdings", [])
        if not holdings:
            return {"success": False, "error": "holdings 不能为空"}

        target_stocks = [h["code"] for h in holdings if h.get("code")]
        if not target_stocks:
            return {"success": False, "error": "未找到有效股票代码"}

        logger.info(f"开始分析持仓: {target_stocks}")

        # ── 预热缓存：并发拉取行情+K线+市场数据，后续16个Agent直接命中缓存 ──
        import asyncio as _aio
        warmup_tasks = []
        for code in target_stocks:
            warmup_tasks.append(eastmoney_api.get_stock_quote(code))
            warmup_tasks.append(eastmoney_api.get_kline_data(code, "101", 100))  # 技术分析用
            warmup_tasks.append(eastmoney_api.get_kline_data(code, "101", 60))   # 风险管理用
        warmup_tasks.append(eastmoney_api.get_market_stats())    # 情绪分析用
        warmup_tasks.append(eastmoney_api.get_sector_ranking())  # 板块数据用
        warm_results = await _aio.gather(*warmup_tasks, return_exceptions=True)
        failed = [r for r in warm_results if isinstance(r, Exception)]
        if failed:
            logger.warning(f"缓存预热部分失败（{len(failed)}个），将降级运行: {failed[0]}")
        else:
            logger.info("缓存预热完成，开始16位大师分析")

        market_data = {"target_stocks": target_stocks}
        agent_signals = await agent_mgr.run_all_agents(market_data)

        # 序列化
        serialized: Dict[str, Any] = {}
        for agent_name, signals in agent_signals.items():
            serialized[agent_name] = {}
            for code, signal in signals.items():
                if isinstance(signal, AgentSignal):
                    serialized[agent_name][code] = signal.model_dump()
                elif isinstance(signal, dict):
                    serialized[agent_name][code] = signal

        result = {
            "success": True,
            "data": serialized,
            "agent_count": len(serialized),
            "stock_count": len(target_stocks),
            "timestamp": datetime.now().isoformat(),
        }

        # 推送到 Telegram
        await notify_holdings_analysis(result, holdings)

        return result

    except Exception as e:
        logger.error(f"analyze-holdings 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/decisions")
async def get_agent_decisions(limit: int = 50):
    """Agent 决策历史"""
    try:
        recent = analysis_history[-limit:] if analysis_history else []
        return {"success": True, "data": recent, "timestamp": datetime.now()}
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
        return {"success": True, "data": estimate, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"获取基金{code}估值失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """实时推送WebSocket"""
    await manager.connect(websocket)
    logger.info(f"新的WebSocket连接: {websocket.client}")
    
    try:
        await manager.send_personal_message(json.dumps({
            "type": "welcome",
            "message": "Connected to QuantAI realtime stream (LLM Agent v2)",
            "timestamp": datetime.now().isoformat()
        }, default=str), websocket)
        
        while True:
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


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    logger.info("QuantAI API (LLM Agent v2) 启动完成")
    asyncio.create_task(periodic_market_check())


async def periodic_market_check():
    """定期市场检查"""
    while True:
        try:
            now = datetime.now()
            if 9 <= now.hour <= 15:
                logger.info("执行定期市场检查...")
                market_overview = await get_market_overview()
                await manager.broadcast(json.dumps({
                    "type": "periodic_update",
                    "data": market_overview["data"]
                }, default=str))
        except Exception as e:
            logger.error(f"定期检查失败: {e}")
        
        await asyncio.sleep(300)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
