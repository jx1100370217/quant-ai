'use client'

import { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp } from 'lucide-react'

interface SectorData {
  code: string; name: string; change: number; flow: number; flowRate: number
}

export default function SectorFlow() {
  const [sectors, setSectors] = useState<SectorData[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const res = await fetch('/api/market')
      const data = await res.json()
      if (data.success && data.sectors) setSectors(data.sectors.slice(0, 5))
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 30000)
    return () => clearInterval(timer)
  }, [])

  const formatFlow = (v: number) => {
    const abs = Math.abs(v)
    if (abs >= 1e8) return `${(v / 1e8).toFixed(1)}亿`
    if (abs >= 1e4) return `${(v / 1e4).toFixed(0)}万`
    return v.toFixed(0)
  }

  if (loading) {
    return <div className="cyber-card p-5 animate-pulse"><div className="h-6 bg-gray-700 rounded mb-4" /><div className="space-y-3">{[1,2,3,4,5].map(i=><div key={i} className="h-14 bg-gray-700 rounded" />)}</div></div>
  }

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <TrendingUp className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">行业轮动</h2>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2 py-0.5 rounded bg-cyan-900/50 text-cyan-400">主力净流入</span>
          <RefreshCw className="w-3 h-3 text-gray-500" />
        </div>
      </div>

      {/* 表头 */}
      <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 mb-2 px-2">
        <div className="col-span-1">排名</div>
        <div className="col-span-5">板块</div>
        <div className="col-span-3 text-right">涨跌幅</div>
        <div className="col-span-3 text-right">主力净流入</div>
      </div>

      <div className="space-y-1.5">
        {sectors.map((s, i) => {
          const isTop3 = i < 3
          return (
            <div key={s.code} className={`grid grid-cols-12 gap-2 items-center p-2.5 rounded-lg transition-colors ${isTop3 ? 'bg-red-900/10 hover:bg-red-900/20' : 'bg-gray-900/30 hover:bg-gray-800/40'}`}>
              {/* 排名 */}
              <div className="col-span-1">
                <span className={`inline-flex items-center justify-center w-5 h-5 rounded text-xs font-bold ${isTop3 ? 'bg-red-600 text-white' : 'bg-gray-700 text-gray-400'}`}>
                  {i + 1}
                </span>
              </div>
              {/* 板块名 */}
              <div className="col-span-5">
                <span className="text-sm font-medium">{s.name}</span>
              </div>
              {/* 涨跌幅 */}
              <div className="col-span-3 text-right">
                <span className={`text-sm font-mono font-bold ${s.change >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {s.change >= 0 ? '+' : ''}{s.change.toFixed(2)}%
                </span>
              </div>
              {/* 主力净流入 */}
              <div className="col-span-3 text-right">
                <span className={`text-sm font-mono font-bold ${s.flow > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {formatFlow(s.flow)}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
