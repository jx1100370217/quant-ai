'use client'

import { useState, useEffect } from 'react'
import { Brain, Zap, Loader2, ChevronDown, ChevronUp, TrendingUp, BarChart2, BookOpen, MessageCircle, ShieldAlert, Star } from 'lucide-react'

interface StockQuote {
  code: string; symbol?: string; current: number; percent: number; chg: number
  high: number; low: number; open: number; last_close: number; volume?: number; amount?: number; turnover_rate?: number
}

interface AgentAnalysis {
  agent: string
  icon: any
  color: string
  bgColor: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  points: string[]
}

interface StockAnalysis {
  code: string
  name: string
  price: number
  change: number
  pnlPct: number
  overallSignal: 'buy' | 'sell' | 'hold'
  overallConfidence: number
  agents: AgentAnalysis[]
}

interface BuyCandidate {
  code: string; name: string; price: number; change: number
  sectorName: string; reasons: string[]; score: number
}

const HOLDINGS = [
  { code: '300394', name: '天孚通信', cost: 280.50 },
  { code: '002916', name: '深南电路', cost: 220.00 },
  { code: '600183', name: '生益科技', cost: 58.30 },
  { code: '300308', name: '中际旭创', cost: 510.00 },
  { code: '002463', name: '沪电股份', cost: 65.40 },
  { code: '300502', name: '新易盛', cost: 350.00 },
]

const signalConfig = {
  buy:  { label: '买入', emoji: '▲', text: 'text-red-400',    bg: 'bg-red-900/20',    border: 'border-red-500/40' },
  sell: { label: '卖出', emoji: '▼', text: 'text-green-400',  bg: 'bg-green-900/20',  border: 'border-green-500/40' },
  hold: { label: '持有', emoji: '─', text: 'text-yellow-400', bg: 'bg-yellow-900/20', border: 'border-yellow-500/40' },
}

// ─── 各分析师逻辑 ──────────────────────────────────────────────
function runMarketAnalyst(q: StockQuote, marketData: any): AgentAnalysis {
  const points: string[] = []
  let score = 0

  const sh = marketData?.indices?.['000001']
  const shChange = sh?.change_pct ?? 0
  if (shChange > 0.5) { points.push(`大盘上涨 +${shChange.toFixed(2)}%，市场整体偏多`); score += 2 }
  else if (shChange < -0.5) { points.push(`大盘下跌 ${shChange.toFixed(2)}%，市场情绪偏弱`); score -= 2 }
  else { points.push(`大盘震荡 ${shChange >= 0 ? '+' : ''}${shChange.toFixed(2)}%，方向不明`); }

  const sectors: any[] = marketData?.sectors ?? []
  const topSector = sectors[0]
  if (topSector) {
    const inSector = q.percent > 0 && q.change > 0
    if (inSector) { points.push(`今日领涨板块「${topSector.name}」，个股走势与板块共振`); score += 1 }
    else { points.push(`今日领涨板块「${topSector.name}」，个股未能跟随强势板块`) }
  }

  const upSectors = sectors.filter((s: any) => s.change_pct > 0).length
  const ratio = sectors.length > 0 ? upSectors / sectors.length : 0.5
  if (ratio > 0.7) { points.push(`板块普涨（涨跌比 ${upSectors}:${sectors.length - upSectors}），行情扩散良好`); score += 1 }
  else if (ratio < 0.3) { points.push(`板块普跌（涨跌比 ${upSectors}:${sectors.length - upSectors}），需谨慎操作`); score -= 1 }
  else { points.push(`板块分化（涨跌比 ${upSectors}:${sectors.length - upSectors}），结构性行情`) }

  const signal = score >= 2 ? 'buy' : score <= -2 ? 'sell' : 'hold'
  const confidence = Math.min(85, 55 + Math.abs(score) * 8)
  return { agent: 'MarketAnalyst', icon: TrendingUp, color: 'text-cyan-400', bgColor: 'bg-cyan-900/10', signal, confidence, points }
}

