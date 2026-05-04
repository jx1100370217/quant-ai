# 🤖 QuantAI — AI-Powered Quantitative Trading System

> 16 World-Class Investment Master AI Agents collaborate in real-time to analyze China A-shares and select the best buy candidates from the entire market

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

[中文](./README.md) | [日本語](./README_JA.md) | [한국어](./README_KO.md)

---

## ✨ Key Features

### 🧠 16 Investment Master AI Agents
| Master | Style | Core Logic |
|--------|-------|------------|
| Warren Buffett | Value Investing | Moat, margin of safety, ROE, long-term holding |
| Charlie Munger | Contrarian Thinking | Multi-disciplinary mental models, inverse elimination |
| Ben Graham | Deep Value | Net asset discount, liquidation value |
| Michael Burry | Contrarian Short | Overlooked risks, market mispricing |
| Mohnish Pabrai | Concentrated Holdings | Low-risk high-return cloning strategy |
| Peter Lynch | Growth at Value | PEG < 1, consumer-driven, local advantage |
| Cathie Wood | Disruptive Innovation | AI/Genomics/Blockchain sectors |
| Phil Fisher | Growth Stocks | Competitive moat, management quality, R&D |
| Rakesh Jhunjhunwala | Emerging Markets | High growth, low valuation, economic cycles |
| Aswath Damodaran | Valuation Models | DCF/FCFF, industry comparative valuation |
| Stanley Druckenmiller | Macro Hedge | Trend following, liquidity analysis |
| Bill Ackman | Activist | Catalyst-driven, special situations |
| Technical Analyst | Quant Indicators | MACD/RSI/KDJ/Bollinger/Moving Averages |
| Fundamental Analyst | Financial Analysis | Valuation, financial health, industry comparison |
| Sentiment Analyst | Market Sentiment | Block trades, limit up/down, capital flow |
| Risk Manager | Risk Control | Volatility, drawdown, position limits |

### 🔥 Hot Sector Picks
From the **top net-inflow sectors**, quantitatively pre-screen constituent stocks, then have 16 masters score and select the best buy candidates.

### 🏆 Master Consensus Picks (All A-Shares)
From **5,500+ A-shares** net-inflow Top 30, quantitatively pre-screen then pass to 16 masters for analysis — not limited to any single sector, selecting the most master-endorsed picks across the entire market.

### 📅 Weekly Stock Advisor (V12b)
Fully automated two-stage mean-reversion system: scan the full A-share universe, rank deep-V rebound candidates, then generate an LLM weekly report.

```
~5,500 A-shares by turnover (Eastmoney clist, paged by 100)
                    ↓
        Exclude halted / ST / delisting-risk names
                    ↓
        Hard filter: 5-day low rebound ≥ 3.5%
                    ↓
        V7 deep-V reversal score (minimum ≥ 40)
          5-day rebound / 2-day momentum / 7-day decline depth
          volume ratio / volume confirmation / ATR-price ratio / RSI6
                    ↓
        Rank by reversal score, select Top 1-5
                    ↓
        Fixed weights: 35/25/20/12/8% normalized by pick count
                    ↓
        Target +5%; single-stock hard stop -6%
        Portfolio weekly drawdown ≤ -4% → next-day exit signal
                    ↓
        LLM buy thesis / risk notes / weekly report + Telegram push
```

### 📊 Portfolio Analysis
One-click analysis of current holdings by all 16 masters, each independently providing bullish/bearish/neutral signals with confidence and reasoning, auto-generating composite decisions.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│           Next.js 14 Frontend (Bloomberg-style)   │
│  MarketOverview │ AgentDecisions │ PortfolioPanel  │
│  WeeklyAdvisor  │ RiskGauge      │ Dashboard       │
└───────────────────────┬──────────────────────────┘
                        │  REST API / WebSocket
┌───────────────────────▼──────────────────────────┐
│              FastAPI Backend (Python 3.10+)        │
├──────────────────┬───────────────────────────────┤
│   📡 Data Layer   │      🤖 AI Agent Layer         │
│  Eastmoney API   │  16 Masters + 4 Analyst Agents │
│  ├ Real-time     │  asyncio.gather concurrency     │
│  ├ K-line        │  Independent analysis → batch   │
│  ├ Sector rank   │  Merge → score → final decision │
│  ├ All A-shares  │                                 │
│  └ Capital flow  │  LLM: Claude Sonnet 4.6         │
├──────────────────┤  Concurrency: to_thread × 4     │
│   🔐 LLM Layer   ├────────────────────────────────┤
│  llm/client.py   │  📅 Weekly Stock Advisor         │
│  Structured out  │  Full-market reversal→Top5→Report │
│  API Key/OAuth   │  V12b + portfolio stop monitor   │
└──────────────────┴────────────────────────────────┘
```

---

## 🚀 Quick Start

### Requirements
- Python 3.10+
- Node.js 18+
- Anthropic API Key or Claude Code Max OAuth Token

### 1. Clone & Install

```bash
git clone https://github.com/jx1100370217/quant-ai.git
cd quant-ai
bash scripts/setup.sh
```

### 2. Configure LLM Authentication

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`, choose **one** of the following:

```bash
# Option 1: Standard Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# Option 2: Claude Code Max OAuth Token (larger free quota)
ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx
```

### 3. Start

```bash
bash scripts/start.sh
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## 📡 API Endpoints

### Market Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/market/overview` | GET | Major indices overview |
| `/api/market/sectors` | GET | Sector capital ranking |
| `/api/stock/{code}/quote` | GET | Real-time stock quote |
| `/api/stock/{code}/kline` | GET | K-line historical data |

### AI Agents

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/analyze-holdings` | POST | 16 masters analyze holdings (~30s) |
| `/api/agents/market-picks` | POST | All A-shares + sector dual-path picks (~40s) |
| `/api/agents/decisions` | GET | Historical decision records |

### Weekly Advisor

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/weekly-advisor/generate` | POST | Generate weekly reversal report (~90-120s) |
| `/api/weekly-advisor/latest` | GET | Get latest weekly report (daily cache) |
| `/api/weekly-advisor/portfolio-stop/status` | GET | Get active weekly portfolio stop state |
| `/api/weekly-advisor/portfolio-stop/check` | GET | Check portfolio-level -4% weekly stop once |
| `/api/weekly-advisor/portfolio-stop/clear` | POST | Clear active weekly portfolio state |

---

## ⚡ Performance

| Operation | Old (Serial) | Current (Concurrent) |
|-----------|-------------|---------------------|
| Holdings Analysis (16 Agents) | ~80s | **~30s** |
| All A-shares Selection | Timeout (>120s) | **~40s** |
| Weekly Stock Report | — | **~90-120s** |
| LLM Model | claude-opus-4 | **claude-sonnet-4-6** |
| LLM Concurrency | 2 | **4** |

---

## ⚠️ Disclaimer

This system is for **educational and research purposes only** and does not constitute any investment advice. AI analysis results have limitations. Markets carry risk — invest cautiously.

---

*Made with ❤️ by [jx1100370217](https://github.com/jx1100370217)*
