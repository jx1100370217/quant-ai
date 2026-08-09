'use client'

import { useEffect, useState } from 'react'
import { Activity, Minus, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react'
import { getMarketTone, marketArrow } from '../lib/marketColors'

interface IndexData {
  code: string
  name: string
  current: number
  change: number
  changePercent: number
  volume: number
  amount: number
}

const INDEX_LABELS: Record<string, string> = {
  '000001': 'SSE COMPOSITE',
  '399001': 'SZSE COMPONENT',
  '399006': 'CHINEXT PRICE',
}

export default function MarketOverview() {
  const [indices, setIndices] = useState<IndexData[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const fetchData = async () => {
    try {
      const res = await fetch('/api/market', { cache: 'no-store' })
      const data = await res.json()
      if (data.success) {
        setIndices(data.indices || [])
        setLastUpdate(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
      }
    } catch (error) {
      console.error('fetch market failed', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const timer = window.setInterval(fetchData, 15000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="quant-panel relative h-full overflow-hidden p-6">
      <div className="panel-corner panel-corner-tl" />
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="panel-kicker">MARKET PULSE</div>
          <div className="mt-2 flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white">核心指数</h2>
            <span className="hidden items-center gap-1.5 rounded-full border border-emerald-400/10 bg-emerald-400/[0.04] px-2 py-1 font-mono text-[9px] text-emerald-400 sm:inline-flex">
              <span className="h-1 w-1 rounded-full bg-emerald-400 animate-pulse" /> LIVE FEED
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 font-mono text-[9px] text-slate-600">
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          {lastUpdate || 'SYNCING'}
        </div>
      </div>

      {loading && indices.length === 0 ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {[1, 2, 3].map(i => <div key={i} className="h-40 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/40" />)}
        </div>
      ) : indices.length === 0 ? (
        <div className="flex h-40 items-center justify-center rounded-2xl border border-dashed border-slate-800 text-xs text-slate-600">指数数据暂不可用</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {indices.map((idx, index) => {
            const tone = getMarketTone(idx.changePercent)
            const DirectionIcon = tone.direction === 'up' ? TrendingUp : tone.direction === 'down' ? TrendingDown : Minus
            const glow = tone.direction === 'up' ? 'market-card-up' : tone.direction === 'down' ? 'market-card-down' : ''

            return (
              <article key={idx.code} className={`market-index-card ${glow}`}>
                <div className="mb-6 flex items-start justify-between">
                  <div>
                    <div className="text-sm font-medium text-slate-200">{idx.name}</div>
                    <div className="mt-1 font-mono text-[9px] tracking-[0.15em] text-slate-600">{INDEX_LABELS[idx.code] || idx.code}</div>
                  </div>
                  <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${tone.border} ${tone.background}`}>
                    <DirectionIcon className={`h-4 w-4 ${tone.text}`} />
                  </div>
                </div>

                <div className={`font-mono text-3xl font-semibold tracking-[-0.04em] ${tone.text}`}>
                  {idx.current.toFixed(2)}
                </div>
                <div className="mt-2 flex items-center gap-2 font-mono text-xs">
                  <span className={tone.text}>{marketArrow(idx.changePercent)} {Math.abs(idx.change).toFixed(2)}</span>
                  <span className={`rounded px-1.5 py-0.5 ${tone.background} ${tone.text}`}>
                    {idx.changePercent > 0 ? '+' : ''}{idx.changePercent.toFixed(2)}%
                  </span>
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-slate-800/70 pt-3 font-mono text-[9px] text-slate-600">
                  <span>VOL {(idx.volume / 1e8).toFixed(1)}亿</span>
                  <span>AMT {(idx.amount / 1e8).toFixed(0)}亿</span>
                </div>
                <span className="absolute bottom-3 right-3 font-mono text-[9px] text-slate-800">0{index + 1}</span>
              </article>
            )
          })}
        </div>
      )}

      <div className="mt-4 flex items-center gap-2 text-[10px] text-slate-600">
        <Activity className="h-3 w-3 text-cyan-600" />
        行情颜色遵循 A 股惯例：上涨红 · 下跌绿
      </div>
    </div>
  )
}
