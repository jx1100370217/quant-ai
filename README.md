# 🤖 QuantAI — AI量化交易分析系统

> 16位全球顶级投资大师 AI Agent 协作，实时分析A股，从全市场中精选买入候选

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

[English](./README_EN.md) | [日本語](./README_JA.md) | [한국어](./README_KO.md)

---

## ✨ 核心功能

### 🧠 16位投资大师 AI Agent
| 大师 | 流派 | 核心逻辑 |
|------|------|----------|
| Warren Buffett | 价值投资 | 护城河、安全边际、ROE、长期持有 |
| Charlie Munger | 逆向思维 | 多元思维模型、反向排除 |
| Ben Graham | 深度价值 | 净资产折价、清算价值 |
| Michael Burry | 逆势做空 | 被忽视的风险、市场错误定价 |
| Mohnish Pabrai | 集中持仓 | 低风险高回报克隆策略 |
| Peter Lynch | 成长价值 | PEG < 1、消费驱动、局部优势 |
| Cathie Wood | 颠覆性创新 | AI/基因/区块链赛道 |
| Phil Fisher | 成长股 | 竞争壁垒、管理层质量、研发投入 |
| Rakesh Jhunjhunwala | 新兴市场 | 高成长低估值、经济周期把握 |
| Aswath Damodaran | 估值模型 | DCF/FCFF、行业比较估值 |
| Stanley Druckenmiller | 宏观对冲 | 趋势跟踪、流动性分析 |
| Bill Ackman | 激进主义 | 催化剂驱动、特殊事件 |
| 技术分析师 | 量化指标 | MACD/RSI/KDJ/布林带/均线系统 |
| 基本面分析师 | 财务分析 | 估值、财务健康、行业对比 |
| 情绪分析师 | 市场情绪 | 龙虎榜、涨跌停、资金流向 |
| 风险管理师 | 风控 | 波动率、回撤、仓位上限 |

### 🔥 热门板块精选
从**净流入最大板块**的成分股中，经量化预筛后由16位大师综合评分，选出最优买入候选。

### 🏆 大师综合精选（全A股）
从**全A股5500+只股票**净流入 Top30 中，量化预筛后交由16位大师分析，不受单一板块限制，选出全市场最受大师认可的标的。

### 📅 周度选股顾问（NEW）
全自动四阶段选股系统，目标：**下周5%盈利**。

```
全A股净流入 Top50 + 动量股 + 龙虎榜 + 板块领涨
                    ↓
        Phase 1: 宽选候选池（~100只）
                    ↓
        Phase 2: 多因子量化预筛（8-12只）
          技术面: RSI/MACD/布林带/均线/成交量
          资金面: 主力净流入率/连续净流入天数
          基本面: PE/PB/市值流动性
          动量面: 5日涨幅/20日动量
                    ↓
        Phase 3: 16位AI大师评审
                    ↓
        Phase 4: 综合评分 + LLM周报生成
          综合评分 = 量化×0.3 + 大师共识×0.4 + 资金×0.2 + 技术×0.1
                    ↓
        ┌─────────────────────────┐
        │  📊 Top 3-5 推荐股      │
        │  目标价(+5%) / 止损(-3%) │
        │  仓位建议 / 风险提示     │
        │  大盘环境 / 策略要点     │
        └─────────────────────────┘
```

### 📊 持仓分析
对当前持仓股票一键调用16位大师，每人独立给出 bullish/bearish/neutral 信号、置信度和推理，综合决策自动生成。

---

## 🏗️ 技术架构

```
┌──────────────────────────────────────────────────┐
│            Next.js 14 前端 (Bloomberg风格UI)       │
│  MarketOverview │ AgentDecisions │ PortfolioPanel  │
│  WeeklyAdvisor  │ RiskGauge      │ Dashboard       │
└───────────────────────┬──────────────────────────┘
                        │  REST API / WebSocket
┌───────────────────────▼──────────────────────────┐
│              FastAPI 后端 (Python 3.10+)           │
├──────────────────┬───────────────────────────────┤
│   📡 数据层       │        🤖 AI Agent 层           │
│  东方财富 API     │  16位投资大师 + 4种分析Agent    │
│  ├ 实时行情       │  asyncio.gather 并发执行        │
│  ├ K线历史        │  每个Agent独立分析→批量LLM调用  │
│  ├ 板块排行       │  结果合并→综合评分→最终决策     │
│  ├ 全A股筛选      │                                │
│  └ 资金流向       │  LLM: Claude Sonnet 4.6        │
├──────────────────┤  并发: asyncio.to_thread × 4   │
│   🔐 LLM层       ├───────────────────────────────┤
│  llm/client.py   │  📅 周度选股顾问                │
│  支持结构化输出   │  宽选→量化预筛→大师评审→周报    │
│  API Key/OAuth   │  多因子评分 + LLM综合分析        │
└──────────────────┴───────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- Anthropic API Key 或 Claude Code Max OAuth Token

### 1. 克隆 & 安装

```bash
git clone https://github.com/jx1100370217/quant-ai.git
cd quant-ai
bash scripts/setup.sh
```

### 2. 配置 LLM 认证

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，填写以下**二选一**：

```bash
# 方式一：Anthropic 标准 API Key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# 方式二：Claude Code Max OAuth Token（免费额度更大）
ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx
```

### 3. 启动

```bash
bash scripts/start.sh
```

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

### 单独启动

```bash
# 后端
cd backend && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend && npm run dev
```

---

## 📡 API 接口

### 行情数据

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/market/overview` | GET | 三大指数概览 |
| `/api/market/sectors` | GET | 板块资金排行 |
| `/api/stock/{code}/quote` | GET | 个股实时行情 |
| `/api/stock/{code}/kline` | GET | K线历史数据 |
| `/api/fund/{code}/estimate` | GET | 基金净值估算 |

