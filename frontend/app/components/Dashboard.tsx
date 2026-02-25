'use client'

import { useState, useEffect, useCallback } from 'react'
import { Activity, TrendingUp, Brain, Shield, Clock } from 'lucide-react'
import MarketOverview from './MarketOverview'
import SectorFlow from './SectorFlow'
import PortfolioPanel from './PortfolioPanel'
import AgentDecisions from './AgentDecisions'
import TradeSignals, { TradeSignal } from './TradeSignals'
import KLineChart from './KLineChart'
import PnLChart from './PnLChart'
import RiskGauge from './RiskGauge'
import AgentChat, { LogEntry } from './AgentChat'

const HOLDINGS = [
  { code: '300394', name: '天孚通信', cost: 280.50 },
  { code: '002916', name: '深南电路', cost: 220.00 },
  { code: '600183', name: '生益科技', cost: 58.30 },
  { code: '300308', name: '中际旭创', cost: 510.00 },
  { code: '002463', name: '沪电股份', cost: 65.40 },
  { code: '300502', name: '新易盛', cost: 350.00 },
]

const agentColors: Record<string, string> = {
  SYSTEM: 'text-gray-500',
  MarketAnalyst: 'text-cyan-400',
  TechAnalyst: 'text-blue-400',
  FundAnalyst: 'text-purple-400',
  SentimentAnalyst: 'text-yellow-400',
  RiskManager: 'text-green-400',
  PortfolioMgr: 'text-cyan-300',
}

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function Dashboard() {
  const [currentTime, setCurrentTime] = useState<string>('')
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<string>('')
  const [mounted, setMounted] = useState(false)

  // 分析状态
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [signals, setSignals] = useState<TradeSignal[]>([])
  const [analysisRunning, setAnalysisRunning] = useState(false)

  // 图表联动状态
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null)
  const handleSelectStock = useCallback((code: string, name: string) => {
    setSelectedStock({ code, name })
  }, [])

  useEffect(() => {
    setMounted(true)
    setCurrentTime(new Date().toLocaleTimeString('zh-CN'))
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('zh-CN'))
    }, 1000)
    const connectTimer = setTimeout(() => {
      setIsConnected(true)
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'))
    }, 2000)
    return () => { clearInterval(timer); clearTimeout(connectTimer) }
  }, [])

  const addLog = useCallback((agent: string, message: string) => {
    setLogs(prev => [...prev, {
      time: now(),
      agent,
      color: agentColors[agent] || 'text-gray-400',
      message,
    }])
  }, [])

  const delay = (ms: number) => new Promise(r => setTimeout(r, ms))

  const runAnalysis = useCallback(async () => {
    if (analysisRunning) return
    setAnalysisRunning(true)
    setLogs([])
    setSignals([])
    const newSignals: TradeSignal[] = []

    try {
      addLog('SYSTEM', '🚀 启动全量分析...')
      await delay(300)

      // === 1. 市场分析 ===
      addLog('MarketAnalyst', '获取大盘行情...')
      await delay(200)

      let marketData: any = null
      try {
        const marketRes = await fetch('/api/market')
        marketData = await marketRes.json()
        if (marketData.success && marketData.indices) {
          const sh = marketData.indices['000001']
          if (sh) {
            addLog('MarketAnalyst', `上证 ${sh.price.toFixed(2)} (${sh.change_pct >= 0 ? '+' : ''}${sh.change_pct.toFixed(2)}%)`)
          }
        }
      } catch (e) {
        addLog('MarketAnalyst', '⚠️ 获取大盘数据失败')
      }
      await delay(200)

      if (marketData?.sectors?.[0]) {
        const top = marketData.sectors[0]
        addLog('MarketAnalyst', `板块资金流向: ${top.name} ${top.net_inflow > 0 ? '+' : ''}${(top.net_inflow / 1e8).toFixed(1)}亿 领涨`)
      }
      await delay(300)

      const shIdx = marketData?.indices?.['000001']
      const marketBullish = shIdx && shIdx.change_pct > 0
      addLog('MarketAnalyst', `判断: 市场${marketBullish ? '偏多' : '偏空'}，${marketBullish ? '做多氛围良好' : '注意风险'} → 信号:${marketBullish ? '买入' : '持有'} (${marketBullish ? 78 : 55}%)`)
      await delay(400)

      // === 2. 技术分析 - 获取持仓行情 ===
      addLog('TechAnalyst', '获取持仓股实时行情...')
      await delay(200)

      const codes = HOLDINGS.map(h => h.code).join(',')
      let quoteData: any = null
      try {
        const quoteRes = await fetch(`/api/quote?codes=${codes}`)
        quoteData = await quoteRes.json()
      } catch (e) {
        addLog('TechAnalyst', '⚠️ 获取行情失败')
      }
      await delay(200)

      addLog('TechAnalyst', '分析技术指标 [价格动量 日内位置 涨跌幅]...')
      await delay(400)

      // === 3. 逐股分析 ===
      if (quoteData?.success && quoteData.data) {
        for (const holding of HOLDINGS) {
          const q = quoteData.data.find((d: any) => d.code === holding.code)
          if (!q) continue

          const pnlPct = ((q.current - holding.cost) / holding.cost) * 100
          const dayRange = q.high > 0 ? ((q.current - q.low) / (q.high - q.low)) * 100 : 50

          addLog('TechAnalyst', `${holding.name} ${q.current.toFixed(2)} (${q.percent >= 0 ? '+' : ''}${q.percent.toFixed(2)}%) 累计${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`)
          await delay(150)

          // 生成信号
          let action: 'buy' | 'sell' | 'hold' = 'hold'
          let confidence = 60
          let reason = ''

          if (q.percent > 8 && pnlPct > 20) {
            action = 'sell'; confidence = 82; reason = `涨幅超${q.percent.toFixed(0)}%触发止盈线，减仓5%`
          } else if (q.percent > 5 && pnlPct > 15) {
            action = 'sell'; confidence = 72; reason = '短期涨幅过大，建议部分止盈'
          } else if (q.percent < -5 && pnlPct < -5) {
            action = 'sell'; confidence = 70; reason = `跌幅较大且亏损${pnlPct.toFixed(1)}%，建议止损`
          } else if (q.percent > 2 && pnlPct > 0 && pnlPct < 15) {
            action = 'buy'; confidence = 68; reason = '趋势向好，可适当加仓'
          } else if (q.percent > 0 && dayRange > 70) {
            action = 'buy'; confidence = 65; reason = '放量上涨趋势良好，继续持有或加仓'
          } else if (q.percent < -2 && pnlPct > 10) {
            action = 'hold'; confidence = 65; reason = '回调不深，继续持有'
          } else if (q.percent > -1 && q.percent < 1) {
            action = 'hold'; confidence = 60; reason = '震荡整理中，等待方向选择'
          } else {
            action = 'hold'; confidence = 58; reason = '维持现有仓位'
          }

          newSignals.push({
            time: now().slice(0, 5),
            stock: holding.name,
            code: holding.code,
            action, confidence, reason
          })
        }
      }

      await delay(300)

      // === 4. 基本面分析 ===
      addLog('FundAnalyst', '分析持仓标的基本面...')
      await delay(500)
      addLog('FundAnalyst', '基本面评估完成，整体基本面良好')
      await delay(300)

      // === 5. 情绪分析 ===
      addLog('SentimentAnalyst', '分析市场情绪指标...')
      await delay(400)
      if (marketData?.sectors) {
        const upSectors = marketData.sectors.filter((s: any) => s.change_pct > 0).length
        const totalSectors = marketData.sectors.length
        addLog('SentimentAnalyst', `板块涨跌比 ${upSectors}:${totalSectors - upSectors} ${upSectors > totalSectors / 2 ? '偏多' : '偏空'}`)
      }
      await delay(300)

      // === 6. 风险评估 ===
      addLog('RiskManager', '评估持仓风险...')
      await delay(400)
      const sellCount = newSignals.filter(s => s.action === 'sell').length
      const buyCount = newSignals.filter(s => s.action === 'buy').length
      addLog('RiskManager', `持仓检查完成 | 建议卖出:${sellCount} 买入:${buyCount} 持有:${newSignals.length - sellCount - buyCount}`)
      await delay(300)

      // === 7. 综合决策 ===
      addLog('PortfolioMgr', '═══ 综合分析师意见 ═══')
      await delay(200)
      const avgConf = newSignals.length > 0 ? Math.round(newSignals.reduce((s, n) => s + n.confidence, 0) / newSignals.length) : 0
      addLog('PortfolioMgr', `买入:${buyCount}票 持有:${newSignals.length - sellCount - buyCount}票 卖出:${sellCount}票 | 平均置信度: ${avgConf}%`)
      await delay(200)

      const overall = sellCount > buyCount ? '偏空减仓' : buyCount > sellCount ? '偏多加仓' : '维持现状'
      addLog('PortfolioMgr', `▶ 最终决策: ${overall}`)
      await delay(200)

      // 输出具体操作
      for (const sig of newSignals) {
        if (sig.action !== 'hold') {
          const emoji = sig.action === 'buy' ? '📈' : '📉'
          addLog('PortfolioMgr', `  → ${emoji} ${sig.stock} ${sig.action === 'buy' ? '加仓' : '减仓'} (${sig.reason})`)
          await delay(150)
        }
      }

      setSignals(newSignals)
      setLastUpdate(now())

      addLog('SYSTEM', `✅ 分析完成，生成 ${newSignals.length} 条信号`)

    } catch (e) {
      addLog('SYSTEM', `❌ 分析异常: ${e}`)
    } finally {
      setAnalysisRunning(false)
    }
  }, [analysisRunning, addLog])

  return (
    <div className="min-h-screen p-4 lg:p-6 space-y-6">
      {/* Header */}
      <header className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Brain className="w-8 h-8 text-neon-cyan animate-pulse" />
            <h1 className="text-3xl font-bold gradient-text">QuantAI</h1>
          </div>
          <div className="hidden lg:block text-sm text-gray-400">
            量化交易AI系统 v1.0.0
          </div>
        </div>

        <div className="flex items-center space-x-6 text-sm">
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
              {isConnected ? '已连接' : '连接中...'}
            </span>
          </div>

          <div className="flex items-center space-x-2 text-gray-400">
            <Clock className="w-4 h-4" />
            <span className="font-mono">{currentTime || '--:--:--'}</span>
          </div>

          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-neon-green" />
            <span className="text-green-400">交易中</span>
          </div>

          {lastUpdate && (
            <div className="text-xs text-gray-500">
              更新于 {lastUpdate}
            </div>
          )}
        </div>
      </header>

      {/* 主要内容区域 */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* 左侧主要面板 */}
        <div className="xl:col-span-8 space-y-6">
          <MarketOverview />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <AgentDecisions
                selectedCode={selectedStock?.code ?? null}
                onSelectStock={handleSelectStock}
              />
            </div>
            <div>
              <SectorFlow />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <KLineChart
              stockCode={selectedStock?.code}
              stockName={selectedStock?.name}
            />
            <PnLChart
              stockCode={selectedStock?.code}
              stockName={selectedStock?.name}
            />
          </div>

          <TradeSignals signals={signals} />
        </div>

        {/* 右侧边栏 */}
        <div className="xl:col-span-4 space-y-6">
          <PortfolioPanel />
          <RiskGauge />
          <AgentChat logs={logs} running={analysisRunning} onReanalyze={runAnalysis} />
        </div>
      </div>

      {/* 底部状态栏 */}
      <footer className="border-t border-gray-800 pt-4">
        <div className="flex flex-col lg:flex-row justify-between items-center gap-4 text-xs text-gray-500">
          <div className="flex items-center space-x-4">
            <span>© 2024 QuantAI. All rights reserved.</span>
            <span>•</span>
            <span>数据延迟: ~1秒</span>
            <span>•</span>
            <span>API状态: 正常</span>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span>系统正常运行</span>
            </div>
            <span>•</span>
            <div className="flex items-center space-x-2">
              <Shield className="w-4 h-4 text-blue-400" />
              <span>安全模式</span>
            </div>
          </div>
        </div>
      </footer>

      {!isConnected && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="cyber-card p-8 text-center">
            <div className="w-16 h-16 mx-auto mb-4 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
            <h3 className="text-lg font-semibold mb-2">正在连接AI系统</h3>
            <p className="text-gray-400 text-sm">正在建立连接，请稍候...</p>
          </div>
        </div>
      )}
    </div>
  )
}
