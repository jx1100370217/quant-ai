import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # LLM 配置
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-4-20250514")
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    
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
    
    # Agent 权重配置（用于信号汇总参考）
    AGENT_WEIGHTS = {
        # 量化支撑
        "TechnicalAnalyst":     0.06,
        "FundamentalAnalyst":   0.06,
        "SentimentAnalyst":     0.05,
        "RiskManager":          0.07,
        # 价值派
        "WarrenBuffett":        0.08,
        "CharlieMunger":        0.07,
        "BenGraham":            0.07,
        "MichaelBurry":         0.06,
        "MohnishPabrai":        0.06,
        # 成长派
        "PeterLynch":           0.07,
        "CathieWood":           0.06,
        "PhilFisher":           0.06,
        "RakeshJhunjhunwala":   0.06,
        # 宏观/激进派
        "AswathDamodaran":      0.07,
        "StanleyDruckenmiller": 0.07,
        "BillAckman":           0.07,
    }
    
    # 风险管理
    MAX_DRAWDOWN = 0.15       # 最大回撤15%
    VAR_CONFIDENCE = 0.95     # VaR置信度
    
config = Config()
