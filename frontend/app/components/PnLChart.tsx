'use client'

import { useState, useEffect } from 'react'
import { TrendingUp } from 'lucide-react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

interface PnLPoint { date: string; pnl: number; benchmark: number }

interface Props {
  stockCode?: string
  stockName?: string
  cost?: number
}

const HOLDINGS_MAP: Record<string, { name: string; cost: number }> = {
  '300394': { name: '天孚通信', cost: 280.50 },
  '002916': { name: '深南电路', cost: 220.00 },
  '600183': { name: '生益科技', cost: 58.30 },
  '300308': { name: '中际旭创', cost: 510.00 },
  '002463': { name: '沪电股份', cost: 65.40 },
  '300502': { name: '新易盛', cost: 350.00 },
}

export default function PnLChart({ stockCode: externalCode, stockName: externalName, cost: externalCost }: Props) {
  const [data, setData] = useState<PnLPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [activeCode, setActiveCode] = useState(externalCode || '600183')

  const holding = HOLDINGS_MAP[activeCode]
  const cost = externalCost ?? holding?.cost ?? 0
  const name = externalName ?? holding?.name ?? activeCode

  const fetchPnL = async (code: string, costPrice: number) => {
    setLoading(true)
    try {
      // 并行获取个股 + 沪深300 K线
      const [stockRes, benchRes] = await Promise.all([
        fetch(`/api/kline?code=${code}&klt=101&lmt=60`),
        fetch(`/api/kline?code=000300&klt=101&lmt=60`),
      ])
      const stockJson = await stockRes.json()
      const benchJson = await benchRes.json()

      if (stockJson.success && stockJson.klines?.length) {
        const klines = stockJson.klines
        const benchKlines: any[] = benchJson.success ? benchJson.klines : []

        // 以第一根 K 线的收盘价作为基准（持仓成本）
        const baseCost = costPrice > 0 ? costPrice : klines[0].close

        // 构建基准 map
        const benchMap: Record<string, number> = {}
        if (benchKlines.length > 0) {
          const benchBase = benchKlines[0].close
          benchKlines.forEach((b: any) => {
            const shortDate = b.date.slice(5) // MM-DD
            benchMap[shortDate] = +((b.close / benchBase - 1) * 100).toFixed(2)
          })
        }

        const points: PnLPoint[] = klines.map((k: any) => {
          const shortDate = k.date.slice(5)
          const pnl = +((k.close / baseCost - 1) * 100).toFixed(2)
          const benchmark = benchMap[shortDate] ?? 0
          return { date: shortDate, pnl, benchmark }
        })

        setData(points)
      }
    } catch (e) {
      console.error('PnLChart fetch error', e)
    } finally {
      setLoading(false)
    }
  }

  // 外部 code 变化时同步
  useEffect(() => {
    const code = externalCode || '600183'
    setActiveCode(code)
  }, [externalCode])

  useEffect(() => {
    if (activeCode && cost !== undefined) {
      fetchPnL(activeCode, cost)
    }
  }, [activeCode, cost])

  const displayData = data.slice(-30)
  const lastPoint = displayData[displayData.length - 1]
  const totalReturn = lastPoint?.pnl ?? 0
  const benchReturn = lastPoint?.benchmark ?? 0
  const alpha = +(totalReturn - benchReturn).toFixed(2)

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <TrendingUp className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">
            盈亏曲线
            <span className="text-sm text-gray-500 font-normal ml-2">{name}</span>
          </h2>
        </div>
        <div className="flex space-x-4 text-xs">
          <div>
            <span className="text-gray-500">持仓收益 </span>
            <span className={`font-mono font-bold ${totalReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </span>
          </div>
          <div>
            <span className="text-gray-500">Alpha </span>
            <span className={`font-mono font-bold ${alpha >= 0 ? 'text-cyan-400' : 'text-green-400'}`}>
              {alpha >= 0 ? '+' : ''}{alpha.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      <div className="h-[260px]">
        {loading ? (
          <div className="h-full flex items-center justify-center text-gray-500">加载中...</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={displayData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="benchGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#6b7280" stopOpacity={0.1} />
                  <stop offset="95%" stopColor="#6b7280" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={{ stroke: '#374151' }}
                tickFormatter={v => v.slice(3)} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={{ stroke: '#374151' }}
                tickFormatter={v => `${v}%`} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 12 }}
                formatter={(value: number, name: string) => [
                  `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`,
                  name === 'pnl' ? '持仓收益' : '沪深300'
                ]}
              />
              <Area type="monotone" dataKey="benchmark" stroke="#6b7280" strokeWidth={1}
                strokeDasharray="4 4" fill="url(#benchGradient)" />
              <Area type="monotone" dataKey="pnl" stroke="#06b6d4" strokeWidth={2}
                fill="url(#pnlGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex items-center justify-center space-x-6 mt-2 text-xs">
        <span className="flex items-center space-x-1">
          <span className="w-3 h-0.5 bg-cyan-500 inline-block" />
          <span className="text-gray-500">持仓收益</span>
        </span>
        <span className="flex items-center space-x-1">
          <span className="w-3 h-0.5 bg-gray-500 inline-block" />
          <span className="text-gray-500">沪深300</span>
        </span>
      </div>
    </div>
  )
}
