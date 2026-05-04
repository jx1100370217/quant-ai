'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  CalendarDays, RefreshCw, Loader2, ChevronDown, ChevronUp,
  TrendingUp, TrendingDown, Minus, AlertTriangle, BookOpen,
  Target, ShieldAlert, BarChart3, Sparkles, ScanSearch,
  Table as TableIcon,
} from 'lucide-react'

// ─── Types ─────────────────────────────────────────────────
interface StockRecommendation {
  code: string
  name: string
  current_price: number
  target_price: number
  stop_loss_price: number
  position_pct: number
  buy_reason: string
  risk_note: string
  master_consensus?: string
  bullish_count?: number
  bearish_count?: number
  neutral_count?: number
  confidence: number
  reversal_score?: number
  decline_5d?: number
  reversal_reason?: string
  // V12b 评分细节 (Top 5 表格展示)
  bounce_pct?: number | null
  decline_7d?: number | null
  vol_ratio?: number | null
  rsi6?: number | null
}

interface WeeklyReport {
  report_date: string
  target_week: string
  market_summary: string
  recommendations: StockRecommendation[]
  total_candidates_scanned: number
  reversal_filtered: number
  risk_warning: string
  strategy_notes: string
}

const GENERATING_STEPS = [
  '🔍 扫描全市场500+股票...',
  '📉 识别上周下跌3-8%候选...',
  '⚙️ 反转力度评分中...',
  '📊 综合排序与筛选...',
  '✍️ 生成反转策略周报...',
]

// ─── Helpers ───────────────────────────────────────────────
function confidenceColor(conf: number): string {
  if (conf > 60) return 'text-green-400'
  if (conf >= 40) return 'text-yellow-400'
  return 'text-red-400'
}

function confidenceBg(conf: number): string {
  if (conf > 60) return 'bg-green-900/20 border-green-500/30'
  if (conf >= 40) return 'bg-yellow-900/20 border-yellow-500/30'
  return 'bg-red-900/20 border-red-500/30'
}

function confidenceBarColor(conf: number): string {
  if (conf > 60) return 'from-green-600 to-green-400'
  if (conf >= 40) return 'from-yellow-600 to-yellow-400'
  return 'from-red-600 to-red-400'
}

// ─── Sub-components ────────────────────────────────────────

