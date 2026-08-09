'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, Bitcoin, BookOpen, Loader2, RefreshCw,
  ScanSearch, ShieldAlert, Sparkles, Trophy, TrendingUp,
} from 'lucide-react'
import { getMarketTone } from '../lib/marketColors'

interface CryptoRecommendation {
  symbol: string
  name: string
  category: string
  current_price: number
  position_pct: number
  potential_score: number
  upside_potential_pct: number
  return_7d: number
  return_30d: number
  ma20_gap: number
  ma60_gap: number
  volume_ratio_7d: number
  volatility_20d: number
  max_drawdown_30d: number
  risk_line_price?: number | null
  reason: string
  risk_note: string
}

interface CryptoReport {
  report_date: string
  target_week: string
  market_summary: string
  recommendations: CryptoRecommendation[]
  universe_size: number
  assets_evaluated: number
  eligible_count: number
  invested_position_pct: number
  cash_position_pct: number
  risk_warning: string
  strategy_notes: string
  data_source: string
  data_updated_at: string
  strategy_version: string
  generated_at: string
}

function signed(value: number) {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function price(value: number) {
  if (value >= 1000) return value.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (value >= 1) return value.toLocaleString('en-US', { maximumFractionDigits: 4 })
  return value.toLocaleString('en-US', { maximumFractionDigits: 8 })
}

export default function CryptoWeeklyAdvisor() {
  const [report, setReport] = useState<CryptoReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const generatingRef = useRef(false)

  const fetchLatest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/weekly-advisor?asset=crypto')
      const payload = await res.json()
      if (payload.success && payload.data) setReport(payload.data)
      else if (res.status === 404) setReport(null)
      else setError(payload.error || '获取加密货币周推荐失败')
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
        body: JSON.stringify({ asset: 'crypto', force: true }),
      })
      const payload = await res.json()
      if (payload.success && payload.data) setReport(payload.data)
      else setError(payload.error || '生成加密货币周推荐失败')
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
      <div className="absolute right-[-80px] top-[-110px] h-72 w-72 rounded-full bg-orange-500/[0.035] blur-3xl" />
      <div className="panel-corner panel-corner-tr" />
      <header className="relative mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div><div className="font-mono text-[9px] tracking-[0.24em] text-orange-500/70">CRYPTO CROSS-ASSET RANKING</div><div className="mt-2 flex flex-wrap items-center gap-2.5"><Bitcoin className="h-5 w-5 text-orange-400" /><h2 className="text-xl font-semibold text-white">主流加密货币周推荐</h2>{report?.target_week && <span className="rounded border border-slate-700/60 bg-slate-950/50 px-2 py-0.5 font-mono text-[10px] text-slate-500">{report.target_week}</span>}{report?.strategy_version && <span className="font-mono text-[9px] tracking-wider text-orange-600">{report.strategy_version}</span>}</div></div>
        <div className="flex items-center gap-3 self-end sm:self-auto">{report && <button onClick={fetchLatest} disabled={loading} title="刷新最新报告" className="text-slate-500 transition hover:text-orange-400 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>}<button onClick={generate} disabled={generating || loading} className="flex items-center gap-2 rounded-xl border border-orange-400/25 bg-orange-400/[0.07] px-4 py-2 text-xs font-semibold text-orange-300 transition hover:bg-orange-400/[0.12] disabled:opacity-40">{generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}<span>{generating ? '正在比较主流币...' : '生成币种推荐'}</span></button></div>
      </header>

      {error && <div className="mb-4 rounded-xl border border-red-500/30 bg-red-950/20 p-3 text-sm text-red-400">⚠️ {error}</div>}
      {loading && !report && <div className="h-52 animate-pulse rounded-2xl bg-slate-900/60" />}
      {!loading && !report && !error && <div className="flex flex-col items-center py-14 text-center"><ScanSearch className="mb-4 h-11 w-11 text-slate-700" /><p className="text-sm text-slate-500">暂无多币种周推荐</p><p className="mt-1 text-xs text-slate-600">横向比较 BTC、ETH、SOL 等主流币的盈利空间</p><button onClick={generate} className="mt-5 rounded-xl border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-xs font-semibold text-orange-300">立即生成</button></div>}

      {report && (
        <div className="relative space-y-4">
          <div className="rounded-2xl border border-orange-500/20 bg-gradient-to-br from-orange-500/[0.07] via-slate-950/25 to-slate-950/40 p-5">
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center"><div><div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-slate-600"><Activity className="h-3.5 w-3.5 text-orange-500" />LIQUID SPOT UNIVERSE</div><p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-300">{report.market_summary}</p></div><div className="grid shrink-0 grid-cols-2 gap-2"><div className="rounded-xl border border-orange-500/20 bg-orange-500/5 px-4 py-3 text-center"><div className="text-[9px] text-slate-600">建议风险仓位</div><div className="mt-1 font-mono text-xl font-bold text-orange-400">{report.invested_position_pct.toFixed(0)}%</div></div><div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-center"><div className="text-[9px] text-slate-600">保留现金</div><div className="mt-1 font-mono text-xl font-bold text-emerald-400">{report.cash_position_pct.toFixed(0)}%</div></div></div></div>
          </div>

          <div className="grid grid-cols-3 gap-3"><div className="rounded-xl border border-slate-800/70 bg-slate-950/35 p-3"><div className="text-[10px] text-slate-600">主流币池</div><div className="mt-1 font-mono text-xl font-bold text-white">{report.universe_size}<span className="ml-1 text-xs text-slate-600">个</span></div></div><div className="rounded-xl border border-slate-800/70 bg-slate-950/35 p-3"><div className="text-[10px] text-slate-600">完成评估</div><div className="mt-1 font-mono text-xl font-bold text-white">{report.assets_evaluated}<span className="ml-1 text-xs text-slate-600">个</span></div></div><div className="rounded-xl border border-slate-800/70 bg-slate-950/35 p-3"><div className="text-[10px] text-slate-600">趋势入选</div><div className="mt-1 font-mono text-xl font-bold text-orange-400">{report.eligible_count}<span className="ml-1 text-xs text-slate-600">个</span></div></div></div>

          {report.recommendations.length > 0 ? (
            <div className="overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-950/25"><div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-xs"><thead className="border-b border-slate-800/70 bg-slate-900/60 text-slate-600"><tr><th className="px-4 py-3 text-left">排名 / 币种</th><th className="px-3 py-3 text-right">仓位</th><th className="px-3 py-3 text-right">盈利空间分</th><th className="px-3 py-3 text-right">上行情景</th><th className="px-3 py-3 text-right">7日</th><th className="px-3 py-3 text-right">30日</th><th className="px-3 py-3 text-right">距MA20</th><th className="px-3 py-3 text-right">量能比</th><th className="px-3 py-3 text-right">年化波动</th><th className="px-4 py-3 text-right">30日回撤</th></tr></thead><tbody>{report.recommendations.map((coin, index) => <tr key={coin.symbol} className="border-b border-slate-800/50 transition hover:bg-orange-950/10"><td className="px-4 py-3"><div className="flex items-center gap-3"><span className="font-mono text-slate-700">0{index + 1}</span><div><div className="font-semibold text-white">{coin.name} <span className="ml-1 font-mono text-[10px] text-orange-500/70">{coin.symbol}</span></div><div className="mt-0.5 text-[10px] text-slate-600">{coin.category} · ${price(coin.current_price)}</div></div></div></td><td className="px-3 py-3 text-right font-mono font-bold text-orange-300">{coin.position_pct.toFixed(0)}%</td><td className="px-3 py-3 text-right font-mono font-bold text-yellow-400">{coin.potential_score.toFixed(1)}</td><td className="px-3 py-3 text-right font-mono font-bold text-red-400">+{coin.upside_potential_pct.toFixed(2)}%</td><td className={`px-3 py-3 text-right font-mono ${getMarketTone(coin.return_7d).text}`}>{signed(coin.return_7d)}</td><td className={`px-3 py-3 text-right font-mono ${getMarketTone(coin.return_30d).text}`}>{signed(coin.return_30d)}</td><td className={`px-3 py-3 text-right font-mono ${getMarketTone(coin.ma20_gap).text}`}>{signed(coin.ma20_gap)}</td><td className="px-3 py-3 text-right font-mono text-slate-300">{coin.volume_ratio_7d.toFixed(2)}</td><td className="px-3 py-3 text-right font-mono text-slate-300">{coin.volatility_20d.toFixed(1)}%</td><td className={`px-4 py-3 text-right font-mono ${getMarketTone(coin.max_drawdown_30d).text}`}>{signed(coin.max_drawdown_30d)}</td></tr>)}</tbody></table></div></div>
          ) : <div className="rounded-2xl border border-yellow-800/30 bg-yellow-950/10 p-6 text-center text-sm text-yellow-300/80">本周没有主流币通过全部趋势与风险约束，策略保持现金。</div>}

          {report.recommendations.length > 0 && <div className="grid gap-3 lg:grid-cols-3">{report.recommendations.map((coin, index) => <article key={coin.symbol} className="rounded-2xl border border-slate-800/70 bg-slate-950/30 p-4"><div className="flex items-start justify-between gap-3"><div className="flex items-start gap-2"><Trophy className={`mt-0.5 h-4 w-4 ${index === 0 ? 'text-yellow-400' : 'text-slate-600'}`} /><div><div className="font-semibold text-white">{coin.name}</div><div className="mt-1 font-mono text-[10px] text-orange-500/70">{coin.symbol} · {coin.category}</div></div></div><div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-2.5 py-1 font-mono text-sm font-bold text-yellow-400">{coin.potential_score}</div></div><div className="my-3 grid grid-cols-2 gap-2 text-xs"><div className="rounded-lg bg-red-950/15 p-2"><TrendingUp className="mb-1 h-3.5 w-3.5 text-red-400" /><span className="text-slate-600">量化上行情景</span><div className="font-mono font-bold text-red-400">+{coin.upside_potential_pct.toFixed(2)}%</div></div><div className="rounded-lg bg-green-950/15 p-2"><ShieldAlert className="mb-1 h-3.5 w-3.5 text-green-400" /><span className="text-slate-600">风险线</span><div className="font-mono font-bold text-green-400">${price(coin.risk_line_price || 0)}</div></div></div><p className="text-xs leading-relaxed text-slate-400">{coin.reason}</p><p className="mt-2 border-t border-slate-800/60 pt-2 text-[11px] leading-relaxed text-orange-300/60">{coin.risk_note}</p></article>)}</div>}

          <div className="grid gap-3 lg:grid-cols-2"><div className="rounded-xl border border-red-500/25 bg-red-950/10 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-400"><AlertTriangle className="h-4 w-4" />风险提醒</div><p className="text-xs leading-relaxed text-red-300/70">{report.risk_warning}</p></div><div className="rounded-xl border border-purple-500/25 bg-purple-950/10 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-purple-400"><BookOpen className="h-4 w-4" />策略说明</div><p className="text-xs leading-relaxed text-purple-300/70">{report.strategy_notes}</p></div></div>
          <div className="text-center font-mono text-[9px] tracking-wider text-slate-700">DATA · {report.data_source} · {report.data_updated_at.replace('T', ' ')}</div>
        </div>
      )}
    </section>
  )
}
