# 🤖 QuantAI — AI量的取引分析システム

> 世界トップクラスの16人の投資マスターAIエージェントが協力し、中国A株をリアルタイム分析、市場全体から最適な買い候補を精選

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

[中文](./README.md) | [English](./README_EN.md) | [한국어](./README_KO.md)

---

## ✨ 主な機能

### 🧠 16人の投資マスター AIエージェント
| マスター | スタイル | コアロジック |
|----------|----------|-------------|
| Warren Buffett | バリュー投資 | 経済的堀、安全余裕、ROE、長期保有 |
| Charlie Munger | 逆張り思考 | 多分野メンタルモデル、逆排除法 |
| Ben Graham | ディープバリュー | 純資産割引、清算価値 |
| Michael Burry | 逆張りショート | 見落とされたリスク、市場のミスプライシング |
| Mohnish Pabrai | 集中投資 | 低リスク・高リターンのクローン戦略 |
| Peter Lynch | 成長バリュー | PEG < 1、消費者主導、ローカル優位性 |
| Cathie Wood | 破壊的イノベーション | AI/ゲノム/ブロックチェーン分野 |
| Phil Fisher | 成長株 | 競争優位性、経営陣の質、R&D投資 |
| Rakesh Jhunjhunwala | 新興市場 | 高成長・低バリュエーション、景気サイクル |
| Aswath Damodaran | バリュエーションモデル | DCF/FCFF、業界比較バリュエーション |
| Stanley Druckenmiller | マクロヘッジ | トレンドフォロー、流動性分析 |
| Bill Ackman | アクティビスト | カタリスト駆動、特殊イベント |
| テクニカルアナリスト | 定量指標 | MACD/RSI/KDJ/ボリンジャー/移動平均 |
| ファンダメンタルアナリスト | 財務分析 | バリュエーション、財務健全性、業界比較 |
| センチメントアナリスト | 市場心理 | 大口取引、ストップ高/安、資金フロー |
| リスクマネージャー | リスク管理 | ボラティリティ、ドローダウン、ポジション上限 |

### 🔥 人気セクター精選
**純流入最大セクター**の構成銘柄から、定量プレスクリーニング後に16人のマスターが総合採点し、最適な買い候補を選出。

### 🏆 マスター総合精選（全A株）
**全A株5,500銘柄以上**の純流入Top30から、定量プレスクリーニング後に16人のマスターが分析。単一セクターに限定されず、市場全体で最もマスターに支持された銘柄を選出。

### 📅 週次銘柄アドバイザー（NEW）
全自動4フェーズ銘柄選定システム、目標：**週次5%の利益**。

```
全A株純流入Top50 + モメンタム株 + 大口取引 + セクターリーダー
                    ↓
        Phase 1: 広範候補プール（約100銘柄）
                    ↓
        Phase 2: マルチファクター定量スクリーニング（8-12銘柄）
          テクニカル: RSI/MACD/ボリンジャー/移動平均/出来高
          資金面: 主力純流入率/連続流入日数
          ファンダメンタル: PE/PB/時価総額・流動性
          モメンタム: 5日騰落率/20日モメンタム
                    ↓
        Phase 3: 16人のAIマスターレビュー
                    ↓
        Phase 4: 総合スコアリング + LLM週次レポート生成
          スコア = 定量×0.3 + マスター合意×0.4 + 資金×0.2 + テクニカル×0.1
                    ↓
        ┌──────────────────────────────┐
        │  📊 Top 3-5 推奨銘柄         │
        │  目標株価(+5%) / 損切り(-3%)  │
        │  ポジション提案 / リスク警告   │
        │  市場概況 / 戦略ノート         │
        └──────────────────────────────┘
```

### 📊 ポートフォリオ分析
現在の保有銘柄を16人のマスターがワンクリックで分析。各マスターが独立してbullish/bearish/neutralシグナル、信頼度、推論を提供し、総合判断を自動生成。

---

## 🏗️ アーキテクチャ

```
┌──────────────────────────────────────────────────┐
│        Next.js 14 フロントエンド (Bloomberg風UI)    │
│  MarketOverview │ AgentDecisions │ PortfolioPanel  │
│  WeeklyAdvisor  │ RiskGauge      │ Dashboard       │
└───────────────────────┬──────────────────────────┘
                        │  REST API / WebSocket
┌───────────────────────▼──────────────────────────┐
│            FastAPI バックエンド (Python 3.10+)      │
├──────────────────┬───────────────────────────────┤
│   📡 データ層     │      🤖 AIエージェント層        │
│  東方財富 API     │  16マスター + 4アナリスト       │
│  リアルタイム相場  │  asyncio.gather 並行実行       │
│  K線/セクター     │  独立分析→バッチLLM呼出→統合   │
│  全A株/資金フロー │  LLM: Claude Sonnet 4.6       │
├──────────────────┼───────────────────────────────┤
│   🔐 LLM層       │  📅 週次銘柄アドバイザー        │
│  構造化出力対応   │  広選→スクリーニング→レビュー→レポート │
└──────────────────┴───────────────────────────────┘
```

---

## 🚀 クイックスタート

### 必要環境
- Python 3.10+
- Node.js 18+
- Anthropic API Key または Claude Code Max OAuth Token

### 1. クローン & インストール

```bash
git clone https://github.com/jx1100370217/quant-ai.git
cd quant-ai
bash scripts/setup.sh
```

### 2. LLM認証の設定

```bash
cp backend/.env.example backend/.env
```

`backend/.env` を編集し、以下のいずれかを設定：

```bash
# 方法1：標準 Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# 方法2：Claude Code Max OAuth Token（無料枠が大きい）
ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx
```

### 3. 起動

```bash
bash scripts/start.sh
```

| サービス | URL |
|----------|-----|
| フロントエンド | http://localhost:3000 |
| バックエンドAPI | http://localhost:8000 |
| APIドキュメント | http://localhost:8000/docs |

---

## ⚡ パフォーマンス

| 操作 | 旧版（直列） | 現行版（並行） |
|------|-------------|---------------|
| 保有分析（16エージェント） | ~80s | **~30s** |
| 全A株精選 | タイムアウト(>120s) | **~40s** |
| 週次銘柄レポート | — | **約2分** |
| LLMモデル | claude-opus-4 | **claude-sonnet-4-6** |
| LLM並行数 | 2 | **4** |

---

## ⚠️ 免責事項

本システムは**学習・研究目的**のみに提供されており、いかなる投資助言も構成しません。AI分析結果には限界があります。投資にはリスクが伴います — 慎重に判断してください。

---

*Made with ❤️ by [jx1100370217](https://github.com/jx1100370217)*
