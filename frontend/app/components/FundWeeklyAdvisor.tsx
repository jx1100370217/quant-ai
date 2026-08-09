'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, BarChart3, BookOpen, Layers3, Loader2,
  RefreshCw, ScanSearch, Sparkles, Trophy, TrendingUp,
} from 'lucide-react'
import { getMarketTone } from '../lib/marketColors'

interface FundRecommendation {
  code: string
  name: string
  fund_type: string
  strategy_group: string
  nav: number
  nav_date: string
  position_pct: number
  potential_score: number
  upside_potential_pct: number
  return_1w: number
  return_1m: number
  return_3m: number
  volatility_3m: number
  max_drawdown_3m: number
  positive_week_ratio: number
  subscribe_status: string
  redeem_status: string
  reason: string
  risk_note: string
}

interface FundReport {
  report_date: string
  target_week: string
  market_summary: string
  recommendations: FundRecommendation[]
  universe_size: number
  funds_evaluated: number
  eligible_count: number
  invested_position_pct: number
  cash_position_pct: number
  risk_warning: string
  strategy_notes: string
  data_source: string
  strategy_version: string
  generated_at: string
}

function signed(value: number) {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

export default function FundWeeklyAdvisor() {
  const [report, setReport] = useState<FundReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const generatingRef = useRef(false)

  const fetchLatest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/weekly-advisor?asset=fund')
      const payload = await res.json()
      if (payload.success && payload.data) setReport(payload.data)
      else if (res.status === 404) setReport(null)
      else setError(payload.error || '获取公募基金周推荐失败')
    } catch (err: any) {
      setError(err?.message || '网络异常')
    } finally {
      setLoading(false)
    }
  }, [])

  const generate = useCallback(async () => {
    if (generatingRef.current) return
    generatingRef.current = true
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch('/api/weekly-advisor', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset: 'fund', force: true }),
      })
      const payload = await res.json()
      if (payload.success && payload.data) setReport(payload.data)
      else setError(payload.error || '生成公募基金周推荐失败')
    } catch (err: any) {
      setError(err?.message || '网络异常')
    } finally {
      generatingRef.current = false
      setGenerating(false)
    }
  }, [])

  useEffect(() => { fetchLatest() }, [fetchLatest])

  return (
    <section className="quant-panel relative overflow-hidden p-5 sm:p-6 lg:p-7">
      <div className="panel-corner panel-corner-tr" />
      <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="panel-kicker">PUBLIC FUND COMPARATOR</div>
          <div className="mt-2 flex flex-wrap items-center gap-2.5">
            <Layers3 className="h-5 w-5 text-cyan-400" />
            <h2 className="text-xl font-semibold text-white">具体公募基金周推荐</h2>
            {report?.target_week && <span className="rounded border border-slate-700/60 bg-slate-950/50 px-2 py-0.5 font-mono text-[10px] text-slate-500">{report.target_week}</span>}
            {report?.strategy_version && <span className="font-mono text-[9px] tracking-wider text-cyan-600">{report.strategy_version}</span>}
          </div>
        </div>
        <div className="flex items-center gap-3 self-end sm:self-auto">
          {report && <button onClick={fetchLatest} disabled={loading} title="刷新最新报告" className="text-slate-500 transition hover:text-cyan-400 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>}
          <button onClick={generate} disabled={generating || loading} className="flex items-center gap-2 rounded-xl border border-cyan-400/25 bg-cyan-400/[0.07] px-4 py-2 text-xs font-semibold text-cyan-300 transition hover:bg-cyan-400/[0.12] disabled:opacity-40">
            {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            <span>{generating ? '正在比较基金净值...' : '生成基金推荐'}</span>
          </button>
        </div>
      </header>

      {error && <div className="mb-4 rounded-xl border border-red-500/30 bg-red-950/20 p-3 text-sm text-red-400">⚠️ {error}</div>}
      {loading && !report && <div className="h-48 animate-pulse rounded-2xl bg-slate-900/60" />}
      {!loading && !report && !error && (
        <div className="flex flex-col items-center py-14 text-center"><ScanSearch className="mb-4 h-11 w-11 text-slate-700" /><p className="text-sm text-slate-500">暂无具体基金周推荐</p><p className="mt-1 text-xs text-slate-600">横向比较财通成长优选混合C等主动权益基金的盈利空间</p><button onClick={generate} className="mt-5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-xs font-semibold text-cyan-300">立即生成</button></div>
      )}

      {report && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-cyan-800/35 bg-cyan-950/10 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-cyan-300"><BarChart3 className="h-4 w-4" />本周基金比较摘要</div><p className="text-sm leading-relaxed text-slate-300">{report.market_summary}</p></div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[
              ['具体基金池', report.universe_size, '只'], ['完成评估', report.funds_evaluated, '只'], ['趋势入选', report.eligible_count, '只'],
              ['建议基金仓位', report.invested_position_pct, '%'], ['保留现金', report.cash_position_pct, '%'],
            ].map(([label, value, unit]) => <div key={String(label)} className="rounded-xl border border-slate-800/70 bg-slate-950/35 px-4 py-3"><div className="text-[10px] tracking-wider text-slate-600">{label}</div><div className="mt-1 font-mono text-xl font-bold text-white">{value}<span className="ml-1 text-xs text-slate-600">{unit}</span></div></div>)}
          </div>

          {report.recommendations.length > 0 ? (
            <div className="overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-950/25">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1080px] text-xs">
                  <thead className="border-b border-slate-800/70 bg-slate-900/60 text-slate-600"><tr><th className="px-4 py-3 text-left">排名 / 具体基金</th><th className="px-3 py-3 text-right">建议仓位</th><th className="px-3 py-3 text-right">盈利空间分</th><th className="px-3 py-3 text-right">上行情景</th><th className="px-3 py-3 text-right">近1周</th><th className="px-3 py-3 text-right">近1月</th><th className="px-3 py-3 text-right">近3月</th><th className="px-3 py-3 text-right">正收益周</th><th className="px-4 py-3 text-right">3月回撤</th></tr></thead>
                  <tbody>{report.recommendations.map((fund, index) => (
                    <tr key={fund.code} className="border-b border-slate-800/50 transition hover:bg-cyan-950/15">
                      <td className="px-4 py-3"><div className="flex items-center gap-3"><span className="font-mono text-slate-700">0{index + 1}</span><div><div className="font-semibold text-white">{fund.name} <span className="ml-1 font-mono text-[10px] text-slate-600">{fund.code}</span></div><div className="mt-0.5 text-[10px] text-slate-600">{fund.strategy_group} · {fund.fund_type} · 净值 {fund.nav.toFixed(4)}</div></div></div></td>
                      <td className="px-3 py-3 text-right font-mono font-bold text-cyan-300">{fund.position_pct.toFixed(0)}%</td>
                      <td className="px-3 py-3 text-right font-mono font-bold text-yellow-400">{fund.potential_score.toFixed(1)}</td>
                      <td className="px-3 py-3 text-right font-mono font-bold text-red-400">+{fund.upside_potential_pct.toFixed(2)}%</td>
                      <td className={`px-3 py-3 text-right font-mono ${getMarketTone(fund.return_1w).text}`}>{signed(fund.return_1w)}</td>
                      <td className={`px-3 py-3 text-right font-mono ${getMarketTone(fund.return_1m).text}`}>{signed(fund.return_1m)}</td>
                      <td className={`px-3 py-3 text-right font-mono ${getMarketTone(fund.return_3m).text}`}>{signed(fund.return_3m)}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{fund.positive_week_ratio.toFixed(0)}%</td>
                      <td className={`px-4 py-3 text-right font-mono ${getMarketTone(fund.max_drawdown_3m).text}`}>{signed(fund.max_drawdown_3m)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          ) : <div className="rounded-2xl border border-yellow-800/30 bg-yellow-950/10 p-6 text-center text-sm text-yellow-300/80">本周没有具体基金通过全部趋势与回撤约束，策略保持现金。</div>}

          {report.recommendations.length > 0 && (
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {report.recommendations.map((fund, index) => (
                <article key={fund.code} className="rounded-2xl border border-slate-800/70 bg-slate-950/30 p-4">
                  <div className="flex items-start justify-between gap-3"><div className="flex items-start gap-2"><Trophy className={`mt-0.5 h-4 w-4 ${index === 0 ? 'text-yellow-400' : 'text-slate-600'}`} /><div><div className="font-semibold text-white">{fund.name}</div><div className="mt-1 font-mono text-[10px] text-slate-600">{fund.code} · {fund.strategy_group}</div></div></div><div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-2.5 py-1 font-mono text-sm font-bold text-yellow-400">{fund.potential_score}</div></div>
                  <div className="my-3 grid grid-cols-2 gap-2 text-xs"><div className="rounded-lg bg-red-950/15 p-2"><TrendingUp className="mb-1 h-3.5 w-3.5 text-red-400" /><span className="text-slate-600">量化上行情景</span><div className="font-mono font-bold text-red-400">+{fund.upside_potential_pct.toFixed(2)}%</div></div><div className="rounded-lg bg-slate-900/50 p-2"><span className="text-slate-600">申购 / 赎回</span><div className="mt-1 text-[11px] text-slate-300">{fund.subscribe_status} / {fund.redeem_status}</div></div></div>
                  <p className="text-xs leading-relaxed text-slate-400">{fund.reason}</p><p className="mt-2 border-t border-slate-800/60 pt-2 text-[11px] leading-relaxed text-orange-300/60">{fund.risk_note}</p>
                </article>
              ))}
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-2"><div className="rounded-xl border border-red-500/25 bg-red-950/10 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-400"><AlertTriangle className="h-4 w-4" />风险提醒</div><p className="text-xs leading-relaxed text-red-300/70">{report.risk_warning}</p></div><div className="rounded-xl border border-purple-500/25 bg-purple-950/10 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-purple-400"><BookOpen className="h-4 w-4" />策略说明</div><p className="text-xs leading-relaxed text-purple-300/70">{report.strategy_notes}</p></div></div>
          <div className="text-center font-mono text-[9px] tracking-wider text-slate-700">DATA · {report.data_source} · NAV UPDATED BY FUND TRADING DAY</div>
        </div>
      )}
    </section>
  )
}
