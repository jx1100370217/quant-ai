'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Brain, Zap, Loader2, ChevronDown, ChevronUp, Star,
  Landmark, Lightbulb, Shield, AlertTriangle, CircleDollarSign,
  Sprout, Rocket, Search, TrendingUp, Hash, Globe, BookOpen,
  BarChart2, MessageCircle, ShieldAlert, RefreshCw,
} from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────
interface LLMSignal {
  signal: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  reasoning: string
}

interface HoldingAnalysis {
  code: string
  name: string
  price: number
  change: number
  pnlPct: number
  overallSignal: 'bullish' | 'bearish' | 'neutral'
  overallConfidence: number
  agentSignals: Record<string, LLMSignal>
}

interface StockQuote {
  code: string; current: number; percent: number; chg: number
  high: number; low: number; open: number; last_close: number
  pe_ttm?: number | null; pb?: number | null
}

// ── 精选股结果 ──────────────────────────────────────────────
interface PickResult {
  code: string; name: string; price: number; change_pct: number
  pe_ttm?: number | null; pb?: number | null; market_cap_b?: number | null
  sector_name: string; net_inflow: number
  bullish: number; bearish: number; neutral: number
  avg_confidence: number; score: number
  agent_signals: Record<string, LLMSignal>
}
interface MarketPicksResult {
  sector_pick: PickResult
  master_pick: PickResult
  candidates_count: number
  top_sectors: string[]
}

// ─── Agent 配置 ───────────────────────────────────────────────
const AGENT_CONFIG: Record<string, { label: string; shortLabel: string; color: string; bgColor: string; icon: any; group: string }> = {
  // 价值派
  WarrenBuffett:        { label: '巴菲特',     shortLabel: 'Buffett',       color: 'text-amber-400',   bgColor: 'bg-amber-900/10',   icon: Landmark,          group: '价值派' },
  CharlieMunger:        { label: '芒格',       shortLabel: 'Munger',        color: 'text-orange-400',  bgColor: 'bg-orange-900/10',  icon: Lightbulb,         group: '价值派' },
  BenGraham:            { label: '格雷厄姆',   shortLabel: 'Graham',        color: 'text-blue-400',    bgColor: 'bg-blue-900/10',    icon: Shield,            group: '价值派' },
  MichaelBurry:         { label: '伯里',       shortLabel: 'Burry',         color: 'text-red-400',     bgColor: 'bg-red-900/10',     icon: AlertTriangle,     group: '价值派' },
  MohnishPabrai:        { label: '帕布莱',     shortLabel: 'Pabrai',        color: 'text-yellow-400',  bgColor: 'bg-yellow-900/10',  icon: CircleDollarSign,  group: '价值派' },
  // 成长派
  PeterLynch:           { label: '彼得林奇',   shortLabel: 'Lynch',         color: 'text-lime-400',    bgColor: 'bg-lime-900/10',    icon: Sprout,            group: '成长派' },
  CathieWood:           { label: '凯西伍德',   shortLabel: 'CathieWood',    color: 'text-pink-400',    bgColor: 'bg-pink-900/10',    icon: Rocket,            group: '成长派' },
  PhilFisher:           { label: '费舍尔',     shortLabel: 'Fisher',        color: 'text-cyan-400',    bgColor: 'bg-cyan-900/10',    icon: Search,            group: '成长派' },
  RakeshJhunjhunwala:   { label: '拉克希',     shortLabel: 'Rakesh',        color: 'text-violet-400',  bgColor: 'bg-violet-900/10',  icon: TrendingUp,        group: '成长派' },
  // 宏观/激进派
  AswathDamodaran:      { label: '达摩达兰',   shortLabel: 'Damodaran',     color: 'text-teal-400',    bgColor: 'bg-teal-900/10',    icon: Hash,              group: '宏观/激进' },
  StanleyDruckenmiller: { label: '德鲁肯米勒', shortLabel: 'Druckenmiller', color: 'text-indigo-400',  bgColor: 'bg-indigo-900/10',  icon: Globe,             group: '宏观/激进' },
  BillAckman:           { label: '阿克曼',     shortLabel: 'Ackman',        color: 'text-rose-400',    bgColor: 'bg-rose-900/10',    icon: Zap,               group: '宏观/激进' },
  // 量化支撑
  FundamentalAnalyst:   { label: '基本面',     shortLabel: 'Fundamentals',  color: 'text-purple-400',  bgColor: 'bg-purple-900/10',  icon: BookOpen,          group: '量化支撑' },
  TechnicalAnalyst:     { label: '技术面',     shortLabel: 'Technicals',    color: 'text-sky-400',     bgColor: 'bg-sky-900/10',     icon: BarChart2,         group: '量化支撑' },
  SentimentAnalyst:     { label: '市场情绪',   shortLabel: 'Sentiment',     color: 'text-emerald-400', bgColor: 'bg-emerald-900/10', icon: MessageCircle,     group: '量化支撑' },
  RiskManager:          { label: '风控',       shortLabel: 'RiskMgr',       color: 'text-gray-400',    bgColor: 'bg-gray-900/20',    icon: ShieldAlert,       group: '量化支撑' },
}