### AI Agent

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agents/analyze-holdings` | POST | 16大师分析持仓（~30s） |
| `/api/agents/market-picks` | POST | 全A股+板块双路精选（~40s） |
| `/api/agents/decisions` | GET | 历史决策记录 |

### 周度选股顾问

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/weekly-advisor/generate` | POST | 生成本周选股报告（~2min） |
| `/api/weekly-advisor/latest` | GET | 获取最新一期周报（当日缓存） |

### 持仓 & 信号

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/portfolio` | GET | 持仓数据（接入东方财富App） |
| `/api/signals` | GET | 交易信号历史 |
| `/ws/realtime` | WS | 实时行情推送 |

---

## 🎯 选股流程

### 实时精选（交易时段）
```
全A股净流入 Top30              热门板块 Top3 × 各取8只
        ↓                              ↓
   量化预筛（5只）               量化预筛（3只）
        ↓                              ↓
        └──────────── 合并去重 ─────────┘
                          ↓
              一次性调用16位大师分析
                          ↓
              ┌─────────────────────┐
              │  🏆 大师综合精选     │  ← 来自全A股路径
              │  (LLM×0.6 + 量化×0.2 + 净流入×0.2)
              ├─────────────────────┤
              │  🔥 热门板块精选     │  ← 来自板块路径
              │  (LLM综合评分最高)   │
              └─────────────────────┘
```

### 周度选股（每周生成）
```
Phase 1 宽选 → Phase 2 量化预筛 → Phase 3 大师评审 → Phase 4 LLM周报
  ~100只候选      8-12只精选        16位大师打分       Top 3-5 推荐
                                                    + 目标价/止损价
                                                    + 仓位/风险提示
```

**量化预评分维度**：主力净流入率、涨幅动量、PE合理区间(5-40x)、PB安全边际(<3)、市值流动性(20-500亿)、RSI/MACD/布林带技术信号

---

## ⚡ 性能

| 操作 | 旧版(串行) | 现版(并发) |
|------|-----------|-----------|
| 持仓分析(16Agent) | ~80s | **~30s** |
| 全A股精选 | 超时(>120s) | **~40s** |
| 周度选股报告 | — | **~2min** |
| LLM模型 | claude-opus-4 | **claude-sonnet-4-6** |
| LLM并发数 | 2 | **4** |

并发原理：`asyncio.to_thread` 包装同步 `call_llm`，16个 Agent 通过线程池真正并行执行，不阻塞事件循环。

---

## 📁 项目结构

```
quant-ai/
├── backend/
│   ├── main.py                 # FastAPI 入口 + 所有路由
│   ├── agents/                 # 16位投资大师 + 功能分析Agent
│   │   ├── warren_buffett.py
│   │   ├── charlie_munger.py
│   │   ├── technical_analyst.py
│   │   ├── risk_manager.py
│   │   └── ...（共16个）
│   ├── weekly_advisor/         # 📅 周度选股顾问模块
│   │   ├── advisor.py          # 核心顾问（四阶段选股流程）
│   │   ├── screener.py         # 量化筛选器（多因子打分）
│   │   └── models.py           # Pydantic数据模型
│   ├── llm/
│   │   └── client.py           # LLM客户端（API Key / OAuth双模式）
│   ├── models/
│   │   └── agent_models.py     # Pydantic输出模型
│   ├── data/
│   │   └── eastmoney.py        # 东方财富API（行情/K线/板块/全A股）
│   └── .env.example            # 配置模板
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── AgentDecisions.tsx   # 大师决策面板 + 精选卡片
│   │   │   ├── WeeklyAdvisor.tsx    # 📅 周度选股顾问面板
│   │   │   ├── PortfolioPanel.tsx   # 持仓概览
│   │   │   ├── MarketOverview.tsx   # 市场行情
│   │   │   └── Dashboard.tsx        # 主仪表盘
│   │   └── api/                     # Next.js API路由（代理后端）
│   └── package.json
└── scripts/
    ├── start.sh / stop.sh / setup.sh
    └── status.sh
```

---

## 🔧 配置说明

### LLM 模型切换

修改 `backend/llm/client.py`：

```python
DEFAULT_MODEL = "claude-sonnet-4-6"   # 当前（快速、低成本）
# DEFAULT_MODEL = "claude-opus-4-20250514"  # 最强但较慢
```

### 并发调整

```python
# backend/llm/client.py
_LLM_SEMAPHORE = threading.Semaphore(4)  # 同时最多4个LLM调用
_MIN_INTERVAL = 0.3                       # 调用间最小间隔(秒)
```

---

## ⚠️ 免责声明

本系统仅供**学习研究**使用，不构成任何投资建议。AI分析结果存在局限性，市场有风险，投资需谨慎。

---

*Made with ❤️ by [jx1100370217](https://github.com/jx1100370217)*