function runTechAnalyst(q: StockQuote): AgentAnalysis {
  const points: string[] = []
  let score = 0

  // 日内位置
  const dayRange = q.high > q.low ? ((q.current - q.low) / (q.high - q.low)) * 100 : 50
  if (dayRange > 75) { points.push(`日内位置偏高 ${dayRange.toFixed(0)}%，站稳日内高位，多头强势`); score += 1 }
  else if (dayRange < 25) { points.push(`日内位置偏低 ${dayRange.toFixed(0)}%，在日内低位徘徊，空头压力`); score -= 1 }
  else { points.push(`日内位置居中 ${dayRange.toFixed(0)}%，多空力量均衡`) }

  // 今日涨跌幅
  if (q.percent > 5) { points.push(`涨幅强势 +${q.percent.toFixed(2)}%，突破性上攻信号`); score += 2 }
  else if (q.percent > 2) { points.push(`稳步上涨 +${q.percent.toFixed(2)}%，趋势延续中`); score += 1 }
  else if (q.percent < -5) { points.push(`大幅下跌 ${q.percent.toFixed(2)}%，破位风险`); score -= 2 }
  else if (q.percent < -2) { points.push(`小幅下跌 ${q.percent.toFixed(2)}%，注意支撑位`); score -= 1 }
  else { points.push(`涨跌幅 ${q.percent >= 0 ? '+' : ''}${q.percent.toFixed(2)}%，价格平稳整理`) }

  // 振幅分析
  const amplitude = q.high > 0 ? ((q.high - q.low) / q.last_close) * 100 : 0
  if (amplitude > 5) { points.push(`振幅 ${amplitude.toFixed(1)}%，今日波动剧烈，注意风险`) }
  else if (amplitude < 2) { points.push(`振幅 ${amplitude.toFixed(1)}%，缩量整理，等待突破方向`) }
  else { points.push(`振幅 ${amplitude.toFixed(1)}%，正常波动区间`) }

  const signal = score >= 2 ? 'buy' : score <= -2 ? 'sell' : 'hold'
  const confidence = Math.min(88, 58 + Math.abs(score) * 8)
  return { agent: 'TechAnalyst', icon: BarChart2, color: 'text-blue-400', bgColor: 'bg-blue-900/10', signal, confidence, points }
}

function runFundAnalyst(q: StockQuote, h: { cost: number }): AgentAnalysis {
  const points: string[] = []
  let score = 0
  const pnlPct = ((q.current - h.cost) / h.cost) * 100

  // 总收益
  if (pnlPct > 30) { points.push(`累计盈利 +${pnlPct.toFixed(1)}%，持股收益丰厚，关注估值泡沫`); score -= 1 }
  else if (pnlPct > 10) { points.push(`累计盈利 +${pnlPct.toFixed(1)}%，持仓成本优势明显`); score += 1 }
  else if (pnlPct > 0) { points.push(`小幅盈利 +${pnlPct.toFixed(1)}%，持股基本面支撑价格`) }
  else if (pnlPct < -10) { points.push(`累计亏损 ${pnlPct.toFixed(1)}%，成本倒挂，考虑止损策略`); score -= 2 }
  else { points.push(`轻微亏损 ${pnlPct.toFixed(1)}%，在正常波动范围内`) }

  // 成本价vs现价关系
  const costRatio = (q.current / h.cost - 1) * 100
  if (costRatio > 20) { points.push(`当前价格是成本价 ${(q.current / h.cost).toFixed(2)}倍，可分批止盈`) }
  else if (costRatio < -10) { points.push(`价格低于成本 ${Math.abs(costRatio).toFixed(1)}%，可考虑摊低成本`) }
  else { points.push(`成本价 ${h.cost.toFixed(2)} vs 现价 ${q.current.toFixed(2)}，持仓安全边际尚可`) }

  // 量价关系（用涨跌推断）
  if (q.percent > 3) { points.push(`今日放量上涨，基本面催化剂可能驱动`) }
  else if (q.percent < -3) { points.push(`今日放量下跌，关注是否有利空消息`) }
  else { points.push(`价格温和变动，等待下季度财报催化`) }

  const signal = score >= 1 ? 'buy' : score <= -2 ? 'sell' : 'hold'
  const confidence = Math.min(80, 52 + Math.abs(score) * 8)
  return { agent: 'FundAnalyst', icon: BookOpen, color: 'text-purple-400', bgColor: 'bg-purple-900/10', signal, confidence, points }
}

