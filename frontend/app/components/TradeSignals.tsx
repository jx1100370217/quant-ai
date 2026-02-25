'use client'

import { Signal, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'

export interface TradeSignal {
  time: string
  stock: string
  code: string
  action: 'buy' | 'sell' | 'hold'
  reason: string
  confidence: number
}

interface TradeSignalsProps {
  signals: TradeSignal[]
}

const actionConfig = {
  buy: { label: '买入', icon: ArrowUpRight, color: 'text-red-400', bg: 'bg-red-900/20', dot: 'bg-red-400' },
  sell: { label: '卖出', icon: ArrowDownRight, color: 'text-green-400', bg: 'bg-green-900/20', dot: 'bg-green-400' },
  hold: { label: '持有', icon: Minus, color: 'text-yellow-400', bg: 'bg-yellow-900/20', dot: 'bg-yellow-400' },
}

export default function TradeSignals({ signals }: TradeSignalsProps) {
  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Signal className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">交易信号</h2>
        </div>
        <span className="text-xs text-gray-500">今日 {signals.length} 条信号</span>
      </div>

      {signals.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-gray-600 text-sm">
          暂无信号，点击「重新分析」生成
        </div>
      ) : (
        <div className="relative">
          {/* 时间轴竖线 */}
          <div className="absolute left-[52px] top-0 bottom-0 w-px bg-gray-800" />

          <div className="space-y-3">
            {signals.map((sig, idx) => {
              const cfg = actionConfig[sig.action]
              const Icon = cfg.icon
              return (
                <div key={idx} className={`flex items-start space-x-4 p-3 rounded-lg ${cfg.bg} hover:bg-opacity-40 transition-colors`}>
                  <div className="w-10 text-xs font-mono text-gray-500 pt-0.5 text-right shrink-0">{sig.time}</div>
                  <div className="relative shrink-0">
                    <div className={`w-3 h-3 rounded-full ${cfg.dot} ring-2 ring-gray-900`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-sm">{sig.stock}</span>
                        <span className="text-xs text-gray-500 font-mono">{sig.code}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${cfg.color} ${cfg.bg} border border-current/20 flex items-center space-x-1`}>
                          <Icon className="w-3 h-3" />
                          <span>{cfg.label}</span>
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 font-mono">置信度 {sig.confidence}%</div>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">{sig.reason}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
