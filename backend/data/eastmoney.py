import aiohttp
import asyncio
import json
import logging
import re
import time
from typing import Dict, List, Optional, Any
from config import config

logger = logging.getLogger(__name__)

# ── 短时内存缓存（30s TTL）──────────────────────────────────────────────────
# 防止 16 个并发 Agent 对同一只股票重复请求东财 API 触发限流
_QUOTE_CACHE: Dict[str, tuple] = {}   # {code: (timestamp, data)}
_SECTOR_CACHE: tuple = (0, None)      # (timestamp, data)
_CACHE_TTL = 60                        # 60 秒内复用缓存

def _make_session() -> aiohttp.ClientSession:
    """创建不走代理的 aiohttp session（解决本地代理干扰问题）"""
    connector = aiohttp.TCPConnector(force_close=True)
    timeout = aiohttp.ClientTimeout(total=15)  # 增加到15s，避免并发高峰超时
    return aiohttp.ClientSession(trust_env=False, connector=connector, timeout=timeout)


class EastmoneyAPI:
    """东方财富API接口"""
    
    def __init__(self):
        self.headers = config.EASTMONEY_HEADERS
        self.ut = "fa5fd1943c7b386f172d6893dbbd1d0c"
        
    def _parse_secid(self, code: str) -> str:
        """解析股票代码为东财 secid 格式（市场.代码）"""
        # 去掉可能的后缀 .SH / .SZ
        pure_code = code.split(".")[0]
        # 沪市：60x/688/000001(上证指数)/51x(ETF) → 市场1；深市：00x/300/399xxx/15x → 市场0
        if pure_code.startswith(("6", "5", "688")) or pure_code in ("000001",):
            # 特殊处理：399开头的是深市指数
            if pure_code.startswith("399"):
                return f"0.{pure_code}"
            return f"1.{pure_code}"
        else:
            return f"0.{pure_code}"

    @staticmethod
    def _safe_float(v, default=None) -> Optional[float]:
        """安全解析浮点数，0/null/'-' 返回 None"""
        if v in (None, "-", "", "null"):
            return default
        try:
            f = float(v)
            return round(f, 4) if f != 0 else default
        except (TypeError, ValueError):
            return default

    async def get_stock_quote(self, code: str) -> Optional[Dict]:
        """获取个股实时行情（含 PE/PB/市值基本面数据）
        
        使用 ulist.np/get + fltt=2 接口：
        - fltt=2 返回已处理的浮点值（不再需要 ÷100）
        - f9/f23/f115 在此接口能正确返回 PE/PB 数据
        - 内置 60s 缓存：16 个并发 Agent 共享同一次 API 调用结果
        """
        # ── 缓存命中检查 ───────────────────────────────
        now = time.time()
        if code in _QUOTE_CACHE:
            ts, cached = _QUOTE_CACHE[code]
            if now - ts < _CACHE_TTL:
                return cached

        secid = self._parse_secid(code)

        # fields:
        # f12=代码 f14=名称 f2=现价 f3=涨跌% f4=涨跌额
        # f15=最高 f16=最低 f17=开盘 f18=昨收
        # f5=成交量(手) f6=成交额 f8=换手率
        # f9=PE静 f115=PETTM f23=PB
        # f20=总市值(元) f21=流通市值(元)
        url = (f"https://push2.eastmoney.com/api/qt/ulist.np/get"
               f"?secids={secid}"
               f"&fields=f12,f14,f2,f3,f4,f5,f6,f8,f15,f16,f17,f18,f9,f115,f23,f20,f21"
               f"&fltt=2&ut={self.ut}")

        try:
            async with _make_session() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    diff = (data.get("data") or {}).get("diff") or []
                    if not diff:
                        return None
                    d = diff[0]

                    price     = self._safe_float(d.get("f2"), 0) or 0
                    high      = self._safe_float(d.get("f15"), price) or price
                    low       = self._safe_float(d.get("f16"), price) or price
                    pre_close = self._safe_float(d.get("f18"), price) or price
                    amplitude = round((high - low) / pre_close * 100, 2) if pre_close else 0

                    result = {
                        "code":       d.get("f12", code),
                        "name":       d.get("f14", ""),
                        "price":      price,
                        "high":       high,
                        "low":        low,
                        "open":       self._safe_float(d.get("f17"), price) or price,
                        "pre_close":  pre_close,
                        "volume":     int(d.get("f5") or 0),
                        "amount":     self._safe_float(d.get("f6"), 0) or 0,
                        "turnover_rate": self._safe_float(d.get("f8")),
                        "change_pct": self._safe_float(d.get("f3"), 0) or 0,
                        "change":     self._safe_float(d.get("f4"), 0) or 0,
                        "amplitude":  amplitude,
                        # 基本面（fltt=2 直接返回真实值）
                        "pe":         self._safe_float(d.get("f9")),    # PE 静
                        "pe_ttm":     self._safe_float(d.get("f115")),  # PE TTM
                        "pb":         self._safe_float(d.get("f23")),   # PB
                        "market_cap_b":       round((d.get("f20") or 0) / 1e8, 2) or None,
                        "float_market_cap_b": round((d.get("f21") or 0) / 1e8, 2) or None,
                    }
                    _QUOTE_CACHE[code] = (time.time(), result)   # 写入缓存
                    return result
        except Exception as e:
            logger.warning(f"获取股票行情失败 {code}: {e}")
            return None
            
    async def get_batch_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取行情"""
        # 构建secids
        secids = [self._parse_secid(code) for code in codes]
        
        url = (f"https://push2.eastmoney.com/api/qt/ulist.np/get"
               f"?secids={','.join(secids)}&fields=f2,f3,f4,f12,f14"
               f"&ut={self.ut}")
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    result = {}
                    if data.get("rc") == 0 and data.get("data", {}).get("diff"):
                        for item in data["data"]["diff"]:
                            result[item["f12"]] = {
                                "code": item["f12"],
                                "name": item["f14"],
                                "price": item.get("f2", 0) / 100,
                                "change_pct": item.get("f3", 0) / 100,
                                "change": item.get("f4", 0) / 100
                            }
                    return result
        except Exception as e:
            logger.warning(f"批量获取行情失败: {e}")
            return {}
            
    async def get_kline_data(self, code: str, klt: str = "101", limit: int = 100) -> List[Dict]:
        """获取K线数据（含 60s 缓存）
        klt: 101=日K, 102=周K, 103=月K, 1/5/15/30/60=分钟K
        """
        cache_key = f"kline_{code}_{klt}_{limit}"
        now = time.time()
        if cache_key in _QUOTE_CACHE:
            ts, cached = _QUOTE_CACHE[cache_key]
            if now - ts < _CACHE_TTL:
                return cached

        secid = self._parse_secid(code)
        
        url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
               f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11"
               f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
               f"&klt={klt}&fqt=1&end=20500101&lmt={limit}&ut={self.ut}")
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)

                    result = []
                    if data.get("rc") == 0 and data.get("data", {}).get("klines"):
                        for kline in data["data"]["klines"]:
                            # 格式: "日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
                            parts = kline.split(",")
                            if len(parts) >= 11:
                                result.append({
                                    "date": parts[0],
                                    "open": float(parts[1]),
                                    "close": float(parts[2]),
                                    "high": float(parts[3]),
                                    "low": float(parts[4]),
                                    "volume": int(parts[5]),
                                    "amount": float(parts[6]),
                                    "amplitude": float(parts[7]),
                                    "change_pct": float(parts[8]),
                                    "change": float(parts[9]),
                                    "turnover": float(parts[10]) if parts[10] else 0
                                })
                    _QUOTE_CACHE[cache_key] = (time.time(), result)  # 写入缓存
                    return result
        except Exception as e:
            logger.warning(f"获取K线数据失败 {code}: {e}")
            return []
            
    async def get_sector_ranking(self, sector_type: str = "industry") -> List[Dict]:
        """获取板块排行（含 60s 缓存）
        sector_type: industry=行业板块, concept=概念板块
        """
        # ── 缓存命中检查 ───────────────────────────────
        global _SECTOR_CACHE
        now = time.time()
        ts, cached = _SECTOR_CACHE
        if cached is not None and now - ts < _CACHE_TTL:
            return cached

        fs = "m:90+t:2+f:!50" if sector_type == "industry" else "m:90+t:3+f:!50"
        url = (f"https://push2.eastmoney.com/api/qt/clist/get"
               f"?cb=j&pn=1&pz=50&po=1&np=1&ut={self.ut}&fltt=2&invt=2"
               f"&fid=f62&fs={fs}&fields=f12,f14,f2,f3,f62,f184")
        
        headers = {
            'Referer': 'https://data.eastmoney.com/',
            'User-Agent': 'Mozilla/5.0'
        }
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers=headers) as resp:
                    text = await resp.text()
                    # 去掉JSONP包装
                    json_str = text.replace("j(", "").rstrip(");")
                    data = json.loads(json_str)
                    
                    result = []
                    if data.get("rc") == 0 and data.get("data", {}).get("diff"):
                        for item in data["data"]["diff"]:
                            result.append({
                                "code": item["f12"],
                                "name": item["f14"],
                                "price": item.get("f2", 0),
                                "change_pct": item.get("f3", 0) / 100,
                                "net_inflow": item.get("f62", 0),
                                "inflow_rate": item.get("f184", 0) / 100
                            })
                    _SECTOR_CACHE = (time.time(), result)   # 写入缓存
                    return result
        except Exception as e:
            logger.warning(f"获取板块排行失败: {e}")
            return []
            
    async def get_sector_stocks(self, sector_code: str, limit: int = 8, retries: int = 3) -> List[Dict]:
        """获取板块成分股（按主力净流入排序，fltt=2 直接是浮点）"""
        url = (f"https://push2.eastmoney.com/api/qt/clist/get"
               f"?cb=j&pn=1&pz={limit}&po=1&np=1&ut={self.ut}&fltt=2&invt=2"
               f"&fid=f62&fs=b:{sector_code}&fields=f12,f14,f2,f3,f62,f184,f9,f23,f115,f20")
        headers = {'Referer': 'https://quote.eastmoney.com/', 'User-Agent': 'Mozilla/5.0'}
        for attempt in range(retries):
            try:
                async with _make_session() as session:
                    async with session.get(url, headers=headers) as resp:
                        text = await resp.text()
                        json_str = text.replace("j(", "").rstrip(");")
                        data = json.loads(json_str)
                        result = []
                        if data.get("rc") == 0 and data.get("data", {}).get("diff"):
                            for d in data["data"]["diff"]:
                                result.append({
                                    "code":          d.get("f12", ""),
                                    "name":          d.get("f14", ""),
                                    "price":         d.get("f2", 0),
                                    "change_pct":    d.get("f3", 0),
                                    "net_inflow":    d.get("f62", 0),
                                    "inflow_rate":   d.get("f184", 0),
                                    "pe_ttm":        d.get("f115") or None,
                                    "pb":            d.get("f23") or None,
                                    "market_cap_b":  round((d.get("f20") or 0) / 1e8, 1) or None,
                                })
                        if result:
                            return result
                        # 空结果重试
                        if attempt < retries - 1:
                            await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"获取板块成分股失败 {sector_code} (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        return []

    async def get_top_stocks_market_wide(self, limit: int = 30, sort_by: str = "inflow", retries: int = 3) -> List[Dict]:
        """全A股按主力净流入/涨幅排序，返回 Top N 个股
        sort_by: inflow=主力净流入, change=涨幅
        fs: m:0+t:6 (深主板) + m:0+t:80 (创业板) + m:1+t:2 (沪主板) + m:1+t:23 (科创板)
        过滤: f:!50 排除ST
        """
        fid = "f62" if sort_by == "inflow" else "f3"
        # 沪深A股个股: m:0+t:6(深主板) m:0+t:80(创业板) m:1+t:2(沪主板) m:1+t:23(科创板)
        url = (f"https://push2.eastmoney.com/api/qt/clist/get"
               f"?cb=j&pn=1&pz={limit}&po=1&np=1&ut={self.ut}&fltt=2&invt=2"
               f"&fid={fid}&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
               f"&fields=f12,f14,f2,f3,f62,f184,f9,f23,f115,f20")
        headers = {'Referer': 'https://quote.eastmoney.com/', 'User-Agent': 'Mozilla/5.0'}
        for attempt in range(retries):
            try:
                async with _make_session() as session:
                    async with session.get(url, headers=headers) as resp:
                        text = await resp.text()
                        json_str = text.replace("j(", "").rstrip(");")
                        data = json.loads(json_str)
                        result = []
                        if data.get("rc") == 0 and data.get("data", {}).get("diff"):
                            for d in data["data"]["diff"]:
                                code = d.get("f12", "")
                                if not code:
                                    continue
                                def _safe_float(v, default=0):
                                    try: return float(v) if v is not None and v != '-' else default
                                    except (ValueError, TypeError): return default
                                result.append({
                                    "code":         code,
                                    "name":         d.get("f14", ""),
                                    "price":        _safe_float(d.get("f2")),
                                    "change_pct":   _safe_float(d.get("f3")),
                                    "net_inflow":   _safe_float(d.get("f62")),
                                    "inflow_rate":  _safe_float(d.get("f184")),
                                    "pe_ttm":       _safe_float(d.get("f115")) or None,
                                    "pb":           _safe_float(d.get("f23")) or None,
                                    "market_cap_b": round(_safe_float(d.get("f20")) / 1e8, 1) if _safe_float(d.get("f20")) > 0 else None,
                                    "source":       "market_wide",
                                })
                        if result:
                            return result
                        if attempt < retries - 1:
                            await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"全A股排行获取失败 (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        return []

    async def get_market_flow(self) -> Dict:
        """获取大盘资金流向"""
        url = (f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
               f"?secid=1.000001&fields1=f1,f2,f3,f7"
               f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
               f"&klt=1&lmt=1&ut={self.ut}")
        
        headers = {
            'Referer': 'https://data.eastmoney.com/',
            'User-Agent': 'Mozilla/5.0'
        }
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json(content_type=None)
                    if data.get("rc") == 0 and data.get("data", {}).get("klines"):
                        # 取最新一条数据
                        latest = data["data"]["klines"][-1].split(",")
                        return {
                            "date": latest[0],
                            "main_inflow": float(latest[1]) if latest[1] != "-" else 0,
                            "main_outflow": float(latest[2]) if latest[2] != "-" else 0,
                            "main_net": float(latest[3]) if latest[3] != "-" else 0,
                            "retail_inflow": float(latest[4]) if latest[4] != "-" else 0,
                            "retail_outflow": float(latest[5]) if latest[5] != "-" else 0,
                            "retail_net": float(latest[6]) if latest[6] != "-" else 0
                        }
        except Exception as e:
            logger.warning(f"获取大盘资金流向失败: {e}")
            return {}
            
    async def get_dragon_tiger(self, date: str) -> List[Dict]:
        """获取龙虎榜数据
        date: YYYY-MM-DD格式
        """
        url = (f"https://datacenter-web.eastmoney.com/api/data/v1/get"
               f"?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
               f"&columns=SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_RATE,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,EXPLANATION,TRADE_DATE"
               f"&pageNumber=1&pageSize=50&sortColumns=BILLBOARD_NET_AMT&sortTypes=-1"
               f"&source=WEB&client=WEB"
               f"&filter=%28TRADE_DATE%3D%27{date}%27%29")
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                    data = await resp.json(content_type=None)
                    result = []
                    if data.get("success") and data.get("result", {}).get("data"):
                        for item in data["result"]["data"]:
                            result.append({
                                "code": item.get("SECURITY_CODE"),
                                "name": item.get("SECURITY_NAME_ABBR"),
                                "change_rate": item.get("CHANGE_RATE", 0),
                                "net_amount": item.get("BILLBOARD_NET_AMT", 0),
                                "buy_amount": item.get("BILLBOARD_BUY_AMT", 0),
                                "sell_amount": item.get("BILLBOARD_SELL_AMT", 0),
                                "reason": item.get("EXPLANATION", ""),
                                "date": item.get("TRADE_DATE")
                            })
                    return result
        except Exception as e:
            logger.warning(f"获取龙虎榜数据失败: {e}")
            return []
            
    async def get_fund_estimate(self, fund_code: str) -> Dict:
        """获取基金估值"""
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        headers = {'Referer': 'https://fund.eastmoney.com/'}
        
        try:
            async with _make_session() as session:
                async with session.get(url, headers=headers) as resp:
                    text = await resp.text()
                    # 解析JSONP
                    match = re.search(r'jsonpgz\((.*)\)', text)
                    if match:
                        data = json.loads(match.group(1))
                        return {
                            "fund_code": data.get("fundcode"),
                            "name": data.get("name"),
                            "net_value": float(data.get("dwjz", 0)),
                            "estimate_value": float(data.get("gsz", 0)),
                            "estimate_change_pct": float(data.get("gszzl", 0)),
                            "estimate_time": data.get("gztime")
                        }
        except Exception as e:
            logger.warning(f"获取基金估值失败 {fund_code}: {e}")
            return {}

    # ============================================================
    # 方法别名 - 兼容 main.py 中的调用
    # ============================================================

    async def get_quote(self, code: str) -> Optional[Dict]:
        """get_stock_quote 的别名"""
        return await self.get_stock_quote(code)

    async def get_kline(self, code: str, period: str = "1d", count: int = 100) -> List[Dict]:
        """get_kline_data 的别名，支持 period 字符串转换"""
        klt_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60",
                   "1d": "101", "1w": "102", "1M": "103"}
        klt = klt_map.get(period, "101")
        return await self.get_kline_data(code, klt=klt, limit=count)

    async def get_sector_list(self, sector_type: str = "industry") -> List[Dict]:
        """get_sector_ranking 的别名"""
        return await self.get_sector_ranking(sector_type)

    async def get_market_stats(self) -> Dict:
        """获取市场涨跌统计"""
        url = (f"https://push2.eastmoney.com/api/qt/clist/get"
               f"?pn=1&pz=1&po=1&np=1&ut={self.ut}&fltt=2&invt=2"
               f"&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
               f"&fields=f2,f3,f4,f12,f14&_=1")
        try:
            async with _make_session() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    total = data.get("data", {}).get("total", 0)
                    return {"total": total, "timestamp": __import__("datetime").datetime.now().isoformat()}
        except Exception as e:
            logger.warning(f"获取市场统计失败: {e}")
            return {}

    async def get_market_overview(self) -> Dict:
        """获取市场全貌数据（供 agents 分析用）"""
        indices = ["000001", "399001", "399006"]
        overview = {"indices": {}, "sectors": [], "flow": {}}
        for code in indices:
            quote = await self.get_stock_quote(code)
            if quote:
                overview["indices"][code] = quote
        overview["sectors"] = await self.get_sector_ranking()
        overview["flow"] = await self.get_market_flow()
        return overview

# 全局实例
eastmoney_api = EastmoneyAPI()