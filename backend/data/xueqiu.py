import aiohttp
from typing import Dict, List, Optional

class XueqiuAPI:
    """雪球API接口 - 备用数据源"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://xueqiu.com/'
        }
        
    async def get_batch_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取实时行情"""
        # 雪球代码格式：SH600000, SZ000001
        xueqiu_codes = []
        for code in codes:
            if code.startswith(("600", "601", "603", "605", "688")):
                xueqiu_codes.append(f"SH{code}")
            else:
                xueqiu_codes.append(f"SZ{code}")
                
        url = f"https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={','.join(xueqiu_codes)}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    result = {}
                    
                    if data.get("error_code") == 0 and "data" in data:
                        for item in data["data"]:
                            # 提取6位代码
                            symbol = item["symbol"]
                            code = symbol[2:] if len(symbol) > 2 else symbol
                            
                            quote = item.get("quote", {})
                            result[code] = {
                                "code": code,
                                "name": quote.get("name", ""),
                                "price": quote.get("current", 0),
                                "change": quote.get("chg", 0),
                                "change_pct": quote.get("percent", 0) / 100,
                                "high": quote.get("high", 0),
                                "low": quote.get("low", 0),
                                "open": quote.get("open", 0),
                                "volume": quote.get("volume", 0),
                                "amount": quote.get("amount", 0),
                                "market_capital": quote.get("market_capital", 0),
                                "pe_ttm": quote.get("pe_ttm", 0),
                                "pb": quote.get("pb", 0)
                            }
                    return result
        except Exception as e:
            print(f"雪球行情获取失败: {e}")
            return {}
            
    async def get_stock_detail(self, code: str) -> Optional[Dict]:
        """获取个股详细信息"""
        symbol = f"SH{code}" if code.startswith(("600", "601", "603", "605", "688")) else f"SZ{code}"
        url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    
                    if data.get("error_code") == 0 and "data" in data:
                        quote = data["data"]["quote"]
                        return {
                            "code": code,
                            "name": quote.get("name"),
                            "current": quote.get("current"),
                            "percent": quote.get("percent", 0) / 100,
                            "chg": quote.get("chg"),
                            "high": quote.get("high"),
                            "low": quote.get("low"),
                            "open": quote.get("open"),
                            "last_close": quote.get("last_close"),
                            "volume": quote.get("volume"),
                            "amount": quote.get("amount"),
                            "market_capital": quote.get("market_capital"),
                            "float_market_capital": quote.get("float_market_capital"),
                            "pe_ttm": quote.get("pe_ttm"),
                            "pb": quote.get("pb"),
                            "eps": quote.get("eps"),
                            "dividend_yield": quote.get("dividend_yield")
                        }
        except Exception as e:
            print(f"雪球股票详情获取失败 {code}: {e}")
            return None

# 全局实例
xueqiu_api = XueqiuAPI()