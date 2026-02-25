'use client'

import { useState, useEffect } from 'react'
import { Briefcase, ChevronUp, ChevronDown, RefreshCw } from 'lucide-react'

interface Holding {
  code: string; name: string; shares: number; cost: number; current: number; change: number
}

// 持仓配置（成本和股数是用户设置的，行情实时获取）
const HOLDINGS_CONFIG = [
  { code: '300394', name: '天孚通信', shares: 652, cost: 280.50 },
  { code: '002916', name: '深南电路', shares: 580, cost: 220.00 },
  { code: '600183', name: '生益科技', shares: 1972, cost: 58.30 },
  { code: '300308', name: '中际旭创', shares: 224, cost: 510.00 },
  { code: '002463', name: '沪电股份', shares: 1872, cost: 65.40 },
  { code: '300502', name: '新易盛', shares: 314, cost: 350.00 },
]

export default function PortfolioPanel() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [sortBy, setSortBy] = useState<'change' | 'pnl'>('change')
  const [loading, setLoading] = useState(true)

  const fetchQuotes = async () => {
    try {
      const codes = HOLDINGS_CONFIG.map(h => h.code).join(',')
      const res = await fetch(`/api/quote?codes=${codes}`)
      const data = await res.json()
      if (data.success && data.data) {
        const updated = HOLDINGS_CONFIG.map(h => {
          const q = data.data.find((d: any) => d.code === h.code)
          return {
            ...h,
            current: q?.current ?? h.cost,
            change: q?.percent ?? 0,
          }
        })
        setHoldings(updated)
      }
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchQuotes()
    const timer = setInterval(fetchQuotes, 15000)
    return () => clearInterval(timer)
  }, [])

  const totalCost = holdings.reduce((s, h) => s + h.cost * h.shares, 0)
  const totalValue = holdings.reduce((s, h) => s + h.current * h.shares, 0)
  const totalPnL = totalValue - totalCost
  const totalReturn = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0

  const sorted = [...holdings].sort((a, b) =>
    sortBy === 'change' ? b.change - a.change : ((b.current - b.cost) * b.shares) - ((a.current - a.cost) * a.shares)
  )

  if (loading) {
    return <div className="cyber-card p-5 animate-pulse"><div className="h-6 bg-gray-700 rounded mb-4" /><div className="space-y-2">{[1,2,3].map(i=><div key={i} className="h-20 bg-gray-700 rounded" />)}</div></div>
  }

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Briefcase className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">持仓概览</h2>
        </div>
        <div className="flex space-x-1 text-xs">
          <button onClick={() => setSortBy('change')} className={`px-2 py-1 rounded ${sortBy === 'change' ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-500'}`}>涨跌幅</button>
          <button onClick={() => setSortBy('pnl')} className={`px-2 py-1 rounded ${sortBy === 'pnl' ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-500'}`}>盈亏额</button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4 p-3 rounded-lg bg-gray-900/50">
        <div><div className="text-xs text-gray-500">总市值</div><div className="font-mono text-sm font-bold">¥{(totalValue / 10000).toFixed(2)}万</div></div>
        <div><div className="text-xs text-gray-500">总盈亏</div><div className={`font-mono text-sm font-bold ${totalPnL >= 0 ? 'text-neon-red' : 'text-neon-green'}`}>{totalPnL >= 0 ? '+' : ''}{(totalPnL / 10000).toFixed(2)}万</div></div>
        <div><div className="text-xs text-gray-500">总收益率</div><div className={`font-mono text-sm font-bold ${totalReturn >= 0 ? 'text-neon-red' : 'text-neon-green'}`}>{totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%</div></div>
      </div>

      <div className="space-y-2 max-h-[400px] overflow-y-auto scrollbar-thin">
        {sorted.map((h) => {
          const pnl = (h.current - h.cost) * h.shares
          const pnlPct = ((h.current - h.cost) / h.cost) * 100
          const isUp = pnl >= 0
          return (
            <div key={h.code} className="p-3 rounded-lg bg-gray-900/30 hover:bg-gray-800/50 transition-colors border border-gray-800/50">
              <div className="flex justify-between items-center">
                <div><div className="font-medium text-sm">{h.name}</div><div className="text-xs text-gray-500 font-mono">{h.code} · {h.shares}股</div></div>
                <div className="text-right">
                  <div className="font-mono text-sm font-bold">{h.current.toFixed(2)}</div>
                  <div className={`flex items-center justify-end text-xs font-mono ${isUp ? 'text-neon-red' : 'text-neon-green'}`}>
                    {isUp ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}{h.change.toFixed(2)}%
                  </div>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-gray-500">成本 {h.cost.toFixed(2)}</span>
                <span className={`font-mono font-bold ${isUp ? 'text-neon-red' : 'text-neon-green'}`}>
                  {isUp ? '+' : ''}{(pnl / 10000).toFixed(2)}万 ({isUp ? '+' : ''}{pnlPct.toFixed(1)}%)
                </span>
              </div>
              <div className="mt-1 h-1 rounded-full bg-gray-800 overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-500 ${isUp ? 'bg-gradient-to-r from-red-600 to-red-400' : 'bg-gradient-to-r from-green-600 to-green-400'}`}
                  style={{ width: `${Math.min(Math.abs(pnlPct) * 2, 100)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
