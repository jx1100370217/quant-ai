# 🤖 QuantAI — AI量化交易分析系统

> A股反转因子策略 + 16位AI投资大师协作 + LLM智能周报，全自动量化选股

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

[English](./README_EN.md) | [日本語](./README_JA.md) | [한국어](./README_KO.md)

---

## ✨ 核心功能

### 📈 周度反转因子策略（V12b 当前生产版）

系统核心策略已从动量策略升级为**反转因子策略**，基于A股市场的均值回归效应：

**策略原理**：全A股按成交额拉取约 5500 只股票，寻找短期深V反弹形态：近5日低点反弹幅度 ≥ 3.5%，并通过 2日动量、7日跌幅深度、量比、ATR/价格、RSI6 等指标打分；反转分 ≥ 40 才进入候选池。

```
全A股约 5500 只股票（东方财富 clist 分页，每页最多100只，按成交额降序）
                    ↓
        工程过滤：停牌 / ST / 退市流程股票剔除
                    ↓
        硬过滤：5日低点反弹 ≥ 3.5%
                    ↓
        V7 深V反弹评分（反转分 ≥ 40 入选）
          5日低点反弹: 0~20
          2日动量: 0~12
          7日跌幅深度: 2~8（加分项，不再硬过滤）
          量比 vs 5日均量: 4~18（加分项，不再硬过滤）
          当日量 > 昨日量: +6
          14日 ATR/价格: 0~12
          RSI6 超卖: 0~10
                    ↓
        按反转分排序取 Top 5 + LLM 周报生成
                    ↓
        ┌──────────────────────────┐
        │  📊 Top 1-5 反转候选      │
        │  权重 35/25/20/12/8%      │
        │  目标价(+5%) / 单股止损(-6%) │
        │  组合回撤≤-4% 次日清仓信号 │
        └──────────────────────────┘
```

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

### 📊 大盘概览 & 行业轮动

实时展示三大指数（上证、深证、创业板）行情 + 行业板块资金流向排行，数据通过后端代理东方财富API获取，含多级容错（push2实时接口 → datacenter备用 → 新浪财经 → 本地持久化缓存）。

### 📅 周度选股顾问

全自动两阶段反转选股系统：全A股反转扫描 → Top 5 加权组合 + LLM报告生成，结果自动推送至 Telegram，并记录活跃持仓用于组合级 -4% 周内止损监控。

### 📊 持仓分析

对当前持仓股票一键调用16位大师，每人独立给出 bullish/bearish/neutral 信号、置信度和推理，综合决策自动生成。

---

## 🏗️ 技术架构

```
┌──────────────────────────────────────────────────┐
│            Next.js 14 前端 (Bloomberg风格UI)       │
│  MarketOverview │ SectorFlow   │ PortfolioPanel   │
│  WeeklyAdvisor  │ RiskGauge    │ Dashboard         │
└───────────────────────┬──────────────────────────┘
                        │  REST API (前端代理后端)
┌───────────────────────▼──────────────────────────┐
│              FastAPI 后端 (Python 3.10+)           │
├──────────────────┬───────────────────────────────┤
│   📡 数据层       │        🤖 AI Agent 层           │
│  东方财富 API     │  16位投资大师 + 4种分析Agent    │
│  ├ 实时行情       │  asyncio.gather 并发执行        │
│  ├ K线历史        │  每个Agent独立分析→批量LLM调用  │
│  ├ 板块排行(多源) │  结果合并→综合评分→最终决策     │
│  ├ 全A股分页扫描  │                                │
│  └ 资金流向       │  LLM: Claude Sonnet 4.6        │
├──────────────────┤  并发: asyncio.to_thread × 4   │
│   🔐 LLM层       ├───────────────────────────────┤
│  llm/client.py   │  📅 反转策略选股顾问             │
│  支持结构化输出   │  反转扫描→因子评分→LLM周报      │
│  API Key/OAuth   │  Telegram自动推送               │
├──────────────────┼───────────────────────────────┤
│   💾 缓存层       │  🔄 容错机制                     │
│  内存缓存(60s)   │  板块数据: push2→datacenter     │
│  日内LLM缓存     │   →新浪财经→本地JSON持久化      │
│  持久化JSON(7天) │  aiohttp: trust_env=False       │
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
| `/api/market/overview` | GET | 三大指数 + 板块排行 + 市场统计 |
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

### 周度反转选股顾问

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/weekly-advisor/generate` | POST | 生成反转选股报告（约90-120s，前端超时保护8min） |
| `/api/weekly-advisor/latest` | GET | 获取最新一期周报（当日缓存） |
| `/api/weekly-advisor/portfolio-stop/status` | GET | 查看当前周度推荐组合止损状态 |
| `/api/weekly-advisor/portfolio-stop/check` | GET | 手动检查一次组合级 -4% 周内止损 |
| `/api/weekly-advisor/portfolio-stop/clear` | POST | 手动清空活跃推荐组合状态 |

