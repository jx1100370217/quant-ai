'use client'

import { useEffect, useState } from 'react'
import { Shield, AlertTriangle } from 'lucide-react'

const riskMetrics = [
  { label: '最大回撤', value: -4.2, limit: -8, unit: '%' },
  { label: '夏普比率', value: 1.85, limit: 1.0, unit: '' },
  { label: '仓位水平', value: 82, limit: 90, unit: '%' },
  { label: '集中度', value: 12.7, limit: 15, unit: '%' },
  { label: '波动率', value: 18.5, limit: 25, unit: '%' },
]

export default function RiskGauge() {
  const [riskScore, setRiskScore] = useState(0)
  const targetScore = 35 // 0-100, 越高越危险

  useEffect(() => {
    const timer = setTimeout(() => setRiskScore(targetScore), 500)
    return () => clearTimeout(timer)
  }, [])

  // 风险等级
  const riskLevel = riskScore < 30 ? '低风险' : riskScore < 60 ? '中等风险' : '高风险'
  const riskColor = riskScore < 30 ? 'text-green-400' : riskScore < 60 ? 'text-yellow-400' : 'text-red-400'
  const gaugeColor = riskScore < 30 ? '#10b981' : riskScore < 60 ? '#f59e0b' : '#ef4444'

  // SVG半圆仪表盘
  const radius = 70
  const circumference = Math.PI * radius
  const strokeDashoffset = circumference - (riskScore / 100) * circumference

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center space-x-2 mb-4">
        <Shield className="w-5 h-5 text-neon-cyan" />
        <h2 className="text-lg font-semibold">风险评估</h2>
      </div>

      {/* 半圆仪表盘 */}
      <div className="flex justify-center mb-4">
        <div className="relative">
          <svg width="180" height="100" viewBox="0 0 180 100">
            {/* 背景弧 */}
            <path d="M 10 90 A 70 70 0 0 1 170 90" fill="none" stroke="#1f2937" strokeWidth="12" strokeLinecap="round" />
            {/* 绿色段 */}
            <path d="M 10 90 A 70 70 0 0 1 58 25" fill="none" stroke="#10b981" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            {/* 黄色段 */}
            <path d="M 58 25 A 70 70 0 0 1 122 25" fill="none" stroke="#f59e0b" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            {/* 红色段 */}
            <path d="M 122 25 A 70 70 0 0 1 170 90" fill="none" stroke="#ef4444" strokeWidth="12" strokeLinecap="round" opacity="0.3" />
            {/* 指针 */}
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
      <div className="space-y-2">
        {riskMetrics.map((m, i) => {
          const isGood = m.label === '最大回撤' ? m.value > m.limit :
                        m.label === '夏普比率' ? m.value > m.limit :
                        m.value < m.limit
          return (
            <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-gray-900/30">
              <span className="text-gray-400">{m.label}</span>
              <div className="flex items-center space-x-2">
                <span className={`font-mono font-bold ${isGood ? 'text-green-400' : 'text-yellow-400'}`}>
                  {m.value}{m.unit}
                </span>
                <span className="text-gray-600">/ {m.limit}{m.unit}</span>
                {!isGood && <AlertTriangle className="w-3 h-3 text-yellow-500" />}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