function runSentimentAnalyst(q: StockQuote, marketData: any): AgentAnalysis {
  const points: string[] = []
  let score = 0

  // 今日人气
  if (q.percent > 7) { points.push(`今日涨幅 +${q.percent.toFixed(2)}%，短期人气极旺，龙头效应`); score += 2 }
  else if (q.percent > 3) { points.push(`今日上涨 +${q.percent.toFixed(2)}%，市场关注度提升`); score += 1 }
  else if (q.percent < -5) { points.push(`今日跌幅 ${q.percent.toFixed(2)}%，情绪恐慌，或超跌机会`); score -= 1 }
  else { points.push(`今日涨跌 ${q.percent >= 0 ? '+' : ''}${q.percent.toFixed(2)}%，市场情绪平稳`) }

  // 板块资金流向
  const sectors: any[] = marketData?.sectors ?? []
  const topSector = sectors[0]
  if (topSector && topSector.net_inflow > 5e8) {
    points.push(`所属板块主力净流入 ${(topSector.net_inflow / 1e8).toFixed(1)}亿，机构积极布局`); score += 1
  } else if (topSector) {
    points.push(`板块资金整体活跃，${topSector.name} 领涨`)
  }

  // 大盘情绪
  const sh = marketData?.indices?.['000001']
  if (sh && sh.change_pct > 1) { points.push(`大盘强势上涨 +${sh.change_pct.toFixed(2)}%，整体赚钱效应好`); score += 1 }
  else if (sh && sh.change_pct < -1) { points.push(`大盘下跌 ${sh.change_pct.toFixed(2)}%，风险偏好下降`); score -= 1 }
  else { points.push(`大盘温和运行，情绪稳定`) }

  const signal = score >= 2 ? 'buy' : score <= -2 ? 'sell' : 'hold'
  const confidence = Math.min(82, 52 + Math.abs(score) * 9)
  return { agent: 'SentimentAnalyst', icon: MessageCircle, color: 'text-yellow-400', bgColor: 'bg-yellow-900/10', signal, confidence, points }
}

function runRiskManager(q: StockQuote, h: { cost: number }, allQuotes: StockQuote[]): AgentAnalysis {
  const points: string[] = []
  let score = 0
  const pnlPct = ((q.current - h.cost) / h.cost) * 100
  const amplitude = q.high > 0 ? ((q.high - q.low) / q.last_close) * 100 : 0

  // 止盈线检测
  if (pnlPct > 25) { points.push(`⚠️ 累计盈利 +${pnlPct.toFixed(1)}%，接近止盈阈值，建议分批减仓`); score -= 2 }
  else if (pnlPct > 15) { points.push(`盈利 +${pnlPct.toFixed(1)}%，可设置移动止盈保护利润`); score -= 1 }
  else { points.push(`持仓盈亏 ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%，风控线未触发`) }

  // 止损线检测
  if (pnlPct < -8) { points.push(`🔴 亏损 ${pnlPct.toFixed(1)}% 超过止损线 -8%，建议止损出局`); score -= 3 }
  else if (pnlPct < -5) { points.push(`⚠️ 亏损 ${pnlPct.toFixed(1)}%，接近止损线，设置保护`); score -= 1 }

  // 波动率风险
  if (amplitude > 6) { points.push(`今日振幅 ${amplitude.toFixed(1)}%，波动剧烈，仓位不宜过重`); score -= 1 }
  else if (amplitude < 2) { points.push(`振幅仅 ${amplitude.toFixed(1)}%，风险可控，适合持有`) }
  else { points.push(`振幅 ${amplitude.toFixed(1)}%，正常波动，风险在合理范围`) }

  // 仓位建议
  const positionRisk = pnlPct < 0 ? '关注止损' : pnlPct > 20 ? '考虑止盈' : '维持仓位'
  points.push(`风控建议：${positionRisk}，单股仓位不超过总资金 20%`)

  const signal = score <= -3 ? 'sell' : score <= -1 ? 'hold' : 'hold'
  const confidence = Math.min(85, 60 + Math.abs(score) * 6)
  return { agent: 'RiskManager', icon: ShieldAlert, color: 'text-emerald-400', bgColor: 'bg-emerald-900/10', signal, confidence, points }
}