### 持仓 & 信号

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/portfolio` | GET | 持仓数据（接入东方财富App） |
| `/api/signals` | GET | 交易信号历史 |
| `/ws/realtime` | WS | 实时行情推送 |

---

## 🎯 选股流程

### 周度反转策略选股（V12b）
```
全A股按成交额降序拉取约5500只（每页100只，push2/push2delay fallback）
                ↓
        剔除停牌、ST、退市流程股票
                ↓
        拉取最近30根日K（实际评分至少需要20根）
                ↓
        V7 深V反弹评分:
          · 硬过滤：5日低点反弹 ≥ 3.5%
          · 反弹强度 / 2日动量 / 7日跌幅深度
          · 量比、放量确认、ATR波动率、RSI6超卖
          · 反转分 ≥ 40 才入选
                ↓
        按反转分排序，取 Top 5（不足5只则按实际数量）
                ↓
        固定权重：35/25/20/12/8%（按Top数量归一化）
                ↓
        LLM 生成买入理由 / 风险提示 / 反转解释
                ↓
        目标价 = 当前价 × 1.05；单股止损价 = 当前价 × 0.94
                ↓
        Telegram 自动推送 + 保存 active_positions.json
                ↓
        交易时段每5分钟检查组合浮亏；≤ -4% 触发“次日清仓”信号
```

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
              │  🏆 大师综合精选     │
              │  🔥 热门板块精选     │
              └─────────────────────┘
```

---

## ⚡ 性能

| 操作 | 旧版(串行) | 现版(并发) |
|------|-----------|-----------|
| 持仓分析(16Agent) | ~80s | **~30s** |
| 全A股精选 | 超时(>120s) | **~40s** |
| 反转扫描+周报 | — | **~90-120s** |
| 全A股 universe 拉取(约5500只) | — | **~10-20s** |
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
│   ├── weekly_advisor/         # 📅 反转策略选股顾问模块
│   │   ├── advisor.py          # 核心顾问（反转扫描→评分→LLM周报）
│   │   ├── screener.py         # V7 深V反弹筛选器（bounce/动量/量比/ATR/RSI6）
│   │   ├── portfolio_monitor.py # V12b 组合级 -4% 周内止损监控
│   │   └── models.py           # Pydantic数据模型
│   ├── llm/
│   │   └── client.py           # LLM客户端（API Key / OAuth双模式）
│   ├── models/
│   │   ├── agent_models.py     # Pydantic输出模型
│   │   └── signal.py           # 交易信号模型
│   ├── data/
│   │   └── eastmoney.py        # 东方财富API（行情/K线/板块/全A股分页）
│   ├── cache/                  # 持久化缓存（板块数据等）
│   ├── utils/
│   │   └── telegram.py         # Telegram推送
│   └── .env.example            # 配置模板
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── AgentDecisions.tsx   # 大师决策面板 + 精选卡片
│   │   │   ├── WeeklyAdvisor.tsx    # 📅 反转选股顾问面板
│   │   │   ├── SectorFlow.tsx       # 行业轮动资金流向
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

### 东方财富数据源容错

板块排行数据采用四级容错策略：
1. **push2实时接口**（交易时段优先）— 独立session + 3次重试
2. **datacenter接口**（urllib绕过aiohttp）
3. **新浪财经接口**（备用数据源）
4. **本地JSON持久化缓存**（7天有效，周末/节假日兜底）

---

## 📋 更新日志

### v2.1 — V12b 周度反转策略
- 周度选股切换到 V12b：5日低点反弹 ≥ 3.5% + 反转分 ≥ 40
- 全A股 universe 扩展到约5500只，按成交额分页拉取并支持 push2/push2delay fallback
- Top 5 固定加权 35/25/20/12/8%，目标 +5%，单股 -6% 硬止损
- 新增组合级周内止损监控：组合加权浮亏 ≤ -4% 触发“次日清仓”信号

### v2.0 — 反转策略重构
- 周度选股从四阶段动量策略重构为两阶段反转因子策略
- 前端市场API改为代理后端，解决系统代理导致的请求失败
- 板块数据四级容错（push2→datacenter→新浪→本地缓存）
- LLM调用优化（max_tokens 200000→4096），修复流式超时错误
- 新增 Telegram 自动推送选股结果

### v1.0 — 初始版本
- 16位AI投资大师Agent并发分析
- 东方财富实时行情 + K线数据
- 全A股+热门板块双路精选
- Bloomberg风格 Next.js 14 前端

---

## ⚠️ 免责声明

本系统仅供**学习研究**使用，不构成任何投资建议。AI分析结果存在局限性，市场有风险，投资需谨慎。

---

*Made with ❤️ by [jx1100370217](https://github.com/jx1100370217)*