const GROUP_ORDER = ['价值派', '成长派', '宏观/激进', '量化支撑']

const SIGNAL_CFG = {
  bullish: { label: '看多', emoji: '▲', text: 'text-red-400',    bg: 'bg-red-900/20',    border: 'border-red-500/40' },
  bearish: { label: '看空', emoji: '▼', text: 'text-green-400',  bg: 'bg-green-900/20',  border: 'border-green-500/40' },
  neutral: { label: '中性', emoji: '─', text: 'text-yellow-400', bg: 'bg-yellow-900/20', border: 'border-yellow-500/40' },
}

// ─── Helper ───────────────────────────────────────────────────
function calcOverall(agentSignals: Record<string, LLMSignal>): { signal: 'bullish' | 'bearish' | 'neutral'; confidence: number; bullish: number; bearish: number; neutral: number } {
  const vals = Object.values(agentSignals)
  if (vals.length === 0) return { signal: 'neutral', confidence: 0, bullish: 0, bearish: 0, neutral: 0 }
  const bullish = vals.filter(v => v.signal === 'bullish').length
  const bearish = vals.filter(v => v.signal === 'bearish').length
  const neutral = vals.length - bullish - bearish
  const majority = Math.ceil(vals.length / 2)
  const signal: 'bullish' | 'bearish' | 'neutral' = bullish >= majority ? 'bullish' : bearish >= majority ? 'bearish' : 'neutral'
  const confidence = Math.round(vals.reduce((s, v) => s + v.confidence, 0) / vals.length)
  return { signal, confidence, bullish, bearish, neutral }
}

// ─── Props ────────────────────────────────────────────────────
interface AgentDecisionsProps {
  holdings?: Array<{ code: string; name: string; cost: number; shares?: number }>
  selectedCode?: string | null
  onSelectStock?: (code: string, name: string) => void
}

