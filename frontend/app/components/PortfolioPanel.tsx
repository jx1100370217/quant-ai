'use client'

import { useState, useEffect } from 'react'
import { Briefcase, ChevronUp, ChevronDown, RefreshCw, AlertCircle } from 'lucide-react'

interface Position {
  code: string
  name: string
  shares: number
  availableShares: number
  cost: number
  current: number
  marketValue: number
  pnl: number
  pnlPct: number
  todayPnl: number
  todayPnlPct: number
}

interface PortfolioData {
  cash: number
  totalAssets: number
  totalMarketValue: number
  totalPnl: number
  todayPnl: number
  positions: Position[]
}

export default function PortfolioPanel() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
  const [sortBy, setSortBy] = useState<'change' | 'pnl'>('change')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  const fetchPortfolio = async () => {
    try {
      const res = await fetch('/api/portfolio')
      const data = await res.json()
      if (data.success && data.data) {
        setPortfolio(data.data)
        setUpdatedAt(data.updatedAt)
        setError(null)
      } else {
        setError(data.error || '获取持仓失败')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPortfolio()
    const timer = setInterval(fetchPortfolio, 30000)
    return () => clearInterval(timer)
  }, [])

  if (loading) {
    return (
      <div className="cyber-card p-5 animate-pulse">
        <div className="h-6 bg-gray-700 rounded mb-4" />
        <div className="space-y-2">{[1,2,3].map(i=><div key={i} className="h-20 bg-gray-700 rounded" />)}</div>
      </div>
    )
  }

  if (error || !portfolio) {
    return (
      <div className="cyber-card p-5">
        <div className="flex items-center space-x-2 mb-3">
          <Briefcase className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">持仓概览</h2>
        </div>
        <div className="flex items-center space-x-2 text-yellow-400 text-sm p-3 bg-yellow-900/20 rounded-lg">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error || '暂无持仓数据'}</span>
        </div>
        <button onClick={fetchPortfolio} className="mt-3 text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1">
          <RefreshCw className="w-3 h-3" /><span>重试</span>
        </button>
      </div>
    )
  }

  const { positions, cash } = portfolio
  const totalAssets = portfolio.totalAssets ?? 0
  const totalMarketValue = portfolio.totalMarketValue ?? 0
  const totalPnl = portfolio.totalPnl ?? 0
  const todayPnl = portfolio.todayPnl ?? 0
  const totalReturn = totalAssets > 0 ? (totalPnl / (totalAssets - totalPnl)) * 100 : 0

  const sorted = [...positions].sort((a, b) =>
    sortBy === 'change' ? b.todayPnlPct - a.todayPnlPct : b.pnl - a.pnl
  )

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Briefcase className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">持仓概览</h2>
          <span className="text-xs text-gray-500">东方财富实时</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1 text-xs">
            <button onClick={() => setSortBy('change')} className={`px-2 py-1 rounded ${sortBy === 'change' ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-500'}`}>涨跌幅</button>
            <button onClick={() => setSortBy('pnl')} className={`px-2 py-1 rounded ${sortBy === 'pnl' ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-500'}`}>盈亏额</button>
          </div>
          <button onClick={fetchPortfolio} className="text-gray-500 hover:text-cyan-400 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-4 p-3 rounded-lg bg-gray-900/50">
        <div><div className="text-xs text-gray-500">总资产</div><div className="font-mono text-sm font-bold">¥{(totalAssets / 10000).toFixed(2)}万</div></div>
        <div><div className="text-xs text-gray-500">持仓市值</div><div className="font-mono text-sm font-bold">¥{(totalMarketValue / 10000).toFixed(2)}万</div></div>
        <div>
          <div className="text-xs text-gray-500">总盈亏</div>
          <div className={`font-mono text-sm font-bold ${totalPnl >= 0 ? 'text-neon-red' : 'text-neon-green'}`}>
            {totalPnl >= 0 ? '+' : ''}{(totalPnl / 10000).toFixed(2)}万
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">今日盈亏</div>
          <div className={`font-mono text-sm font-bold ${todayPnl >= 0 ? 'text-neon-red' : 'text-neon-green'}`}>
            {todayPnl >= 0 ? '+' : ''}{todayPnl.toFixed(2)}
          </div>
        </div>
      </div>

      {cash > 0.01 && (
        <div className="mb-2 px-3 py-2 rounded-lg bg-gray-900/30 border border-gray-800/50 flex justify-between items-center">
          <span className="text-sm text-gray-400">💰 可用资金</span>
          <span className="font-mono text-sm">¥{cash.toFixed(2)}</span>
        </div>
      )}

      <div className="space-y-2 max-h-[400px] overflow-y-auto scrollbar-thin">
        {sorted.length === 0 && (
          <div className="text-center text-gray-500 py-8 text-sm">暂无持仓</div>
        )}
        {sorted.map((p) => {
          // 防空值（API 可能返回 null/NaN）
          const current    = p.current    ?? 0
          const cost       = p.cost       ?? 0
          const pnl        = p.pnl        ?? 0
          const pnlPct     = p.pnlPct     ?? 0
          const todayPnl   = p.todayPnl   ?? 0
          const todayPnlPct = p.todayPnlPct ?? 0
          const isUp = pnl >= 0
          const isTodayUp = todayPnl >= 0
          return (
            <div key={p.code} className="p-3 rounded-lg bg-gray-900/30 hover:bg-gray-800/50 transition-colors border border-gray-800/50">
              <div className="flex justify-between items-center">
                <div>
                  <div className="font-medium text-sm">{p.name}</div>
                  <div className="text-xs text-gray-500 font-mono">{p.code} · {p.shares}股 {p.availableShares < p.shares ? `(可卖${p.availableShares})` : ''}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm font-bold">{current.toFixed(3)}</div>
                  <div className={`flex items-center justify-end text-xs font-mono ${isTodayUp ? 'text-neon-red' : 'text-neon-green'}`}>
                    {isTodayUp ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {(todayPnlPct * 100).toFixed(2)}%
                  </div>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-gray-500">成本 {cost.toFixed(3)}</span>
                <span className={`font-mono font-bold ${isUp ? 'text-neon-red' : 'text-neon-green'}`}>
                  {isUp ? '+' : ''}{(pnl / 10000).toFixed(2)}万 ({isUp ? '+' : ''}{(pnlPct * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="mt-1 h-1 rounded-full bg-gray-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${isUp ? 'bg-gradient-to-r from-red-600 to-red-400' : 'bg-gradient-to-r from-green-600 to-green-400'}`}
                  style={{ width: `${Math.min(Math.abs(pnlPct * 100) * 2, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {updatedAt && (
        <div className="mt-2 text-right text-xs text-gray-600">
          同步 {new Date(updatedAt).toLocaleTimeString('zh-CN')}
        </div>
      )}
    </div>
  )
}