// V12b Top 5 推荐组合 — 清单式表格（权重/代码/名称/评分/收盘价/反弹%/7日%/量比/RSI6）
function Top5Table({ stocks }: { stocks: StockRecommendation[] }) {
  if (!stocks || stocks.length === 0) return null
  const fmt = (v: number | null | undefined, digits = 2, withSign = false) => {
    if (v === null || v === undefined || Number.isNaN(v)) return '—'
    const s = v.toFixed(digits)
    return withSign && v > 0 ? `+${s}` : s
  }
  const delta7dColor = (v: number | null | undefined) => {
    if (v === null || v === undefined) return 'text-gray-500'
    return v < 0 ? 'text-green-400' : v > 0 ? 'text-red-400' : 'text-gray-400'
  }

  return (
    <div className="rounded-lg border border-cyan-800/40 bg-gray-900/40 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-cyan-800/40 bg-cyan-900/10">
        <div className="flex items-center space-x-2">
          <TableIcon className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-semibold text-cyan-400">Top 5 推荐组合（按权重买入）</span>
        </div>
        <span className="text-xs text-gray-500 font-mono">V12b · 反弹≥3.5% ∧ 反转分≥40</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800/60">
              <th className="px-3 py-2 text-left font-normal">#</th>
              <th className="px-3 py-2 text-left font-normal">权重</th>
              <th className="px-3 py-2 text-left font-normal">代码</th>
              <th className="px-3 py-2 text-left font-normal">名称</th>
              <th className="px-3 py-2 text-right font-normal">评分</th>
              <th className="px-3 py-2 text-right font-normal">收盘价</th>
              <th className="px-3 py-2 text-right font-normal">反弹%</th>
              <th className="px-3 py-2 text-right font-normal">7日%</th>
              <th className="px-3 py-2 text-right font-normal">量比</th>
              <th className="px-3 py-2 text-right font-normal">RSI6</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((s, i) => (
              <tr
                key={s.code}
                className="border-b border-gray-800/40 hover:bg-cyan-900/10 transition-colors"
              >
                <td className="px-3 py-2.5 text-gray-600 font-mono">{i + 1}</td>
                <td className="px-3 py-2.5">
                  <span className="font-bold text-cyan-400">{s.position_pct.toFixed(0)}%</span>
                </td>
                <td className="px-3 py-2.5 font-mono text-gray-400">{s.code}</td>
                <td className="px-3 py-2.5 font-bold text-white">{s.name}</td>
                <td className="px-3 py-2.5 text-right font-mono font-bold text-yellow-400">
                  {s.reversal_score !== undefined ? s.reversal_score.toFixed(0) : '—'}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-gray-300">
                  {s.current_price.toFixed(2)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-green-400">
                  {fmt(s.bounce_pct, 2)}
                </td>
                <td className={`px-3 py-2.5 text-right font-mono ${delta7dColor(s.decline_7d)}`}>
                  {fmt(s.decline_7d, 2, true)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-gray-300">
                  {fmt(s.vol_ratio, 2)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-gray-300">
                  {fmt(s.rsi6, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2 bg-gray-900/60 border-t border-gray-800/60 text-[11px] text-gray-500 leading-relaxed">
        <span className="text-gray-400">提示：</span>
        权重 Top1→Top5 为 35/25/20/12/8%（按反转分加权）；单股 -6% 挂止损；组合周内加权回撤 ≤ -4% 次日清仓
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-gray-800/50 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-24 bg-gray-800 rounded" />
        <div className="h-4 w-16 bg-gray-800 rounded" />
      </div>
      <div className="h-3 w-full bg-gray-800 rounded mb-2" />
      <div className="h-3 w-3/4 bg-gray-800 rounded mb-4" />
      <div className="flex space-x-2">
        <div className="h-6 w-20 bg-gray-800 rounded" />
        <div className="h-6 w-20 bg-gray-800 rounded" />
      </div>
    </div>
  )
}

interface StockCardProps {
  stock: StockRecommendation
  index: number
}

function StockCard({ stock, index }: StockCardProps) {
  const [reasonOpen, setReasonOpen] = useState(false)
  const [riskOpen, setRiskOpen] = useState(false)

  const targetPct = stock.current_price > 0
    ? ((stock.target_price - stock.current_price) / stock.current_price * 100)
    : 0
  const stopPct = stock.current_price > 0
    ? ((stock.stop_loss_price - stock.current_price) / stock.current_price * 100)
    : 0

  return (
    <div className={`rounded-lg border-2 ${confidenceBg(stock.confidence)} transition-all duration-300`}>
      {/* 卡片头部 */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          {/* 左：股票信息 */}
          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-600 font-mono w-4">{index + 1}.</span>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-base text-white">{stock.name}</span>
                <span className="text-xs text-gray-500 font-mono">{stock.code}</span>
              </div>
              <div className="flex items-center space-x-1 mt-0.5 text-xs text-gray-500">
                <span>现价</span>
                <span className="font-mono text-gray-300 font-semibold">{stock.current_price.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* 右：置信度徽章 */}
          <div className={`flex flex-col items-center px-3 py-1.5 rounded-lg border ${confidenceBg(stock.confidence)}`}>
            <span className="text-xs text-gray-500">置信度</span>
            <span className={`font-mono font-bold text-base ${confidenceColor(stock.confidence)}`}>
              {stock.confidence}%
            </span>
          </div>
        </div>

        {/* 目标价 / 止损价 */}
        <div className="flex items-center space-x-2 mb-3 flex-wrap gap-y-1">
          <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-green-900/20 border border-green-500/30">
            <Target className="w-3 h-3 text-green-400" />
            <span className="text-xs text-gray-400">目标</span>
            <span className="text-xs font-mono font-bold text-green-400">{stock.target_price.toFixed(2)}</span>
            <span className="text-xs text-green-300/70">(+{targetPct.toFixed(1)}%)</span>
          </div>
          <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-red-900/20 border border-red-500/30">
            <ShieldAlert className="w-3 h-3 text-red-400" />
            <span className="text-xs text-gray-400">止损</span>
            <span className="text-xs font-mono font-bold text-red-400">{stock.stop_loss_price.toFixed(2)}</span>
            <span className="text-xs text-red-300/70">({stopPct.toFixed(1)}%)</span>
          </div>
        </div>

        {/* 仓位进度条 */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1 text-xs">
            <span className="text-gray-500">建议仓位</span>
            <span className="font-mono font-bold text-cyan-400">{stock.position_pct.toFixed(0)}%</span>
          </div>
          <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-700 to-cyan-400 transition-all duration-1000"
              style={{ width: `${Math.min(stock.position_pct, 100)}%` }}
            />
          </div>
        </div>

        {/* 置信度条 */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1 text-xs">
            <span className="text-gray-500">置信度</span>
            <span className={`font-mono font-bold ${confidenceColor(stock.confidence)}`}>{stock.confidence}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${confidenceBarColor(stock.confidence)} transition-all duration-1000`}
              style={{ width: `${stock.confidence}%` }}
            />
          </div>
        </div>

        {/* 反转评分 */}
        {stock.reversal_score !== undefined && (
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1.5 text-xs">
              <span className="text-gray-500 flex items-center space-x-1">
                <BarChart3 className="w-3 h-3" />
                <span>反转评分</span>
              </span>
              <span className="font-mono font-bold text-cyan-400">{stock.reversal_score}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-700 to-cyan-400 transition-all duration-1000"
                style={{ width: `${Math.min(stock.reversal_score, 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* 5日跌幅 */}
        {stock.decline_5d !== undefined && (
          <div className="mb-3">
            <div className="flex items-center space-x-1 text-xs">
              <TrendingDown className="w-3 h-3 text-orange-400" />
              <span className="text-gray-500">5日跌幅:</span>
              <span className="font-mono font-bold text-orange-400">{stock.decline_5d.toFixed(1)}%</span>
            </div>
          </div>
        )}

        {/* 买入理由/反转理由（展开/折叠） */}
        <div className="mb-2 rounded-lg border border-gray-800/60 overflow-hidden">
          <button
            onClick={() => setReasonOpen(v => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-cyan-400 hover:bg-gray-800/30 transition-colors"
          >
            <div className="flex items-center space-x-1.5">
              <BookOpen className="w-3.5 h-3.5" />
              <span className="font-medium">{stock.reversal_reason ? '反转理由' : '买入理由'}</span>
            </div>
            {reasonOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {reasonOpen && (
            <div className="px-3 pb-3 pt-1 bg-gray-900/30 text-xs text-gray-300 leading-relaxed">
              {stock.reversal_reason || stock.buy_reason}
            </div>
          )}
        </div>

        {/* 风险提示（展开/折叠） */}
        <div className="rounded-lg border border-orange-900/40 overflow-hidden">
          <button
            onClick={() => setRiskOpen(v => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-orange-400 hover:bg-orange-900/10 transition-colors"
          >
            <div className="flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
              <span className="font-medium text-orange-300/80">风险提示</span>
            </div>
            {riskOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {riskOpen && (
            <div className="px-3 pb-3 pt-1 bg-orange-900/10 text-xs text-orange-300/80 leading-relaxed">
              {stock.risk_note}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main Component ────────────────────────────────────────
export default function WeeklyAdvisor() {
  const [report, setReport] = useState<WeeklyReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const generatingRef = useRef(false)           // 稳定守卫，避免闭包陷阱
  const [error, setError] = useState<string | null>(null)
  const [generatingStep, setGeneratingStep] = useState(0)

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null
    if (generating) {
      setGeneratingStep(0)
      timer = setInterval(() => {
        setGeneratingStep(prev => (prev + 1) % GENERATING_STEPS.length)
      }, 15000)
    }
    return () => { if (timer) clearInterval(timer) }
  }, [generating])

  // 加载最新周报
  const fetchLatest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/weekly-advisor')
      const data = await res.json()
      if (data.success && data.data) {
        setReport(data.data)
      } else if (res.status === 404 || data.error === 'NOT_FOUND') {
        setReport(null) // 无周报，显示空态
      } else {
        setError(data.error || '获取周报失败')
      }
    } catch (e: any) {
      setError(e.message || '网络异常')
    } finally {
      setLoading(false)
    }
  }, [])

  // 生成新周报（使用 ref 守卫 + 最小显示时间，确保用户能看到加载状态）
  const generateReport = useCallback(async () => {
    if (generatingRef.current) return        // ref 始终读到最新值，不受闭包影响
    generatingRef.current = true
    setGenerating(true)
    setError(null)
    const startTime = Date.now()
    try {
      const res = await fetch('/api/weekly-advisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      })
      const data = await res.json()
      // 若后端缓存秒回，至少展示 800ms 加载态，让用户感知到"已刷新"
      const elapsed = Date.now() - startTime
      if (elapsed < 800) {
        await new Promise(r => setTimeout(r, 800 - elapsed))
      }
      if (data.success && data.data) {
        setReport(data.data)
      } else {
        setError(data.error || '生成失败')
      }
    } catch (e: any) {
      setError(e.message || '网络异常')
    } finally {
      generatingRef.current = false
      setGenerating(false)
    }
  }, [])  // 空依赖 → 稳定引用，不会因 re-render 丢失事件绑定

  // 首次自动加载最新周报
  useEffect(() => {
    fetchLatest()
  }, [fetchLatest])

  // ─── 生成中状态 ───────────────────────────────────────────
  if (generating) {
    return (
      <div className="cyber-card p-5">
        <div className="flex items-center space-x-2 mb-6">
          <CalendarDays className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">周度选股顾问</h2>
        </div>
        <div className="rounded-lg border border-cyan-700/30 bg-cyan-900/5 p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
            <span className="text-cyan-400 font-medium">正在生成本周选股报告...</span>
          </div>
          <p className="text-sm text-gray-400 mb-4 leading-relaxed animate-pulse">
            {GENERATING_STEPS[generatingStep]}
          </p>
          <div className="space-y-1.5">
            {GENERATING_STEPS.map((step, i) => (
              <div key={i} className={`flex items-center space-x-2 text-xs transition-colors duration-500 ${i <= generatingStep ? 'text-cyan-400' : 'text-gray-700'}`}>
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${i < generatingStep ? 'bg-cyan-400' : i === generatingStep ? 'bg-cyan-400 animate-pulse' : 'bg-gray-700'}`} />
                <span>{step}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-600 mt-4">⏱ 生成过程约需 1-2 分钟，请勿关闭页面</p>
        </div>
      </div>
    )
  }

  return (
    <div className="cyber-card p-5">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <CalendarDays className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">周度选股顾问</h2>
          {report?.target_week && (
            <span className="text-xs text-gray-500 ml-1 font-mono bg-gray-800/50 px-2 py-0.5 rounded">
              {report.target_week}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {report && (
            <button
              onClick={fetchLatest}
              disabled={loading}
              className="flex items-center space-x-1 text-gray-400 hover:text-cyan-400 transition-colors disabled:opacity-40"
              title="刷新"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
          <button
            onClick={generateReport}
            disabled={generating || loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-900/30 border border-cyan-500/40 text-cyan-400 hover:bg-cyan-900/50 hover:border-cyan-400/60 transition-all disabled:opacity-40"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>生成本周推荐</span>
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-500/40 bg-red-900/10 text-sm text-red-400">
          ⚠️ {error}
          <button onClick={() => setError(null)} className="ml-2 text-xs underline opacity-70 hover:opacity-100">关闭</button>
        </div>
      )}

      {/* 骨架屏 */}
      {loading && !report && (
        <div className="space-y-4">
          <div className="h-20 rounded-lg bg-gray-800/40 animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        </div>
      )}

      {/* 空态 */}
      {!loading && !report && !error && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <ScanSearch className="w-12 h-12 text-gray-700 mb-4" />
          <p className="text-gray-500 text-sm mb-1">暂无周度选股报告</p>
          <p className="text-gray-600 text-xs mb-4">点击右上角「生成本周推荐」，使用反转策略为你精选本周最优股票</p>
          <button
            onClick={generateReport}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-900/30 border border-cyan-500/40 text-cyan-400 hover:bg-cyan-900/50 transition-all"
          >
            <Sparkles className="w-4 h-4" />
            <span>立即生成本周推荐</span>
          </button>
        </div>
      )}

      {/* 周报内容 */}
      {report && (
        <div className="space-y-4">
          {/* 报告日期 */}
          {report.report_date && (
            <div className="text-xs text-gray-600 font-mono">
              报告日期：{report.report_date}
            </div>
          )}

          {/* 大盘环境摘要 */}
          {report.market_summary && (
            <div className="rounded-lg border border-cyan-800/40 bg-cyan-900/5 p-4">
              <div className="flex items-center space-x-2 mb-2">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-semibold text-cyan-400">大盘环境摘要</span>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed">{report.market_summary}</p>
            </div>
          )}

          {/* Top 5 清单表格（V12b 指标速览） */}
          {report.recommendations && report.recommendations.length > 0 && (
            <Top5Table stocks={report.recommendations.slice(0, 5)} />
          )}

          {/* 推荐股票列表（卡片详情） */}
          {report.recommendations && report.recommendations.length > 0 && (
            <>
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-yellow-400" />
                <span className="text-sm font-semibold text-gray-300">
                  本周精选推荐
                </span>
                <span className="text-xs text-gray-600">
                  ({report.recommendations.length} 只 · 点击卡片查看理由/风险)
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {report.recommendations.map((stock, idx) => (
                  <StockCard key={stock.code} stock={stock} index={idx} />
                ))}
              </div>
            </>
          )}

          {/* 底部统计栏 */}
          {(report.total_candidates_scanned || report.reversal_filtered) && (
            <div className="flex items-center justify-center space-x-2 text-xs text-gray-500 py-2 border-t border-gray-800/50 flex-wrap gap-y-1">
              <div className="flex items-center space-x-1">
                <ScanSearch className="w-3.5 h-3.5 text-gray-600" />
                <span>扫描</span>
                <span className="font-mono font-bold text-gray-400">{report.total_candidates_scanned ?? '--'}</span>
                <span>只候选</span>
              </div>
              <span className="text-gray-700">→</span>
              <div className="flex items-center space-x-1">
                <span>量化预筛</span>
                <span className="font-mono font-bold text-cyan-400">{report.reversal_filtered ?? '--'}</span>
                <span>只</span>
              </div>
              <span className="text-gray-700">→</span>
              <div className="flex items-center space-x-1">
                <Sparkles className="w-3 h-3 text-yellow-400" />
                <span>最终推荐</span>
                <span className="font-mono font-bold text-yellow-400">{report.recommendations?.length ?? '--'}</span>
                <span>只</span>
              </div>
            </div>
          )}

          {/* 风险警告 */}
          {report.risk_warning && (
            <div className="rounded-lg border border-red-500/30 bg-red-900/10 p-4">
              <div className="flex items-center space-x-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <span className="text-sm font-semibold text-red-400">风险提醒</span>
              </div>
              <p className="text-sm text-red-300/80 leading-relaxed">{report.risk_warning}</p>
            </div>
          )}

          {/* 策略要点 */}
          {report.strategy_notes && (
            <div className="rounded-lg border border-purple-500/30 bg-purple-900/10 p-4">
              <div className="flex items-center space-x-2 mb-2">
                <BookOpen className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-semibold text-purple-400">策略要点</span>
              </div>
              <p className="text-sm text-purple-300/80 leading-relaxed whitespace-pre-line">{report.strategy_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
