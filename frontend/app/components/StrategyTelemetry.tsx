'use client'

import { useCallback, useEffect, useState } from 'react'
import { Activity, Database, Filter, Layers3, RefreshCw, Radio, ShieldCheck } from 'lucide-react'

interface WeeklyReportLite {
  strategy_version?: string
  target_week?: string
  total_candidates_scanned?: number
  reversal_filtered?: number
  recommendations?: Array<{ code: string }>
  invested_position_pct?: number
  cash_position_pct?: number
  scan_data_complete?: boolean | null
}

export default function StrategyTelemetry() {
  const [report, setReport] = useState<WeeklyReportLite | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchTelemetry = useCallback(async () => {
    try {
      const res = await fetch('/api/weekly-advisor', { cache: 'no-store' })
      const data = await res.json()
      if (data.success && data.data) setReport(data.data)
    } catch {
      // 遥测卡片保持降级态，不影响市场主界面。
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTelemetry()
    const timer = window.setInterval(fetchTelemetry, 60000)
    return () => window.clearInterval(timer)
  }, [fetchTelemetry])

  const scanned = report?.total_candidates_scanned ?? 0
  const filtered = report?.reversal_filtered ?? 0
  const selected = report?.recommendations?.length ?? 0
  const cash = report?.cash_position_pct ?? 100
  const complete = report?.scan_data_complete !== false

  return (
    <div className="quant-panel relative h-full overflow-hidden p-6">
      <div className="telemetry-glow" aria-hidden="true" />
      <div className="panel-corner panel-corner-tr" />

      <div className="relative z-10 flex h-full flex-col">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="panel-kicker">STRATEGY TELEMETRY</div>
            <h3 className="mt-2 text-xl font-semibold text-white">本周策略遥测</h3>
          </div>
          <button onClick={fetchTelemetry} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-slate-600 transition hover:border-cyan-500/30 hover:text-cyan-300" title="刷新策略遥测">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="mb-5 flex items-center justify-between rounded-xl border border-emerald-400/10 bg-emerald-400/[0.035] px-4 py-3">
          <div className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-emerald-400" />
            <div>
              <div className="text-xs font-medium text-slate-200">{report?.strategy_version || '策略等待加载'}</div>
              <div className="mt-0.5 font-mono text-[9px] text-slate-600">{report?.target_week || 'NO ACTIVE WINDOW'}</div>
            </div>
          </div>
          <span className={`rounded-full border px-2 py-1 font-mono text-[9px] ${complete ? 'border-emerald-400/15 text-emerald-400' : 'border-amber-400/20 text-amber-400'}`}>
            {complete ? 'NOMINAL' : 'DEGRADED'}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="telemetry-metric">
            <Database className="h-3.5 w-3.5 text-cyan-500" />
            <span>扫描口径</span>
            <strong>{scanned ? scanned.toLocaleString('zh-CN') : '—'}</strong>
          </div>
          <div className="telemetry-metric">
            <Filter className="h-3.5 w-3.5 text-indigo-400" />
            <span>量化预筛</span>
            <strong>{filtered || '—'}</strong>
          </div>
          <div className="telemetry-metric">
            <Layers3 className="h-3.5 w-3.5 text-amber-400" />
            <span>最终信号</span>
            <strong>{selected}</strong>
          </div>
          <div className="telemetry-metric">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            <span>现金缓冲</span>
            <strong>{cash.toFixed(0)}%</strong>
          </div>
        </div>

        <div className="mt-auto pt-6">
          <div className="mb-2 flex items-center justify-between font-mono text-[9px] tracking-[0.15em] text-slate-600">
            <span>CAPITAL DEPLOYMENT</span>
            <span>{(report?.invested_position_pct ?? 0).toFixed(0)}% ACTIVE</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-900">
            <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-indigo-500 transition-all duration-700" style={{ width: `${Math.max(0, Math.min(100, report?.invested_position_pct ?? 0))}%` }} />
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px] text-slate-600">
            <Activity className="h-3 w-3 text-cyan-500" />
            数据只用于研究信号，不接入真实账户
          </div>
        </div>
      </div>
    </div>
  )
}
