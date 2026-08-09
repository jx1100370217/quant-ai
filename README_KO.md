# 🤖 QuantAI — AI 퀀트 트레이딩 분석 시스템

> A주 반전 시그널, 구체적인 공모펀드, 주요 암호화폐를 비교하는 통합 주간 리서치 터미널

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

[中文](./README.md) | [English](./README_EN.md) | [日本語](./README_JA.md)

---

## ✨ 핵심 기능

### 🧠 16명의 투자 마스터 AI 에이전트
| 마스터 | 스타일 | 핵심 로직 |
|--------|--------|-----------|
| Warren Buffett | 가치 투자 | 경제적 해자, 안전마진, ROE, 장기 보유 |
| Charlie Munger | 역발상 사고 | 다학제 멘탈 모델, 역소거법 |
| Ben Graham | 딥 밸류 | 순자산 할인, 청산 가치 |
| Michael Burry | 역발상 숏 | 간과된 리스크, 시장 오류 가격 |
| Mohnish Pabrai | 집중 투자 | 저위험 고수익 클론 전략 |
| Peter Lynch | 성장 가치 | PEG < 1, 소비자 주도, 지역 우위 |
| Cathie Wood | 파괴적 혁신 | AI/유전체/블록체인 섹터 |
| Phil Fisher | 성장주 | 경쟁 우위, 경영진 자질, R&D 투자 |
| Rakesh Jhunjhunwala | 신흥 시장 | 고성장·저평가, 경기 사이클 |
| Aswath Damodaran | 밸류에이션 모델 | DCF/FCFF, 산업 비교 밸류에이션 |
| Stanley Druckenmiller | 매크로 헤지 | 추세 추종, 유동성 분석 |
| Bill Ackman | 행동주의 | 카탈리스트 주도, 특수 상황 |
| 기술 분석가 | 정량 지표 | MACD/RSI/KDJ/볼린저/이동평균 |
| 펀더멘털 분석가 | 재무 분석 | 밸류에이션, 재무 건전성, 산업 비교 |
| 센티멘트 분석가 | 시장 심리 | 대량 거래, 상한가/하한가, 자금 흐름 |
| 리스크 매니저 | 리스크 관리 | 변동성, 드로다운, 포지션 상한 |

### 🔥 인기 섹터 엄선
**순유입 최대 섹터**의 구성 종목에서 정량 프리스크리닝 후 16명의 마스터가 종합 채점하여 최적의 매수 후보를 선정합니다.

### 🏆 마스터 종합 엄선 (전체 A주)
**전체 A주 5,500개 이상** 순유입 Top30에서 정량 프리스크리닝 후 16명의 마스터가 분석합니다. 단일 섹터에 국한되지 않고, 전체 시장에서 마스터들이 가장 인정하는 종목을 선정합니다.

### 📅 주간 종목 어드바이저 (V14 Research Baseline)
전체 A주에서 딥-V 반등 후보를 스캔하고, 반전 점수로 Top 후보를 선정해 LLM 주간 리포트를 생성하는 2단계 반전 전략입니다.

```
전체 A주 약 5,500개 (동방재부 clist, 100개/페이지, 거래대금순)
                    ↓
        거래정지 / ST / 상장폐지 위험 종목 제외
                    ↓
        하드 필터: 5일 저점 대비 반등 ≥ 3.5%
                    ↓
        V7 딥-V 반전 점수 (40점 이상)
          5일 반등 / 2일 모멘텀 / 7일 하락 깊이
          거래량 비율 / 거래량 확인 / ATR-가격 비율 / RSI6
                    ↓
        반전 점수순 Top 1-5 선정
                    ↓
        순위별 비중: 35/25/20/12/8% (미사용 비중은 현금 유지)
                    ↓
        목표 +5%; 단일 종목 -6% 하드 스톱
        주간 포트폴리오 손익 ≤ -4% → 익일 전량 청산 신호
                    ↓
        LLM 매수 근거 / 리스크 노트 / Telegram 알림
```

### 🌐 멀티에셋 주간 추천

- **A주 개별 종목**: 대형·중형주 딥-V 반전 후보에서 최대 5개를 선정하며, 후보가 부족하면 남는 비중을 현금으로 유지합니다.
- **구체적인 공모펀드**: “财通成长优选混合C(021528)”를 포함한 액티브 주식형 C클래스 34개 상품을 1주/1개월/3개월 수익률, 20/60일 추세, 플러스 주간 비율, 변동성, 드로다운, 청약 상태로 비교해 최대 5개 상품을 제시합니다.
- **주요 암호화폐**: BTC, ETH, SOL 등 유동성이 높은 USDT 현물 16개를 7/30일 모멘텀, 20/60일 추세, 거래량, 변동성, 드로다운으로 비교해 위험 조정 상위 최대 3개를 제시합니다.

