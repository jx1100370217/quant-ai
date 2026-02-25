import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Redis配置
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # FastAPI配置
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # 数据源配置
    EASTMONEY_HEADERS = {
        'Referer': 'https://quote.eastmoney.com/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    SINA_HEADERS = {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # 交易配置
    INITIAL_CAPITAL = 1000000  # 初始资金100万
    MAX_POSITION_SIZE = 0.2    # 单只股票最大仓位20%
    STOP_LOSS = 0.08          # 止损8%
    TAKE_PROFIT = 0.15        # 止盈15%
    
    # Agent配置
    ANALYSIS_INTERVAL = 300    # 分析间隔秒数
    MAX_STOCKS_TO_ANALYZE = 50 # 最多分析股票数量
    
    # 风险管理
    MAX_DRAWDOWN = 0.15       # 最大回撤15%
    VAR_CONFIDENCE = 0.95     # VaR置信度
    
config = Config()