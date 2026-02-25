import aiohttp
import json
from typing import Dict, List, Optional
from config import config

class SinaAPI:
    """新浪财经API接口 - 备用数据源"""
    
    def __init__(self):
        self.headers = config.SINA_HEADERS
        
    async def get_sector_flow(self, sector_type: int = 0) -> List[Dict]:
        """获取板块资金流向
        sector_type: 0=行业, 1=概念
        """
        url = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"MoneyFlow.ssl_bkzj_bk?page=1&num=20&sort=netamount&asc=0&fenlei={sector_type}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json(content_type=None)
                    result = []
                    for item in data:
                        result.append({
                            "code": item.get("code"),
                            "name": item.get("name"),
                            "net_amount": float(item.get("netamount", 0)),
                            "buy_amount": float(item.get("buyamount", 0)),
                            "sell_amount": float(item.get("sellamount", 0)),
                            "change_pct": float(item.get("updownpercent", 0))
                        })
                    return result
        except Exception as e:
            print(f"新浪板块资金流向获取失败: {e}")
            return []
            
    async def get_realtime_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        """获取实时行情"""
        # 新浪股票代码格式转换
        sina_codes = []
        for code in codes:
            if code.startswith(("600", "601", "603", "605", "688")):
                sina_codes.append(f"sh{code}")
            else:
                sina_codes.append(f"sz{code}")
                
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as resp:
                    text = await resp.text(encoding='gbk')
                    result = {}
                    
                    for line in text.strip().split('\n'):
                        if 'var hq_str_' in line:
                            # 解析新浪行情数据
                            parts = line.split('="')
                            if len(parts) >= 2:
                                code_part = parts[0].split('_')[-1]
                                data_part = parts[1].rstrip('";')
                                fields = data_part.split(',')
                                
                                if len(fields) >= 32:
                                    # 提取6位数字代码
                                    code = code_part[2:] if len(code_part) > 2 else code_part
                                    result[code] = {
                                        "name": fields[0],
                                        "open": float(fields[1]) if fields[1] else 0,
                                        "pre_close": float(fields[2]) if fields[2] else 0,
                                        "price": float(fields[3]) if fields[3] else 0,
                                        "high": float(fields[4]) if fields[4] else 0,
                                        "low": float(fields[5]) if fields[5] else 0,
                                        "volume": int(fields[8]) if fields[8] else 0,
                                        "amount": float(fields[9]) if fields[9] else 0,
                                        "date": fields[30],
                                        "time": fields[31]
                                    }
                    return result
        except Exception as e:
            print(f"新浪实时行情获取失败: {e}")
            return {}

# 全局实例
sina_api = SinaAPI()