function buildStockAnalysis(q: StockQuote, h: { cost: number; name: string }, marketData: any, allQuotes: StockQuote[]): StockAnalysis {
  const pnlPct = ((q.current - h.cost) / h.cost) * 100
  const agents = [
    runMarketAnalyst(q, marketData),
    runTechAnalyst(q),
    runFundAnalyst(q, h),
    runSentimentAnalyst(q, marketData),
    runRiskManager(q, h, allQuotes),
  ]
  const buyVotes  = agents.filter(a => a.signal === 'buy').length
  const sellVotes = agents.filter(a => a.signal === 'sell').length
  const overallSignal: 'buy' | 'sell' | 'hold' = sellVotes >= 3 ? 'sell' : buyVotes >= 3 ? 'buy' : 'hold'
  const overallConfidence = Math.round(agents.reduce((s, a) => s + a.confidence, 0) / agents.length)
  return { code: q.code, name: h.name, price: q.current, change: q.percent, pnlPct, overallSignal, overallConfidence, agents }
}

interface AgentDecisionsProps {
  selectedCode?: string | null
  onSelectStock?: (code: string, name: string) => void
}

// ─── 主组件 ───────────────────────────────────────────────────
export default function AgentDecisions({ selectedCode, onSelectStock }: AgentDecisionsProps) {
  const [analyses, setAnalyses] = useState<StockAnalysis[]>([])
  const [buyCandidate, setBuyCandidate] = useState<BuyCandidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // 同步外部 selectedCode → 展开对应卡片
  useEffect(() => {
    if (selectedCode !== undefined) setExpandedStock(selectedCode)
  }, [selectedCode])

  // 分析完成后默认展开第一只（如果父级没指定）
  const handleExpand = (code: string, name: string) => {
    const next = expandedStock === code ? null : code
    setExpandedStock(next)
    if (onSelectStock) onSelectStock(next ? code : (analyses[0]?.code ?? code), next ? name : (analyses[0]?.name ?? name))
  }

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const codes = HOLDINGS.map(h => h.code).join(',')
        const [quoteRes, marketRes] = await Promise.all([
          fetch(`/api/quote?codes=${codes}`),
          fetch('/api/market'),
        ])
        const quoteData = await quoteRes.json()
        const marketData = await marketRes.json()

        if (quoteData.success && quoteData.data) {
          const allQuotes: StockQuote[] = quoteData.data
          const results = HOLDINGS.map(h => {
            const q = allQuotes.find((d: any) => d.code === h.code)
            if (!q) return null
            return buildStockAnalysis(q, h, marketData.success ? marketData : {}, allQuotes)
          }).filter(Boolean) as StockAnalysis[]
          setAnalyses(results)
          // 默认选中第一只（如果父级还未指定）
          if (results.length > 0 && !selectedCode && onSelectStock) {
            onSelectStock(results[0].code, results[0].name)
          }
        }

        // 买入候选
        if (marketData.success && marketData.sectors?.[0]) {
          const topSector = marketData.sectors[0]
          const sectorRes = await fetch(`/api/sector-stocks?code=${topSector.code}&limit=15`)
          const sectorData = await sectorRes.json()
          if (sectorData.success) {
            const holdingCodes = new Set(HOLDINGS.map(h => h.code))
            const available = sectorData.stocks.filter((s: any) => !holdingCodes.has(s.code))
            const candidates = available
              .filter((s: any) => s.changePct > 1 && s.changePct < 9 && s.mainNetInflow > 0)
              .sort((a: any, b: any) => b.mainNetInflow - a.mainNetInflow)
            const pick = candidates[0] || available[0]
            if (pick) {
              setBuyCandidate({
                code: pick.code, name: pick.name, price: pick.price, change: pick.changePct,
                sectorName: topSector.name,
                reasons: [
                  `所属板块「${topSector.name}」为今日资金净流入第一`,
                  `今日涨幅 ${pick.changePct.toFixed(2)}%，走势活跃`,
                  `主力资金净流入 ${(pick.mainNetInflow / 1e8).toFixed(2)}亿`,
                  pick.changePct < 5 ? '涨幅适中，追高风险较小' : '涨幅较大，注意追高风险',
                ],
                score: Math.min(85, 60 + pick.mainNetInflow / 1e8 * 2),
              })
            }
          }
        }
      } catch (e) { console.error(e) }
      finally { setLoading(false) }
    }
    fetchAll()
    const timer = setInterval(fetchAll, 30000)
    return () => clearInterval(timer)
  }, [])

  const buyCount  = analyses.filter(a => a.overallSignal === 'buy').length
  const sellCount = analyses.filter(a => a.overallSignal === 'sell').length
  const holdCount = analyses.filter(a => a.overallSignal === 'hold').length
  const avgConf   = analyses.length > 0 ? Math.round(analyses.reduce((s, a) => s + a.overallConfidence, 0) / analyses.length) : 0
  const overallSignal = sellCount >= 3 ? 'sell' : buyCount >= 3 ? 'buy' : 'hold'
  const overallCfg = signalConfig[overallSignal]

  if (loading) {
    return (
      <div className="cyber-card p-5">
        <div className="flex items-center justify-center h-40 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />AI分析中...
        </div>
      </div>
    )
  }

  return (
    <div className="cyber-card p-5">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Brain className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">AI Agent 决策面板</h2>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <Zap className="w-3 h-3 text-yellow-400" />
          <span className="text-gray-400">实时分析</span>
        </div>
      </div>

      {/* 综合决策概览 */}
      <div className={`mb-4 p-4 rounded-lg border-2 ${overallCfg.border} ${overallCfg.bg} relative overflow-hidden`}>
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-cyan-500/10 to-transparent rounded-bl-full" />
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <Brain className="w-6 h-6 text-cyan-400" />
            <span className="font-bold text-lg">综合决策</span>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-bold ${overallCfg.text} ${overallCfg.bg} border ${overallCfg.border}`}>
            {overallCfg.emoji} {overallCfg.label}
          </div>
        </div>
        <div className="flex items-center space-x-4 mb-2 text-sm">
          <span className="text-red-400">买入:{buyCount}</span>
          <span className="text-yellow-400">持有:{holdCount}</span>
          <span className="text-green-400">卖出:{sellCount}</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-500">综合置信度</span>
          <div className="flex-1 h-2 rounded-full bg-gray-800 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all duration-1000"
              style={{ width: `${avgConf}%` }} />
          </div>
          <span className="text-sm font-mono font-bold text-cyan-400">{avgConf}%</span>
        </div>
      </div>

      {/* 逐股分析卡片 */}
      <div className="mb-3 text-xs text-gray-500 font-medium">📊 持仓逐股分析（点击展开各分析师详情）</div>
      <div className="space-y-2 mb-4">
        {analyses.map((a) => {
          const cfg = signalConfig[a.overallSignal]
          const expanded = expandedStock === a.code
          return (
            <div key={a.code}
              className={`rounded-lg border transition-all duration-300 ${expanded ? 'border-cyan-700/50' : 'border-gray-800/50'}`}>
              {/* 卡片头部 - 点击展开/收起 */}
              <div
                onClick={() => handleExpand(a.code, a.name)}
                className={`flex items-center justify-between p-3 cursor-pointer rounded-lg hover:bg-gray-800/30 transition-colors ${expanded ? 'rounded-b-none' : ''}`}
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  {/* 信号标识 */}
                  <div className={`w-1 h-10 rounded-full flex-shrink-0 ${a.overallSignal === 'buy' ? 'bg-red-500' : a.overallSignal === 'sell' ? 'bg-green-500' : 'bg-yellow-500'}`} />
                  {/* 名称代码 */}
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-sm">{a.name}</span>
                      <span className="text-xs text-gray-500 font-mono">{a.code}</span>
                    </div>
                    <div className="flex items-center space-x-3 mt-0.5">
                      <span className="font-mono text-sm font-bold">{a.price.toFixed(2)}</span>
                      <span className={`font-mono text-xs font-bold ${a.change >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                        {a.change >= 0 ? '+' : ''}{a.change.toFixed(2)}%
                      </span>
                      <span className={`font-mono text-xs ${a.pnlPct >= 0 ? 'text-red-300' : 'text-green-300'}`}>
                        持仓 {a.pnlPct >= 0 ? '+' : ''}{a.pnlPct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-3 flex-shrink-0 ml-2">
                  {/* 各分析师投票缩略图 */}
                  <div className="hidden sm:flex items-center space-x-1">
                    {a.agents.map(ag => {
                      const agCfg = signalConfig[ag.signal]
                      return (
                        <span key={ag.agent} title={`${ag.agent}: ${agCfg.label}`}
                          className={`text-xs px-1.5 py-0.5 rounded ${agCfg.text} ${agCfg.bg} font-mono`}>
                          {agCfg.emoji}
                        </span>
                      )
                    })}
                  </div>
                  {/* 综合信号 */}
                  <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${cfg.text} ${cfg.bg} border ${cfg.border}`}>
                    {cfg.label}
                  </span>
                  {/* 置信度 */}
                  <span className="text-xs font-mono text-gray-500">{a.overallConfidence}%</span>
                  {/* 展开箭头 */}
                  {expanded
                    ? <ChevronUp className="w-4 h-4 text-gray-500" />
                    : <ChevronDown className="w-4 h-4 text-gray-500" />
                  }
                </div>
              </div>

              {/* 展开详情 - 5位分析师 */}
              {expanded && (
                <div className="border-t border-gray-800 divide-y divide-gray-800/50">
                  {a.agents.map((ag) => {
                    const agCfg = signalConfig[ag.signal]
                    const Icon = ag.icon
                    return (
                      <div key={ag.agent} className={`p-3 ${ag.bgColor}`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <Icon className={`w-3.5 h-3.5 ${ag.color}`} />
                            <span className={`text-xs font-semibold ${ag.color}`}>{ag.agent}</span>
                          </div>
                          <div className="flex items-center space-x-2">
                            {/* 置信度细条 */}
                            <div className="w-20 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-700 ${ag.signal === 'buy' ? 'bg-red-500' : ag.signal === 'sell' ? 'bg-green-500' : 'bg-yellow-500'}`}
                                style={{ width: `${ag.confidence}%` }}
                              />
                            </div>
                            <span className={`text-xs font-mono ${agCfg.text} font-bold`}>
                              {agCfg.emoji} {agCfg.label} {ag.confidence}%
                            </span>
                          </div>
                        </div>
                        <div className="space-y-1">
                          {ag.points.map((pt, i) => (
                            <div key={i} className="flex items-start space-x-1.5">
                              <span className={`mt-0.5 text-xs ${ag.color} opacity-60`}>•</span>
                              <span className="text-xs text-gray-400 leading-relaxed">{pt}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 买入候选推荐 */}
      {buyCandidate && (
        <>
          <div className="mb-3 text-xs text-gray-500 font-medium flex items-center space-x-1">
            <Star className="w-3 h-3 text-yellow-400" />
            <span>🔥 热门板块买入候选</span>
          </div>
          <div className="p-4 rounded-lg border-2 border-red-500/20 bg-red-900/10 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-yellow-500/10 to-transparent rounded-bl-full" />
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="font-bold text-base">{buyCandidate.name}</span>
                <span className="text-xs text-gray-500 font-mono ml-2">{buyCandidate.code}</span>
                <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-red-900/30 text-red-400 border border-red-500/30">
                  {buyCandidate.sectorName}
                </span>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold">{buyCandidate.price.toFixed(2)}</div>
                <div className={`text-xs font-mono ${buyCandidate.change >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {buyCandidate.change >= 0 ? '+' : ''}{buyCandidate.change.toFixed(2)}%
                </div>
              </div>
            </div>
            <div className="space-y-1 mb-2">
              {buyCandidate.reasons.map((r, i) => (
                <div key={i} className="text-xs text-gray-400 flex items-start space-x-1">
                  <span className="text-yellow-500 mt-0.5">▸</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-xs text-gray-500">推荐评分</span>
              <div className="flex-1 h-2 rounded-full bg-gray-800 overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-yellow-600 to-yellow-400 transition-all duration-1000"
                  style={{ width: `${buyCandidate.score}%` }} />
              </div>
              <span className="text-sm font-mono font-bold text-yellow-400">{Math.round(buyCandidate.score)}%</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
