'use client'

import { useEffect, useState } from 'react'
import { Shield, AlertTriangle } from 'lucide-react'

interface PortfolioSummary {
  cash: number
  totalAssets: number
  totalMarketValue: number
  totalPnl: number
  todayPnl: number
  positions: Array<{ code: string; name: string; cost: number; shares: number }>
}

interface Props {
  portfolio?: PortfolioSummary | null
}

export default function RiskGauge({ portfolio }: Props) {
  const [riskScore, setRiskScore] = useState(0)

  // 从真实持仓计算风险指标
  const calcMetrics = () => {
    if (!portfolio || portfolio.totalAssets <= 0) {
      // 无数据时返回默认值
      return [
        { label: '最大回撤', value: 0, limit: -8, unit: '%', isGood: true },
        { label: '仓位水平', value: 0, limit: 90, unit: '%', isGood: true },
        { label: '集中度', value: 0, limit: 20, unit: '%', isGood: true },
        { label: '波动率', value: 0, limit: 25, unit: '%', isGood: true },
        { label: '止损警戒', value: 0, limit: -8, unit: '%', isGood: true },
      ]
    }

    const { totalAssets, totalMarketValue, totalPnl, positions } = portfolio

    // 仓位水平 = 持仓市值 / 总资产
    const positionRatio = (totalMarketValue / totalAssets) * 100

    // 集中度 = 最大单只持仓市值 / 总资产（持仓数越少越集中）
    const maxPositionValue = positions.length > 0
      ? Math.max(...positions.map(p => p.shares * p.cost))
      : 0
    const concentration = (maxPositionValue / totalAssets) * 100

    // 当前亏损率（以成本价计算）
    const totalCost = positions.reduce((s, p) => s + p.shares * p.cost, 0)
    const currentPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0

    // 止损警戒（距8%止损线还剩多少）
    const stopLossWarning = currentPnlPct  // 负数 = 亏损

    // 简化的风险分：以仓位+集中度+亏损综合估算
    let score = 20 // 基础分
    if (positionRatio > 85) score += 20
    else if (positionRatio > 70) score += 10
    if (concentration > 50) score += 25
    else if (concentration > 30) score += 10
    if (currentPnlPct < -5) score += 20
    else if (currentPnlPct < -3) score += 10

    return {
      score: Math.min(score, 100),
      metrics: [
        {
          label: '持仓盈亏',
          value: +currentPnlPct.toFixed(1),
          limit: -8,
          unit: '%',
          isGood: currentPnlPct >= -5,
        },
        {
          label: '仓位水平',
          value: +positionRatio.toFixed(1),
          limit: 90,
          unit: '%',
          isGood: positionRatio < 90,
        },
        {
          label: '持仓集中度',
          value: +concentration.toFixed(1),
          limit: 50,
          unit: '%',
          isGood: concentration < 50,
        },
        {
          label: '止损警戒',
          value: +currentPnlPct.toFixed(1),
          limit: -8,
          unit: '%',
          isGood: currentPnlPct > -8,
        },
        {
          label: '持仓标的数',
          value: positions.length,
          limit: 1,
          unit: '只',
          isGood: positions.length >= 3,
          note: positions.length < 3 ? '建议分散' : '已分散',
        },
      ],
    }
  }

  const result = calcMetrics()
  const targetScore = typeof result === 'number' ? result : (result as any).score ?? 35
  const riskMetrics = typeof result === 'object' && (result as any).metrics ? (result as any).metrics : []

  useEffect(() => {
    const timer = setTimeout(() => setRiskScore(targetScore), 500)
    return () => clearTimeout(timer)
  }, [targetScore])

  const riskLevel = riskScore < 30 ? '低风险' : riskScore < 60 ? '中等风险' : '高风险'
  const riskColor = riskScore < 30 ? 'text-green-400' : riskScore < 60 ? 'text-yellow-400' : 'text-red-400'
  const gaugeColor = riskScore < 30 ? '#10b981' : riskScore < 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center space-x-2 mb-4">
        <Shield className="w-5 h-5 text-neon-cyan" />
        <h2 className="text-lg font-semibold">风险评估</h2>
        {portfolio && <span className="text-xs text-gray-500 ml-1">实时计算</span>}
      </div>

      {/* 半圆仪表盘 */}
      <div className="flex justify-center mb-4">
        <div className="relative">
          <svg width="180" height="100" viewBox="0 0 180 100">
            <path d="M 10 90 A 70 70 0 0 1 170 90" fill="none" stroke="#1f2937" strokeWidth="12" strokeLinecap="round" />
            <path d="M 10 90 A 70 70 0 0 1 58 25" fill="none" stroke="#10b981" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            <path d="M 58 25 A 70 70 0 0 1 122 25" fill="none" stroke="#f59e0b" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            <path d="M 122 25 A 70 70 0 0 1 170 90" fill="none" stroke="#ef4444" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            <line
              x1="90" y1="90"
              x2={90 + 55 * Math.cos(Math.PI * (1 - riskScore / 100))}
              y2={90 - 55 * Math.sin(Math.PI * (1 - riskScore / 100))}
              stroke={gaugeColor} strokeWidth="2" strokeLinecap="round"
              className="transition-all duration-1000"
            />
            <circle cx="90" cy="90" r="4" fill={gaugeColor} />
          </svg>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
            <div className={`text-2xl font-bold font-mono ${riskColor}`}>{riskScore}</div>
            <div className={`text-xs ${riskColor}`}>{riskLevel}</div>
          </div>
        </div>
      </div>

      {/* 风险指标列表 */}
      {!portfolio ? (
        <div className="text-center text-gray-600 text-xs py-2">等待持仓数据...</div>
      ) : (
        <div className="space-y-2">
          {riskMetrics.map((m: any, i: number) => (
            <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-gray-900/30">
              <span className="text-gray-400">{m.label}</span>
              <div className="flex items-center space-x-2">
                <span className={`font-mono font-bold ${m.isGood ? 'text-green-400' : 'text-yellow-400'}`}>
                  {m.value >= 0 && m.unit !== '只' ? (m.value > 0 && m.label === '持仓盈亏' ? '+' : '') : ''}{m.value}{m.unit}
                </span>
                {m.note && <span className="text-gray-600 text-xs">{m.note}</span>}
                {!m.note && <span className="text-gray-600">/ {m.limit}{m.unit}</span>}
                {!m.isGood && <AlertTriangle className="w-3 h-3 text-yellow-500" />}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