// ─── 主组件 ───────────────────────────────────────────────────
export default function AgentDecisions({ holdings = [], selectedCode, onSelectStock }: AgentDecisionsProps) {
  const [analyses, setAnalyses] = useState<HoldingAnalysis[]>([])
  const [marketPicks, setMarketPicks] = useState<MarketPicksResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [picksLoading, setPicksLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [picksError, setPicksError] = useState<string | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)
  const [expandedPick, setExpandedPick] = useState<'sector' | 'master' | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [agentGroups, setAgentGroups] = useState<string[]>([])
  const [analysisTriggered, setAnalysisTriggered] = useState(false)

  // 同步外部 selectedCode
  useEffect(() => {
    if (selectedCode !== undefined) setExpandedStock(selectedCode)
  }, [selectedCode])

  const handleExpand = (code: string, name: string) => {
    const next = expandedStock === code ? null : code
    setExpandedStock(next)
    // Trigger analysis if not yet triggered
    if (next && !analysisTriggered && analyses.length === 0) {
      setAnalysisTriggered(true)
      fetchAnalysis()
      fetchMarketPicks()
    }
    if (onSelectStock) onSelectStock(
      next ? code : (analyses[0]?.code ?? code),
      next ? name : (analyses[0]?.name ?? name)
    )
  }

  const fetchAnalysis = useCallback(async () => {
    if (holdings.length === 0) return
    setLoading(true)
    setError(null)
    try {
      const codes = holdings.map(h => h.code).join(',')

      // 并发：行情 + 大师分析 + 市场数据
      const [quoteRes, agentRes, marketRes] = await Promise.all([
        fetch(`/api/quote?codes=${codes}`),
        fetch('/api/agents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ holdings }),
        }),
        fetch('/api/market'),
      ])

      const quoteData = await quoteRes.json()
      const agentData = await agentRes.json()
      const marketData = await marketRes.json()

      if (!agentData.success) {
        setError(agentData.error || '后端返回错误')
        return
      }

      const allQuotes: StockQuote[] = quoteData.success ? quoteData.data : []
      const agentSignalsMap: Record<string, Record<string, LLMSignal>> = agentData.data || {}

      // 整理每只股票的分析结果
      const results: HoldingAnalysis[] = holdings.map(h => {
        const q = allQuotes.find(d => d.code === h.code)
        const price = q?.current ?? 0
        const change = q?.percent ?? 0
        const pnlPct = h.cost > 0 ? ((price - h.cost) / h.cost) * 100 : 0

        // 收集该股票在各 agent 的信号
        const agentSignals: Record<string, LLMSignal> = {}
        for (const [agentName, signals] of Object.entries(agentSignalsMap)) {
          if (signals[h.code]) {
            agentSignals[agentName] = signals[h.code] as LLMSignal
          }
        }

        const overall = calcOverall(agentSignals)
        return {
          code: h.code,
          name: h.name,
          price,
          change,
          pnlPct,
          overallSignal: overall.signal,
          overallConfidence: overall.confidence,
          agentSignals,
        }
      })

      setAnalyses(results)
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'))

      // 识别有信号的 agent 分组
      const presentAgents = new Set(Object.keys(agentSignalsMap))
      setAgentGroups(GROUP_ORDER.filter(g =>
        Object.entries(AGENT_CONFIG).some(([name, cfg]) => cfg.group === g && presentAgents.has(name))
      ))

      // 默认展开第一只
      if (results.length > 0 && !selectedCode && onSelectStock) {
        onSelectStock(results[0].code, results[0].name)
      }

    } catch (e: any) {
      setError(e.message || '网络异常')
    } finally {
      setLoading(false)
    }
  }, [holdings, onSelectStock, selectedCode])

  // ─── 市场精选（独立异步，不阻塞持仓分析）──────────────────
  const fetchMarketPicks = useCallback(async () => {
    if (holdings.length === 0) return
    setPicksLoading(true)
    setPicksError(null)
    try {
      const res = await fetch('/api/market-picks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings }),
      })
      const data = await res.json()
      if (!data.success) {
        setPicksError(data.error || '精选选股失败')
      } else {
        setMarketPicks(data as MarketPicksResult)
      }
    } catch (e: any) {
      setPicksError(e.message || '网络异常')
    } finally {
      setPicksLoading(false)
    }
  }, [holdings])


  // ─── 综合统计 ─────────────────────────────────────────────
  const bullishCount = analyses.filter(a => a.overallSignal === 'bullish').length
  const bearishCount = analyses.filter(a => a.overallSignal === 'bearish').length
  const neutralCount = analyses.filter(a => a.overallSignal === 'neutral').length
  const avgConf = analyses.length > 0
    ? Math.round(analyses.reduce((s, a) => s + a.overallConfidence, 0) / analyses.length) : 0
  const majority = analyses.length > 0 ? Math.ceil(analyses.length / 2) : 2
  const portfolioSignal: 'bullish' | 'bearish' | 'neutral' =
    bullishCount >= majority ? 'bullish' : bearishCount >= majority ? 'bearish' : 'neutral'
  const portfolioCfg = SIGNAL_CFG[portfolioSignal]

  // ─── 空状态 ───────────────────────────────────────────────
  if (holdings.length === 0) {
    return (
      <div className="cyber-card p-5">
        <div className="flex items-center space-x-2 mb-4">
          <Brain className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">AI 投资大师决策面板</h2>
        </div>
        <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
          正在加载真实持仓数据...
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
          <h2 className="text-lg font-semibold">AI 投资大师决策面板</h2>
          <span className="text-xs text-gray-500 ml-1">
            ({Object.keys(AGENT_CONFIG).length} 位大师)
          </span>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          {lastUpdated && <span className="text-gray-500">{lastUpdated}</span>}
          <button
            onClick={fetchAnalysis}
            disabled={loading}
            className="flex items-center space-x-1 text-gray-400 hover:text-cyan-400 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-500/40 bg-red-900/10 text-sm text-red-400">
          ⚠️ {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && analyses.length === 0 && (
        <div className="mb-4 p-4 rounded-lg border border-cyan-700/30 bg-cyan-900/5">
          <div className="flex items-center space-x-2 mb-3">
            <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
            <span className="text-sm text-cyan-400">正在召唤 {Object.keys(AGENT_CONFIG).length} 位投资大师分析中...</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(AGENT_CONFIG).map(([name, cfg]) => {
              const Icon = cfg.icon
              return (
                <div key={name} className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs ${cfg.bgColor} ${cfg.color} opacity-60 animate-pulse`}>
                  <Icon className="w-3 h-3" />
                  <span>{cfg.shortLabel}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 综合决策概览 */}
      {analyses.length > 0 && (
        <div className={`mb-4 p-4 rounded-lg border-2 ${portfolioCfg.border} ${portfolioCfg.bg} relative overflow-hidden`}>
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-cyan-500/10 to-transparent rounded-bl-full" />
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <Brain className="w-5 h-5 text-cyan-400" />
              <span className="font-bold">综合决策</span>
            </div>
            <div className={`px-3 py-1 rounded-full text-sm font-bold ${portfolioCfg.text} ${portfolioCfg.bg} border ${portfolioCfg.border}`}>
              {portfolioCfg.emoji} {portfolioCfg.label}
            </div>
          </div>
          <div className="flex items-center space-x-4 mb-2 text-sm">
            <span className="text-red-400">看多:{bullishCount}</span>
            <span className="text-yellow-400">中性:{neutralCount}</span>
            <span className="text-green-400">看空:{bearishCount}</span>
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
      )}

      {/* 未触发分析提示 */}
      {analyses.length === 0 && !analysisTriggered && !loading && (
        <div className="rounded-lg border border-gray-800/50 bg-gray-900/20 p-4 mb-4">
          <p className="text-sm text-gray-400">点击上方按钮启动16位大师分析</p>
        </div>
      )}

      {/* 逐股分析卡片 */}
      {analyses.length > 0 && (
        <>
          <div className="mb-3 text-xs text-gray-500 font-medium">
            📊 持仓逐股分析（点击展开 {Object.keys(AGENT_CONFIG).length} 位大师详情）
          </div>
          <div className="space-y-2 mb-4">
            {analyses.map(a => {
              const cfg = SIGNAL_CFG[a.overallSignal]
              const expanded = expandedStock === a.code
              const overall = calcOverall(a.agentSignals)

              return (
                <div key={a.code}
                  className={`rounded-lg border transition-all duration-300 ${expanded ? 'border-cyan-700/50' : 'border-gray-800/50'}`}>
                  {/* 卡片头部 */}
                  <div
                    onClick={() => handleExpand(a.code, a.name)}
                    className={`flex items-center justify-between p-3 cursor-pointer rounded-lg hover:bg-gray-800/30 transition-colors ${expanded ? 'rounded-b-none' : ''}`}
                  >
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      <div className={`w-1 h-10 rounded-full flex-shrink-0 ${a.overallSignal === 'bullish' ? 'bg-red-500' : a.overallSignal === 'bearish' ? 'bg-green-500' : 'bg-yellow-500'}`} />
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
                    <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
                      {/* 大师分组投票缩略 */}
                      <div className="hidden md:flex items-center space-x-0.5">
                        {Object.entries(a.agentSignals).slice(0, 8).map(([name, sig]) => {
                          const ac = AGENT_CONFIG[name]
                          if (!ac) return null
                          const sc = SIGNAL_CFG[sig.signal]
                          return (
                            <span key={name} title={`${ac.label}: ${sc.label} ${sig.confidence}%`}
                              className={`text-xs px-1 py-0.5 rounded ${sc.text} ${sc.bg}`}>
                              {sc.emoji}
                            </span>
                          )
                        })}
                        {Object.keys(a.agentSignals).length > 8 && (
                          <span className="text-xs text-gray-500 ml-0.5">+{Object.keys(a.agentSignals).length - 8}</span>
                        )}
                      </div>
                      {/* 票数统计 */}
                      <div className="text-xs text-gray-500 font-mono">
                        <span className="text-red-400">{overall.bullish}▲</span>
                        <span className="mx-0.5 text-gray-600">·</span>
                        <span className="text-green-400">{overall.bearish}▼</span>
                      </div>
                      <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${cfg.text} ${cfg.bg} border ${cfg.border}`}>
                        {cfg.label}
                      </span>
                      <span className="text-xs font-mono text-gray-500">{a.overallConfidence}%</span>
                      {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
                    </div>
                  </div>

                  {/* 展开详情：按分组显示所有大师 */}
                  {expanded && (
                    <div className="border-t border-gray-800">
                      {GROUP_ORDER.map(group => {
                        const groupAgents = Object.entries(AGENT_CONFIG)
                          .filter(([name, cfg]) => cfg.group === group && a.agentSignals[name])
                        if (groupAgents.length === 0) return null
                        return (
                          <div key={group}>
                            <div className="px-3 py-1.5 bg-gray-900/50 border-b border-gray-800/50">
                              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{group}</span>
                            </div>
                            <div className="divide-y divide-gray-800/30">
                              {groupAgents.map(([agentName, agentCfg]) => {
                                const sig = a.agentSignals[agentName]
                                if (!sig) return null
                                const sc = SIGNAL_CFG[sig.signal]
                                const Icon = agentCfg.icon
                                return (
                                  <div key={agentName} className={`p-3 ${agentCfg.bgColor}`}>
                                    <div className="flex items-center justify-between mb-1.5">
                                      <div className="flex items-center space-x-2">
                                        <Icon className={`w-3.5 h-3.5 ${agentCfg.color}`} />
                                        <span className={`text-xs font-semibold ${agentCfg.color}`}>
                                          {agentCfg.label}
                                        </span>
                                        <span className="text-xs text-gray-600">{agentCfg.shortLabel}</span>
                                      </div>
                                      <div className="flex items-center space-x-2">
                                        <div className="w-16 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                                          <div
                                            className={`h-full rounded-full transition-all duration-700 ${sig.signal === 'bullish' ? 'bg-red-500' : sig.signal === 'bearish' ? 'bg-green-500' : 'bg-yellow-500'}`}
                                            style={{ width: `${sig.confidence}%` }}
                                          />
                                        </div>
                                        <span className={`text-xs font-mono font-bold ${sc.text}`}>
                                          {sc.emoji} {sc.label} {sig.confidence}%
                                        </span>
                                      </div>
                                    </div>
                                    <p className="text-xs text-gray-400 leading-relaxed pl-5">
                                      {sig.reasoning}
                                    </p>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )
                      })}
                      {/* 未匹配到 config 的 agent（兜底显示） */}
                      {Object.entries(a.agentSignals)
                        .filter(([name]) => !AGENT_CONFIG[name])
                        .map(([agentName, sig]) => {
                          const sc = SIGNAL_CFG[sig.signal]
                          return (
                            <div key={agentName} className="p-3 bg-gray-900/20 border-t border-gray-800/30">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-semibold text-gray-400">{agentName}</span>
                                <span className={`text-xs font-mono ${sc.text}`}>{sc.emoji} {sc.label} {sig.confidence}%</span>
                              </div>
                              <p className="text-xs text-gray-500 pl-3">{sig.reasoning}</p>
                            </div>
                          )
                        })
                      }
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* ──────────── 市场精选区 ──────────────────────────── */}
      <div className="mt-2 border-t border-gray-800/50 pt-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Star className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-semibold text-gray-300">AI 大师精选买入推荐</span>
            <span className="text-xs text-gray-600">（16位大师从A股全量筛选）</span>
          </div>
          <button onClick={fetchMarketPicks} disabled={picksLoading}
            className="flex items-center space-x-1 text-xs text-gray-500 hover:text-yellow-400 transition-colors disabled:opacity-40">
            <RefreshCw className={`w-3 h-3 ${picksLoading ? 'animate-spin' : ''}`} />
            <span>{picksLoading ? '选股中...' : '重新选股'}</span>
          </button>
        </div>

        {picksError && (
          <div className="p-3 rounded-lg border border-orange-500/30 bg-orange-900/10 text-xs text-orange-400 mb-3">
            ⚠️ {picksError}
          </div>
        )}

        {picksLoading && !marketPicks && (
          <div className="p-5 rounded-lg border border-yellow-700/30 bg-yellow-900/5">
            <div className="flex items-center space-x-2 mb-2">
              <Loader2 className="w-4 h-4 animate-spin text-yellow-400" />
              <span className="text-sm text-yellow-400">正在从A股候选池召唤16位大师分析选股...</span>
            </div>
            <p className="text-xs text-gray-600">分析多只候选股，约需 1-3 分钟，请耐心等待</p>
          </div>
        )}

        {marketPicks && (
          <div className="space-y-3">
            {/* 说明 */}
            {marketPicks.candidates_count > 0 && (
              <div className="text-xs text-gray-600">
                候选池：全A股净流入 Top30 + 热门板块 → 量化预筛 → {marketPicks.candidates_count} 只候选 → 16大师分析
              </div>
            )}

            {/* ── 热门板块精选 ── */}
            {renderPickCard(
              marketPicks.sector_pick,
              '🔥 热门板块精选',
              'sector',
              'border-orange-500/30 bg-orange-900/5',
              'text-orange-400'
            )}

            {/* ── 大师综合精选 ── */}
            {renderPickCard(
              marketPicks.master_pick,
              '🏆 大师综合精选',
              'master',
              'border-yellow-500/30 bg-yellow-900/5',
              'text-yellow-400'
            )}
          </div>
        )}
      </div>
    </div>
  )

  // ─── 精选卡片渲染函数 ─────────────────────────────────────
  function renderPickCard(
    pick: PickResult,
    title: string,
    pickKey: 'sector' | 'master',
    cardClass: string,
    accentColor: string
  ) {
    if (!pick) return null
    const expanded = expandedPick === pickKey
    const totalVotes = pick.bullish + pick.bearish + pick.neutral
    const scorePercent = Math.round(pick.score)

    return (
      <div className={`rounded-lg border-2 ${cardClass}`}>
        {/* 卡片头 */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <span className={`text-sm font-bold ${accentColor}`}>{title}</span>
              {pick.sector_name && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">
                  {pick.sector_name}
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2 text-xs text-gray-500">
              <span className="text-red-400 font-mono">{pick.bullish}▲</span>
              <span className="text-yellow-400 font-mono">{pick.neutral}─</span>
              <span className="text-green-400 font-mono">{pick.bearish}▼</span>
              <span className="text-gray-600">/ {totalVotes}位</span>
            </div>
          </div>

          {/* 股票基本信息 */}
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-base">{pick.name}</span>
                <span className="text-xs text-gray-500 font-mono">{pick.code}</span>
              </div>
              <div className="flex items-center space-x-3 mt-1 text-xs">
                {pick.pe_ttm != null && pick.pe_ttm > 0 && (
                  <span className="text-gray-400">PE <span className="text-gray-300 font-mono">{pick.pe_ttm.toFixed(1)}x</span></span>
                )}
                {pick.pb != null && pick.pb > 0 && (
                  <span className="text-gray-400">PB <span className="text-gray-300 font-mono">{pick.pb.toFixed(2)}x</span></span>
                )}
                {pick.market_cap_b != null && (
                  <span className="text-gray-400">市值 <span className="text-gray-300 font-mono">{pick.market_cap_b.toFixed(1)}亿</span></span>
                )}
                {pick.net_inflow > 0 && (
                  <span className="text-gray-400">主力净流入 <span className="text-red-300 font-mono">{(pick.net_inflow / 1e8).toFixed(2)}亿</span></span>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono font-bold text-base">{(pick.price ?? 0).toFixed(2)}</div>
              <div className={`text-xs font-mono font-bold ${(pick.change_pct ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                {(pick.change_pct ?? 0) >= 0 ? '+' : ''}{(pick.change_pct ?? 0).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* 综合评分 */}
          <div className="flex items-center space-x-2 mb-3">
            <span className="text-xs text-gray-500">综合评分</span>
            <div className="flex-1 h-2 rounded-full bg-gray-800 overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-1000 bg-gradient-to-r ${pickKey === 'master' ? 'from-yellow-600 to-yellow-400' : 'from-orange-600 to-orange-400'}`}
                style={{ width: `${Math.min(scorePercent * 1.5, 100)}%` }} />
            </div>
            <span className={`text-sm font-mono font-bold ${accentColor}`}>{pick.avg_confidence}% 置信</span>
          </div>

          {/* 展开/收起按钮 */}
          <button
            onClick={() => setExpandedPick(expanded ? null : pickKey)}
            className="w-full flex items-center justify-center space-x-1 py-1.5 rounded-lg text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800/30 transition-colors border border-gray-800/50"
          >
            {expanded ? (
              <><ChevronUp className="w-3.5 h-3.5" /><span>收起 {totalVotes} 位大师分析</span></>
            ) : (
              <><ChevronDown className="w-3.5 h-3.5" /><span>展开 {totalVotes} 位大师详细分析</span></>
            )}
          </button>
        </div>

        {/* 展开的大师分析 */}
        {expanded && (
          <div className="border-t border-gray-800">
            {GROUP_ORDER.map(group => {
              const groupAgents = Object.entries(AGENT_CONFIG)
                .filter(([name, cfg]) => cfg.group === group && pick.agent_signals[name])
              if (groupAgents.length === 0) return null
              return (
                <div key={group}>
                  <div className="px-3 py-1.5 bg-gray-900/50 border-b border-gray-800/50">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{group}</span>
                  </div>
                  <div className="divide-y divide-gray-800/30">
                    {groupAgents.map(([agentName, agentCfg]) => {
                      const sig = pick.agent_signals[agentName]
                      if (!sig) return null
                      const sc = SIGNAL_CFG[sig.signal]
                      const Icon = agentCfg.icon
                      return (
                        <div key={agentName} className={`p-3 ${agentCfg.bgColor}`}>
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center space-x-2">
                              <Icon className={`w-3.5 h-3.5 ${agentCfg.color}`} />
                              <span className={`text-xs font-semibold ${agentCfg.color}`}>{agentCfg.label}</span>
                            </div>
                            <div className="flex items-center space-x-2">
                              <div className="w-16 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                                <div className={`h-full rounded-full ${sig.signal === 'bullish' ? 'bg-red-500' : sig.signal === 'bearish' ? 'bg-green-500' : 'bg-yellow-500'}`}
                                  style={{ width: `${sig.confidence}%` }} />
                              </div>
                              <span className={`text-xs font-mono font-bold ${sc.text}`}>
                                {sc.emoji} {sc.label} {sig.confidence}%
                              </span>
                            </div>
                          </div>
                          <p className="text-xs text-gray-400 leading-relaxed pl-5">{sig.reasoning}</p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }
}
