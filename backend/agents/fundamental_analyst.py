from typing import Dict, List, Any
from .base import BaseAgent
import asyncio

class FundamentalAnalyst(BaseAgent):
    """基本面分析Agent - 分析财务数据、估值水平、行业地位"""
    
    def __init__(self):
        super().__init__(
            name="FundamentalAnalyst",
            description="分析财务数据、估值水平、行业地位"
        )
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """基本面分析"""
        
        # 获取目标股票列表
        target_stocks = data.get("target_stocks", ["000001"])
        
        analysis_results = {}
        
        for stock_code in target_stocks:
            stock_analysis = await self._analyze_stock_fundamentals(stock_code)
            if stock_analysis:
                analysis_results[stock_code] = stock_analysis
                
        # 行业分析
        industry_analysis = await self._analyze_industry_trends()
        
        # 市场估值分析
        market_valuation = await self._analyze_market_valuation(analysis_results)
        
        return {
            "stock_fundamentals": analysis_results,
            "industry_analysis": industry_analysis,
            "market_valuation": market_valuation,
            "overall_assessment": self._generate_overall_assessment(analysis_results, industry_analysis, market_valuation)
        }
        
    async def _analyze_stock_fundamentals(self, stock_code: str) -> Dict[str, Any]:
        """分析个股基本面"""
        from data.xueqiu import xueqiu_api
        
        try:
            # 获取股票详细信息（包含基本面数据）
            stock_detail = await xueqiu_api.get_stock_detail(stock_code)
            
            if not stock_detail:
                return {"error": "无法获取基本面数据", "stock_code": stock_code}
                
            # 提取关键指标
            pe_ttm = stock_detail.get("pe_ttm", 0)
            pb = stock_detail.get("pb", 0)
            market_cap = stock_detail.get("market_capital", 0)
            float_market_cap = stock_detail.get("float_market_capital", 0)
            dividend_yield = stock_detail.get("dividend_yield", 0)
            eps = stock_detail.get("eps", 0)
            
            # 估值分析
            valuation_analysis = self._analyze_valuation(pe_ttm, pb, dividend_yield, stock_code)
            
            # 规模分析
            scale_analysis = self._analyze_company_scale(market_cap, float_market_cap)
            
            # 盈利能力分析
            profitability_analysis = self._analyze_profitability(eps, pe_ttm)
            
            # 财务健康度评估
            financial_health = self._assess_financial_health(pe_ttm, pb, dividend_yield)
            
            return {
                "stock_code": stock_code,
                "name": stock_detail.get("name", ""),
                "basic_metrics": {
                    "pe_ttm": pe_ttm,
                    "pb": pb,
                    "market_cap": market_cap,
                    "float_market_cap": float_market_cap,
                    "dividend_yield": dividend_yield,
                    "eps": eps
                },
                "valuation_analysis": valuation_analysis,
                "scale_analysis": scale_analysis,
                "profitability_analysis": profitability_analysis,
                "financial_health": financial_health
            }
            
        except Exception as e:
            return {"error": str(e), "stock_code": stock_code}
            
    def _analyze_valuation(self, pe_ttm: float, pb: float, dividend_yield: float, stock_code: str) -> Dict[str, Any]:
        """估值分析"""
        valuation_signals = []
        valuation_score = 0
        
        # PE估值分析
        if pe_ttm > 0:
            if pe_ttm < 15:
                valuation_signals.append("PE偏低")
                valuation_score += 0.3
            elif pe_ttm < 25:
                valuation_signals.append("PE合理")
                valuation_score += 0.1
            elif pe_ttm < 50:
                valuation_signals.append("PE偏高")
                valuation_score -= 0.1
            else:
                valuation_signals.append("PE过高")
                valuation_score -= 0.3
        else:
            valuation_signals.append("PE为负或无效")
            valuation_score -= 0.2
            
        # PB估值分析
        if pb > 0:
            if pb < 1:
                valuation_signals.append("PB破净")
                valuation_score += 0.2
            elif pb < 2:
                valuation_signals.append("PB较低")
                valuation_score += 0.15
            elif pb < 3:
                valuation_signals.append("PB合理")
                valuation_score += 0.05
            else:
                valuation_signals.append("PB偏高")
                valuation_score -= 0.1
                
        # 股息率分析
        if dividend_yield > 0:
            if dividend_yield > 0.04:  # 4%以上
                valuation_signals.append("高股息率")
                valuation_score += 0.15
            elif dividend_yield > 0.02:  # 2%-4%
                valuation_signals.append("中等股息率")
                valuation_score += 0.1
            else:
                valuation_signals.append("低股息率")
                
        # 估值等级
        if valuation_score > 0.3:
            valuation_level = "严重低估"
        elif valuation_score > 0.1:
            valuation_level = "低估"
        elif valuation_score > -0.1:
            valuation_level = "合理估值"
        elif valuation_score > -0.3:
            valuation_level = "高估"
        else:
            valuation_level = "严重高估"
            
        return {
            "valuation_level": valuation_level,
            "valuation_score": valuation_score,
            "signals": valuation_signals,
            "pe_ttm": pe_ttm,
            "pb": pb,
            "dividend_yield": dividend_yield
        }
        
    def _analyze_company_scale(self, market_cap: float, float_market_cap: float) -> Dict[str, Any]:
        """公司规模分析"""
        if market_cap <= 0:
            return {"scale": "未知", "category": "数据缺失"}
            
        # 按市值分类（单位：亿元）
        market_cap_yi = market_cap / 100000000
        
        if market_cap_yi >= 1000:
            scale_category = "超大盘股"
            liquidity_level = "极高"
        elif market_cap_yi >= 300:
            scale_category = "大盘股"
            liquidity_level = "高"
        elif market_cap_yi >= 100:
            scale_category = "中盘股"
            liquidity_level = "中等"
        elif market_cap_yi >= 50:
            scale_category = "小盘股"
            liquidity_level = "一般"
        else:
            scale_category = "微盘股"
            liquidity_level = "较低"
            
        # 流通比例
        circulation_ratio = float_market_cap / market_cap if market_cap > 0 else 0
        
        if circulation_ratio > 0.8:
            circulation_level = "高流通"
        elif circulation_ratio > 0.5:
            circulation_level = "中等流通"
        else:
            circulation_level = "低流通"
            
        return {
            "scale_category": scale_category,
            "market_cap_yi": market_cap_yi,
            "liquidity_level": liquidity_level,
            "circulation_ratio": circulation_ratio,
            "circulation_level": circulation_level
        }
        
    def _analyze_profitability(self, eps: float, pe_ttm: float) -> Dict[str, Any]:
        """盈利能力分析"""
        profitability_signals = []
        profitability_score = 0
        
        # EPS分析
        if eps > 0:
            if eps > 2:
                profitability_signals.append("高盈利能力")
                profitability_score += 0.3
            elif eps > 1:
                profitability_signals.append("良好盈利能力")
                profitability_score += 0.2
            elif eps > 0.5:
                profitability_signals.append("一般盈利能力")
                profitability_score += 0.1
            else:
                profitability_signals.append("盈利能力较弱")
        else:
            profitability_signals.append("亏损状态")
            profitability_score -= 0.3
            
        # PE与盈利能力综合分析
        if pe_ttm > 0 and eps > 0:
            if pe_ttm < 15 and eps > 1:
                profitability_signals.append("高性价比")
                profitability_score += 0.2
            elif pe_ttm > 50 and eps < 0.5:
                profitability_signals.append("低性价比")
                profitability_score -= 0.2
                
        # 盈利等级
        if profitability_score > 0.4:
            profitability_level = "优秀"
        elif profitability_score > 0.2:
            profitability_level = "良好"
        elif profitability_score > 0:
            profitability_level = "一般"
        else:
            profitability_level = "较差"
            
        return {
            "profitability_level": profitability_level,
            "profitability_score": profitability_score,
            "signals": profitability_signals,
            "eps": eps
        }
        
    def _assess_financial_health(self, pe_ttm: float, pb: float, dividend_yield: float) -> Dict[str, Any]:
        """财务健康度评估"""
        health_score = 0
        health_factors = []
        
        # PE健康度
        if pe_ttm > 0 and pe_ttm < 30:
            health_score += 0.3
            health_factors.append("PE健康")
        elif pe_ttm <= 0 or pe_ttm > 100:
            health_score -= 0.2
            health_factors.append("PE异常")
            
        # PB健康度
        if pb > 0.5 and pb < 5:
            health_score += 0.2
            health_factors.append("PB正常")
        elif pb <= 0:
            health_score -= 0.3
            health_factors.append("PB异常")
            
        # 分红健康度
        if dividend_yield > 0.01:  # 1%以上分红
            health_score += 0.15
            health_factors.append("有分红")
        
        # 健康等级
        if health_score > 0.4:
            health_level = "健康"
        elif health_score > 0.1:
            health_level = "一般"
        else:
            health_level = "需关注"
            
        return {
            "health_level": health_level,
            "health_score": health_score,
            "factors": health_factors
        }
        
    async def _analyze_industry_trends(self) -> Dict[str, Any]:
        """行业趋势分析"""
        from data.eastmoney import eastmoney_api
        
        try:
            # 获取行业板块数据
            sectors = await eastmoney_api.get_sector_ranking("industry")
            
            if not sectors:
                return {"trend": "数据获取失败"}
                
            # 计算行业整体表现
            rising_sectors = len([s for s in sectors if s.get("change_pct", 0) > 0])
            total_sectors = len(sectors)
            rising_ratio = rising_sectors / total_sectors if total_sectors > 0 else 0
            
            # 热门行业（资金流入前5）
            hot_industries = sorted(sectors, key=lambda x: x.get("net_inflow", 0), reverse=True)[:5]
            
            # 冷门行业（资金流出最多的5个）
            cold_industries = sorted(sectors, key=lambda x: x.get("net_inflow", 0))[:5]
            
            # 行业轮动强度
            total_inflow = sum(s.get("net_inflow", 0) for s in hot_industries if s.get("net_inflow", 0) > 0)
            total_outflow = abs(sum(s.get("net_inflow", 0) for s in cold_industries if s.get("net_inflow", 0) < 0))
            
            rotation_intensity = min((total_inflow + total_outflow) / 20000000000, 1.0)  # 标准化
            
            # 趋势判断
            if rising_ratio > 0.7:
                industry_trend = "普涨行情"
            elif rising_ratio > 0.5:
                industry_trend = "结构性行情"
            elif rising_ratio > 0.3:
                industry_trend = "分化行情"
            else:
                industry_trend = "普跌行情"
                
            return {
                "trend": industry_trend,
                "rising_ratio": rising_ratio,
                "rotation_intensity": rotation_intensity,
                "hot_industries": [{"name": s["name"], "change_pct": s.get("change_pct", 0)} for s in hot_industries],
                "cold_industries": [{"name": s["name"], "change_pct": s.get("change_pct", 0)} for s in cold_industries],
                "total_sectors_analyzed": total_sectors
            }
            
        except Exception as e:
            return {"error": str(e), "trend": "分析失败"}
            
    async def _analyze_market_valuation(self, stock_results: Dict[str, Any]) -> Dict[str, Any]:
        """市场整体估值分析"""
        if not stock_results:
            return {"level": "无数据", "average_pe": 0, "average_pb": 0}
            
        pe_values = []
        pb_values = []
        
        for stock_data in stock_results.values():
            if "basic_metrics" in stock_data:
                metrics = stock_data["basic_metrics"]
                pe = metrics.get("pe_ttm", 0)
                pb = metrics.get("pb", 0)
                
                if pe > 0 and pe < 100:  # 过滤异常值
                    pe_values.append(pe)
                if pb > 0 and pb < 10:    # 过滤异常值
                    pb_values.append(pb)
                    
        if not pe_values and not pb_values:
            return {"level": "无有效数据", "average_pe": 0, "average_pb": 0}
            
        avg_pe = sum(pe_values) / len(pe_values) if pe_values else 0
        avg_pb = sum(pb_values) / len(pb_values) if pb_values else 0
        
        # 估值水平判断
        valuation_level = "合理"
        if avg_pe > 0:
            if avg_pe < 15:
                valuation_level = "低估"
            elif avg_pe > 25:
                valuation_level = "高估"
                
        return {
            "level": valuation_level,
            "average_pe": avg_pe,
            "average_pb": avg_pb,
            "sample_size": len(pe_values)
        }
        
    def _generate_overall_assessment(self, stock_results: Dict, industry_analysis: Dict, market_valuation: Dict) -> Dict[str, Any]:
        """生成整体评估"""
        assessment_score = 0
        key_points = []
        
        # 个股基本面评分
        if stock_results:
            stock_scores = []
            for stock_data in stock_results.values():
                if "valuation_analysis" in stock_data:
                    val_score = stock_data["valuation_analysis"].get("valuation_score", 0)
                    stock_scores.append(val_score)
                    
            if stock_scores:
                avg_stock_score = sum(stock_scores) / len(stock_scores)
                assessment_score += avg_stock_score * 0.4
                
                if avg_stock_score > 0.2:
                    key_points.append("个股基本面较好")
                elif avg_stock_score < -0.2:
                    key_points.append("个股基本面较差")
                    
        # 行业趋势评分
        industry_trend = industry_analysis.get("trend", "")
        rising_ratio = industry_analysis.get("rising_ratio", 0.5)
        
        if "普涨" in industry_trend:
            assessment_score += 0.3
            key_points.append("行业普遍上涨")
        elif "结构性" in industry_trend:
            assessment_score += 0.1
            key_points.append("结构性行情")
        elif "普跌" in industry_trend:
            assessment_score -= 0.3
            key_points.append("行业普遍下跌")
            
        # 市场估值评分
        market_level = market_valuation.get("level", "")
        if market_level == "低估":
            assessment_score += 0.2
            key_points.append("市场估值偏低")
        elif market_level == "高估":
            assessment_score -= 0.2
            key_points.append("市场估值偏高")
            
        # 总体评级
        if assessment_score > 0.3:
            overall_rating = "积极"
        elif assessment_score > 0:
            overall_rating = "中性偏积极"
        elif assessment_score > -0.3:
            overall_rating = "中性偏谨慎"
        else:
            overall_rating = "谨慎"
            
        return {
            "overall_rating": overall_rating,
            "assessment_score": assessment_score,
            "key_points": key_points,
            "confidence": min(abs(assessment_score) + 0.3, 1.0)
        }
        
    async def get_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成基本面交易信号"""
        if "error" in analysis:
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reason": "基本面数据获取失败"
            }
            
        overall_assessment = analysis.get("overall_assessment", {})
        rating = overall_assessment.get("overall_rating", "中性")
        score = overall_assessment.get("assessment_score", 0)
        confidence = overall_assessment.get("confidence", 0.5)
        
        # 生成信号
        if score > 0.2 and "积极" in rating:
            signal = "BUY"
        elif score < -0.2 and "谨慎" in rating:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        # 生成理由
        key_points = overall_assessment.get("key_points", [])
        reason = f"基本面{rating}：" + "；".join(key_points) if key_points else f"基本面{rating}"
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "assessment_score": score
        }