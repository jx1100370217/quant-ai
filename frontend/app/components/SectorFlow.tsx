'use client'

import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, RefreshCw, Waves } from 'lucide-react'
import { getMarketTone } from '../lib/marketColors'

interface SectorData {
  code: string
  name: string
  change: number
  flow: number
  flowRate: number
}

export default function SectorFlow() {
  const [sectors, setSectors] = useState<SectorData[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const res = await fetch('/api/market', { cache: 'no-store' })
      const data = await res.json()
      if (data.success && data.sectors) setSectors(data.sectors.slice(0, 7))
    } catch (error) {
      console.error('sector flow failed', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const timer = window.setInterval(fetchData, 30000)
    return () => window.clearInterval(timer)
  }, [])

  const maxFlow = useMemo(() => Math.max(...sectors.map(s => Math.abs(s.flow)), 1), [sectors])

  const formatFlow = (value: number) => {
    const abs = Math.abs(value)
    if (abs >= 1e8) return `${(value / 1e8).toFixed(1)}亿`
    if (abs >= 1e4) return `${(value / 1e4).toFixed(0)}万`
    return value.toFixed(0)
  }

  return (
    <div className="quant-panel relative h-full overflow-hidden p-6">
      <div className="panel-corner panel-corner-bl" />
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="panel-kicker">CAPITAL ROTATION</div>
          <div className="mt-2 flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white">行业资金雷达</h2>
            <span className="rounded border border-cyan-400/10 bg-cyan-400/[0.04] px-2 py-0.5 font-mono text-[9px] text-cyan-500">NET INFLOW</span>
          </div>
        </div>
        <RefreshCw className={`h-3.5 w-3.5 text-slate-600 ${loading ? 'animate-spin' : ''}`} />
      </div>

      <div className="mb-3 grid grid-cols-[36px_1fr_80px_92px] gap-3 px-3 font-mono text-[9px] uppercase tracking-[0.15em] text-slate-700">
        <span>Rank</span><span>Sector / momentum</span><span className="text-right">Change</span><span className="text-right">Inflow</span>
      </div>

      <div className="space-y-2">
        {loading && sectors.length === 0 ? (
          [1, 2, 3, 4, 5].map(i => <div key={i} className="h-14 animate-pulse rounded-xl bg-slate-900/50" />)
        ) : sectors.length === 0 ? (
          <div className="flex h-48 items-center justify-center text-xs text-slate-600">行业资金数据暂不可用</div>
        ) : sectors.map((sector, index) => {
          const changeTone = getMarketTone(sector.change)
          const flowTone = getMarketTone(sector.flow)
          const barWidth = Math.max(8, Math.abs(sector.flow) / maxFlow * 100)
          return (
            <div key={sector.code} className="sector-row group grid grid-cols-[36px_1fr_80px_92px] items-center gap-3">
              <span className={`flex h-7 w-7 items-center justify-center rounded-lg border font-mono text-[10px] ${index < 3 ? 'border-cyan-400/20 bg-cyan-400/[0.07] text-cyan-300' : 'border-slate-800 text-slate-600'}`}>{String(index + 1).padStart(2, '0')}</span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-slate-300 group-hover:text-white">{sector.name}</span>
                  {index === 0 && <ArrowUpRight className="h-3 w-3 text-cyan-400" />}
                </div>
                <div className="mt-2 h-0.5 overflow-hidden rounded-full bg-slate-900">
                  <div className={`h-full rounded-full ${sector.flow >= 0 ? 'bg-gradient-to-r from-red-500/40 to-red-400' : 'bg-gradient-to-r from-emerald-500/40 to-emerald-400'}`} style={{ width: `${barWidth}%` }} />
                </div>
              </div>
              <span className={`text-right font-mono text-xs font-semibold ${changeTone.text}`}>{sector.change > 0 ? '+' : ''}{sector.change.toFixed(2)}%</span>
              <span className={`text-right font-mono text-xs font-semibold ${flowTone.text}`}>{formatFlow(sector.flow)}</span>
            </div>
          )
        })}
      </div>

      <div className="mt-4 flex items-center gap-2 border-t border-slate-800/60 pt-4 text-[10px] text-slate-600">
        <Waves className="h-3 w-3 text-indigo-500" />
        按主力净流入强度排序 · 30 秒更新
      </div>
    </div>
  )
}
