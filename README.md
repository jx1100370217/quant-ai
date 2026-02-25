# 🤖 QuantAI - AI量化交易分析系统

基于多Agent协作的A股智能量化交易分析平台。

## ✨ 功能特性

- 🧠 **6大AI Agent协作决策** — 市场分析、技术面、基本面、情绪面、风控、组合管理
- 📊 **实时行情数据** — 接入东方财富/新浪/雪球三大数据源
- 📈 **板块资金热力图** — 可视化资金流向
- 🎯 **交易信号系统** — 多策略融合生成买卖信号
- 🛡️ **智能风控** — 仓位管理、回撤控制、集中度监控
- 🖥️ **科技感界面** — Bloomberg Terminal风格深色UI

## 🏗️ 架构

```
┌─────────────────────────────────────┐
│      Next.js 前端 (科技感UI)         │
└──────────────┬──────────────────────┘
               │ REST + WebSocket
┌──────────────▼──────────────────────┐
│         FastAPI 后端                 │
├─────────────┬───────────────────────┤
│ 📊 数据层    │  🤖 AI Agent 层       │
│ 东方财富API  │  市场/技术/基本面     │
│ 新浪(备用)   │  情绪/风控/组合经理   │
│ 雪球(备用)   │                      │
├─────────────┼───────────────────────┤
│ 📈 策略层    │  💾 模型层            │
│ 动量/均值回归│  持仓/信号/分析       │
│ 板块轮动    │                       │
│ 多因子      │                       │
└─────────────┴───────────────────────┘
```

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- npm 9+

### 安装
```bash
git clone <repo>
cd quant-ai
bash scripts/setup.sh
```

### 启动
```bash
bash scripts/start.sh
```

- 前端: http://localhost:3000
- 后端: http://localhost:8000
- API文档: http://localhost:8000/docs

### 单独启动

```bash
# 后端
cd backend && uvicorn main:app --reload --port 8000

# 前端
cd frontend && npm run dev
```

## 📡 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/market/overview` | GET | 大盘概览（三大指数） |
| `/api/market/sectors` | GET | 板块排行 |
| `/api/stock/{code}/quote` | GET | 个股实时行情 |
| `/api/stock/{code}/kline` | GET | K线历史数据 |
| `/api/analysis/run` | GET | 触发AI全量分析 |
| `/api/portfolio` | GET | 当前持仓 |
| `/api/portfolio/update` | POST | 更新持仓 |
| `/api/agents/decisions` | GET | Agent决策历史 |
| `/api/signals` | GET | 交易信号 |
| `/api/fund/{code}/estimate` | GET | 基金净值估算 |
| `/ws/realtime` | WS | 实时行情推送 |

## 🤖 AI Agent系统

| Agent | 职责 | 数据源 |
|-------|------|--------|
| 市场分析师 | 大盘方向、板块轮动、资金流向 | 东方财富板块数据 |
| 技术分析师 | MACD/RSI/KDJ/BOLL指标分析 | K线数据 |
| 基本面分析师 | 估值、财务、行业对比 | 财务数据 |
| 情绪分析师 | 龙虎榜、涨跌停、市场温度 | 龙虎榜数据 |
| 风险管理师 | 回撤控制、仓位管理 | 持仓数据 |
| 投资组合经理 | 综合决策、生成调仓指令 | 所有Agent输出 |

## ⚠️ 免责声明

本系统仅供学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。

---
Made with ❤️ by 小婧 (OpenClaw AI)
