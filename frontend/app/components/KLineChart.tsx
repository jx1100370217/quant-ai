'use client'

import { useState, useEffect } from 'react'
import { BarChart3 } from 'lucide-react'
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts'

interface KlineData {
  date: string; open: number; close: number; high: number; low: number; volume: number; change: number
  ma5?: number; ma10?: number; ma20?: number
}

interface Props {
  stockCode?: string
  stockName?: string
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload
  const isUp = d.close >= d.open
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs font-mono">
      <div className="text-gray-400 mb-1">{label}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-gray-500">开盘</span><span>{d.open}</span>
        <span className="text-gray-500">收盘</span><span className={isUp ? 'text-red-400' : 'text-green-400'}>{d.close}</span>
        <span className="text-gray-500">最高</span><span>{d.high}</span>
        <span className="text-gray-500">最低</span><span>{d.low}</span>
      </div>
    </div>
  )
}

export default function KLineChart({ stockCode: externalCode, stockName: externalName }: Props) {
  const [data, setData] = useState<KlineData[]>([])
  const [stockName, setStockName] = useState(externalName || '加载中...')
  const [stockCode, setStockCode] = useState(externalCode || '000852')
  const [period, setPeriod] = useState('101')
  const [loading, setLoading] = useState(true)

  const periodMap: Record<string, string> = { '日K': '101', '周K': '102', '月K': '103', '60分': '60' }

  const fetchKline = async (code: string, klt: string) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/kline?code=${code}&klt=${klt}&lmt=60`)
      const json = await res.json()
      if (json.success && json.klines) {
        const klines = json.klines as KlineData[]
        for (let i = 0; i < klines.length; i++) {
          if (i >= 4)  klines[i].ma5  = +(klines.slice(i-4, i+1).reduce((s,d) => s+d.close, 0)/5).toFixed(2)
          if (i >= 9)  klines[i].ma10 = +(klines.slice(i-9, i+1).reduce((s,d) => s+d.close, 0)/10).toFixed(2)
          if (i >= 19) klines[i].ma20 = +(klines.slice(i-19, i+1).reduce((s,d) => s+d.close, 0)/20).toFixed(2)
        }
        setData(klines)
        if (json.name) setStockName(json.name)
      }
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  // 外部 code/name 变化时同步（含名字）
  useEffect(() => {
    if (externalCode && externalCode !== stockCode) {
      setStockCode(externalCode)
      setStockName(externalName || '加载中...')
    } else if (externalName && externalName !== stockName) {
      setStockName(externalName)
    }
  }, [externalCode, externalName])

  useEffect(() => {
    fetchKline(stockCode, period)
  }, [stockCode, period])

  const displayData = data.slice(-30)

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <BarChart3 className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">{stockName} <span className="text-sm text-gray-500 font-mono">{stockCode}</span></h2>
        </div>
        <div className="flex space-x-1 text-xs">
          {Object.entries(periodMap).map(([label, klt]) => (
            <button key={klt} onClick={() => setPeriod(klt)}
              className={`px-2 py-1 rounded ${period === klt ? 'bg-cyan-900/50 text-cyan-400' : 'text-gray-500 hover:text-gray-300'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[300px]">
        {loading ? (
          <div className="h-full flex items-center justify-center text-gray-500">加载中...</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={displayData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={{ stroke: '#374151' }}
                tickFormatter={(v) => v.length > 5 ? v.slice(5) : v} />
              <YAxis domain={['auto', 'auto']} tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={{ stroke: '#374151' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="close" barSize={6}>
                {displayData.map((entry, index) => (
                  <Cell key={index} fill={entry.close >= entry.open ? '#ef4444' : '#10b981'} fillOpacity={0.8} />
                ))}
              </Bar>
              <Line type="monotone" dataKey="ma5"  stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
              <Line type="monotone" dataKey="ma10" stroke="#3b82f6" dot={false} strokeWidth={1.5} connectNulls />
              <Line type="monotone" dataKey="ma20" stroke="#a855f7" dot={false} strokeWidth={1.5} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex items-center justify-center space-x-6 mt-2 text-xs">
        <span className="flex items-center space-x-1"><span className="w-3 h-0.5 bg-yellow-500 inline-block" /><span className="text-gray-500">MA5</span></span>
        <span className="flex items-center space-x-1"><span className="w-3 h-0.5 bg-blue-500 inline-block" /><span className="text-gray-500">MA10</span></span>
        <span className="flex items-center space-x-1"><span className="w-3 h-0.5 bg-purple-500 inline-block" /><span className="text-gray-500">MA20</span></span>
      </div>
    </div>
  )
}