세 자산군은 전략 버전, 캐시, append-only 추천 감사 로그를 각각 독립적으로 관리합니다. 펀드와 암호화폐 순위는 LLM에 의존하지 않으며 공개 시장 데이터로 다시 계산할 수 있습니다.
펀드 기준가 이력은 동방재부/天天基金 공개 데이터를, 암호화폐 일봉은 Binance Spot 공개 시장 데이터를 사용합니다. 캐시 데이터는 명시된 폴백으로만 사용합니다.

### 🧭 계좌 연동 없는 리서치 터미널

프론트엔드는 실제 증권 계좌나 보유 내역을 읽거나 표시하지 않습니다. 화면의 모든 비중은 연구용 모델 포트폴리오 배분이며 실제 계좌 상태가 아닙니다.

---

## 🏗️ 아키텍처

```
┌──────────────────────────────────────────────────┐
│        Next.js 14 프론트엔드 (리서치 터미널)         │
│  MarketOverview │ SectorFlow │ StrategyTelemetry  │
│  WeeklyAdvisor: A주 │ 공모펀드 │ 암호화폐           │
└───────────────────────┬──────────────────────────┘
                        │  REST API / WebSocket
┌───────────────────────▼──────────────────────────┐
│             FastAPI 백엔드 (Python 3.10+)          │
├──────────────────┬───────────────────────────────┤
│   📡 데이터 레이어 │     🤖 AI 에이전트 레이어      │
│  동방재부 API     │  16 마스터 + 4 분석 에이전트    │
│  실시간 시세      │  asyncio.gather 병렬 실행       │
│  K선/섹터         │  독립 분석→배치 LLM→통합 결정   │
│  전체 A주/펀드 NAV │  LLM: Claude Sonnet 4.6        │
├──────────────────┼───────────────────────────────┤
│ Binance Spot 일봉 │  📅 멀티에셋 주간 어드바이저      │
│  공개 시장 데이터 │  반전 │ 공모펀드 │ 암호화폐       │
└──────────────────┴───────────────────────────────┘
```

---

## 🚀 빠른 시작

### 필수 환경
- Python 3.10+
- Node.js 18+
- Anthropic API Key 또는 Claude Code Max OAuth Token

### 1. 클론 & 설치

```bash
git clone https://github.com/jx1100370217/quant-ai.git
cd quant-ai
bash scripts/setup.sh
```

### 2. LLM 인증 설정

```bash
cp backend/.env.example backend/.env
```

`backend/.env`를 편집하여 다음 중 하나를 설정:

```bash
# 방법 1: 표준 Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# 방법 2: Claude Code Max OAuth Token (무료 할당량이 더 큼)
ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx
```

### 3. 시작

```bash
bash scripts/start.sh
```

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:3000 |
| 백엔드 API | http://localhost:8000 |
| API 문서 | http://localhost:8000/docs |

---

## 📡 API 엔드포인트

### 주간 어드바이저

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/api/weekly-advisor/generate` | POST | A주 반전 리포트 생성 |
| `/api/weekly-advisor/latest` | GET | 최신 A주 주간 리포트 조회 |
| `/api/weekly-advisor/fund/generate` | POST | 구체적인 공모펀드를 비교하고 추천 생성 |
| `/api/weekly-advisor/fund/latest` | GET | 최신 펀드 리포트 조회 |
| `/api/weekly-advisor/crypto/generate` | POST | 주요 암호화폐를 비교하고 추천 생성 |
| `/api/weekly-advisor/crypto/latest` | GET | 최신 암호화폐 리포트 조회 |

---

## ⚡ 성능

| 작업 | 구버전 (직렬) | 현재 버전 (병렬) |
|------|-------------|-----------------|
| 전체 A주 선정 | 타임아웃(>120s) | **~40s** |
| 주간 종목 리포트 | — | **약90-120초** |
| 공모펀드 비교 | — | **일반적으로 30초 미만** |
| 암호화폐 교차 비교 | — | **일반적으로 15초 미만** |
| LLM 모델 | claude-opus-4 | **claude-sonnet-4-6** |
| LLM 병렬 수 | 2 | **4** |

---

## ⚠️ 면책 조항

본 시스템은 **학습 및 연구 목적**으로만 제공되며, 어떠한 투자 조언도 구성하지 않습니다. AI 분석 결과에는 한계가 있습니다. 시장에는 리스크가 있으므로 신중하게 투자하시기 바랍니다.

---

*Made with ❤️ by [jx1100370217](https://github.com/jx1100370217)*
