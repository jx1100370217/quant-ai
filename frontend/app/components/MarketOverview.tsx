'use client'

import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface IndexData {
  code: string; name: string; current: number; change: number; changePercent: number;
  volume: number; amount: number
}

interface SectorData {
  code: string; name: string; change: number; flow: number; flowRate: number
}

export default function MarketOverview() {
  const [indices, setIndices] = useState<IndexData[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const fetchData = async () => {
    try {
      const res = await fetch('/api/market')
      const data = await res.json()
      if (data.success) {
        setIndices(data.indices)
        setLastUpdate(new Date().toLocaleTimeString('zh-CN'))
      }
    } catch (e) { console.error('fetch market failed', e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 15000) // 每15秒刷新
    return () => clearInterval(timer)
  }, [])

  const nameMap: Record<string, string> = { '000001': '上证指数', '399001': '深证成指', '399006': '创业板指' }

  if (loading) {
    return (
      <div className="cyber-card p-6 animate-pulse">
        <div className="h-8 bg-gray-700 rounded mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="h-24 bg-gray-700 rounded" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="cyber-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">市场概览</h2>
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <RefreshCw className="w-3 h-3" />
          <span>实时</span>
          {lastUpdate && <span className="text-gray-600">更新于 {lastUpdate}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {indices.map((idx) => {
          const isUp = idx.changePercent >= 0
          return (
            <div key={idx.code} className={`p-4 rounded-lg border ${isUp ? 'border-red-900/30 bg-red-900/10' : 'border-green-900/30 bg-green-900/10'}`}>
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="text-sm text-gray-400">{nameMap[idx.code] || idx.name}</div>
                  <div className="text-xs text-gray-600 font-mono">{idx.code}</div>
                </div>
                {isUp ? <TrendingUp className="w-4 h-4 text-red-500" /> : <TrendingDown className="w-4 h-4 text-green-500" />}
              </div>
              <div className={`text-2xl font-bold font-mono ${isUp ? 'text-red-400' : 'text-green-400'}`}>
                {idx.current.toFixed(2)}
              </div>
              <div className="flex items-center space-x-3 mt-1 text-sm font-mono">
                <span className={isUp ? 'text-red-400' : 'text-green-400'}>
                  {isUp ? '↑' : '↓'} {Math.abs(idx.change).toFixed(2)}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-xs ${isUp ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'}`}>
                  {isUp ? '+' : ''}{idx.changePercent.toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                <span>成交量 {(idx.volume / 1e8).toFixed(1)}亿</span>
                <span>成交额 {(idx.amount / 1e8).toFixed(0)}亿</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
