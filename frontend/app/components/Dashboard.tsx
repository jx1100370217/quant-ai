'use client'

import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowDown,
  ArrowRight,
  BrainCircuit,
  Clock3,
  Database,
  Radar,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react'
import MarketOverview from './MarketOverview'
import SectorFlow from './SectorFlow'
import StrategyTelemetry from './StrategyTelemetry'
import WeeklyAdvisor from './WeeklyAdvisor'

const PIPELINE = [
  { index: '01', title: '全域扫描', detail: 'A股股票池', icon: Database },
  { index: '02', title: '反转过滤', detail: '价格 · 量能', icon: ScanSearch },
  { index: '03', title: '风险定标', detail: '纪律优先', icon: ShieldCheck },
  { index: '04', title: '组合输出', detail: '现金感知', icon: Target },
]

function SignalCore() {
  return (
    <div className="relative mx-auto flex h-[300px] w-full max-w-[440px] items-center justify-center lg:h-[340px]">
      <div className="signal-orbit signal-orbit-outer" />
      <div className="signal-orbit signal-orbit-middle" />
      <div className="signal-orbit signal-orbit-inner" />
      <div className="absolute inset-0 radar-sweep" />

      <div className="relative z-10 flex h-32 w-32 flex-col items-center justify-center rounded-full border border-cyan-300/30 bg-[#071621]/90 shadow-[0_0_60px_rgba(34,211,238,0.18)]">
        <BrainCircuit className="mb-2 h-7 w-7 text-cyan-300" />
        <span className="font-mono text-[10px] tracking-[0.28em] text-cyan-500">QUANT CORE</span>
        <span className="mt-1 font-mono text-xl font-semibold text-white">V14</span>
      </div>

      <div className="absolute left-[3%] top-[16%] signal-node">
        <Database className="h-3.5 w-3.5" /> DATA
      </div>
      <div className="absolute right-[1%] top-[32%] signal-node">
        <Radar className="h-3.5 w-3.5" /> FACTOR
      </div>
      <div className="absolute bottom-[15%] left-[13%] signal-node">
        <ShieldCheck className="h-3.5 w-3.5" /> RISK
      </div>
      <div className="absolute bottom-[7%] right-[13%] signal-node">
        <Zap className="h-3.5 w-3.5" /> SIGNAL
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [currentTime, setCurrentTime] = useState('--:--:--')
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const updateClock = () => setCurrentTime(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
    updateClock()
    const clockTimer = window.setInterval(updateClock, 1000)
    const connectionTimer = window.setTimeout(() => setConnected(true), 500)
    return () => {
      window.clearInterval(clockTimer)
      window.clearTimeout(connectionTimer)
    }
  }, [])

  const scrollToSignals = () => {
    document.getElementById('weekly-signals')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="quant-shell min-h-screen">
      <div className="scanline-layer" aria-hidden="true" />

      <div className="relative z-10 mx-auto w-full max-w-[1680px] px-4 pb-8 pt-3 sm:px-6 lg:px-8">
        <header className="command-header mb-5 flex min-h-16 items-center justify-between gap-4 px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="brand-mark">
              <BrainCircuit className="h-5 w-5 text-cyan-200" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold tracking-tight text-white sm:text-xl">QuantAI</h1>
                <span className="hidden rounded border border-cyan-500/20 bg-cyan-500/5 px-1.5 py-0.5 font-mono text-[9px] tracking-[0.18em] text-cyan-400 sm:inline">WEEKLY ALPHA LAB</span>
              </div>
              <p className="truncate text-[10px] tracking-[0.18em] text-slate-600">REVERSAL SIGNAL INTELLIGENCE</p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-slate-800 bg-slate-950/50 px-3 py-1.5 text-[10px] text-slate-400 md:flex">
              <Activity className="h-3.5 w-3.5 text-cyan-400" />
              <span>策略引擎</span>
              <span className="text-white">V14</span>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-emerald-500/15 bg-emerald-500/5 px-3 py-1.5 text-[10px] text-emerald-300">
              <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-emerald-400 shadow-[0_0_10px_#34d399]' : 'bg-amber-400 animate-pulse'}`} />
              <span className="hidden sm:inline">{connected ? 'DATA ONLINE' : 'CONNECTING'}</span>
              <span className="sm:hidden">LIVE</span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] text-slate-400">
              <Clock3 className="h-3.5 w-3.5 text-slate-600" />
              <span>{currentTime}</span>
            </div>
          </div>
        </header>

        <main className="space-y-5">
          <section className="hero-grid relative overflow-hidden rounded-[28px] border border-cyan-500/15 bg-[#050b12]/90">
            <div className="hero-glow" aria-hidden="true" />
            <div className="grid min-h-[440px] grid-cols-1 items-center lg:grid-cols-[1.15fr_0.85fr]">
              <div className="relative z-10 px-6 py-10 sm:px-10 lg:px-14 lg:py-14">
                <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-3 py-1.5 font-mono text-[10px] tracking-[0.2em] text-cyan-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  SYSTEMATIC REVERSAL · WEEKLY SIGNAL
                </div>

                <h2 className="max-w-4xl text-balance text-4xl font-semibold leading-[1.08] tracking-[-0.04em] text-white sm:text-5xl lg:text-6xl">
                  从全市场噪声中
                  <span className="block bg-gradient-to-r from-cyan-300 via-sky-400 to-indigo-400 bg-clip-text text-transparent">提取可执行的反转信号</span>
                </h2>
                <p className="mt-6 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
                  面向周频决策的量化研究终端。以价格反转、量能确认和刚性风险边界，输出透明、可复核的候选组合。
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-3">
                  <button onClick={scrollToSignals} className="group inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-white hover:shadow-[0_0_32px_rgba(103,232,249,0.35)]">
                    查看本周信号
                    <ArrowDown className="h-4 w-4 transition-transform group-hover:translate-y-0.5" />
                  </button>
                  <div className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-4 py-3 font-mono text-[11px] text-slate-500">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                    研究模式 · 非自动交易
                  </div>
                </div>

                <div className="mt-10 grid max-w-2xl grid-cols-3 border-t border-slate-800/70 pt-5">
                  <div>
                    <div className="font-mono text-xl font-semibold text-white sm:text-2xl">5,500+</div>
                    <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-600">Universe</div>
                  </div>
                  <div className="border-l border-slate-800/70 pl-5">
                    <div className="font-mono text-xl font-semibold text-white sm:text-2xl">W1</div>
                    <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-600">Horizon</div>
                  </div>
                  <div className="border-l border-slate-800/70 pl-5">
                    <div className="font-mono text-xl font-semibold text-cyan-300 sm:text-2xl">≤ 5</div>
                    <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-600">Signals</div>
                  </div>
                </div>
              </div>

              <div className="relative hidden h-full min-h-[420px] items-center border-l border-cyan-500/10 bg-cyan-400/[0.015] px-8 lg:flex">
                <SignalCore />
              </div>
            </div>
          </section>

          <section aria-label="策略流程" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {PIPELINE.map((step, i) => {
              const Icon = step.icon
              return (
                <div key={step.index} className="pipeline-card group relative overflow-hidden">
                  <span className="absolute right-3 top-2 font-mono text-3xl font-semibold text-white/[0.025]">{step.index}</span>
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-400/15 bg-cyan-400/[0.06] text-cyan-400 transition group-hover:border-cyan-300/30 group-hover:text-cyan-200">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-200">{step.title}</div>
                      <div className="mt-0.5 font-mono text-[10px] tracking-wider text-slate-600">{step.detail}</div>
                    </div>
                    {i < PIPELINE.length - 1 && <ArrowRight className="ml-auto hidden h-3.5 w-3.5 text-slate-800 lg:block" />}
                  </div>
                </div>
              )
            })}
          </section>

          <section className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="xl:col-span-8">
              <MarketOverview />
            </div>
            <div className="xl:col-span-4">
              <StrategyTelemetry />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="xl:col-span-7">
              <SectorFlow />
            </div>
            <div className="quant-panel relative overflow-hidden p-6 xl:col-span-5">
              <div className="panel-corner panel-corner-tr" />
              <div className="mb-6 flex items-start justify-between gap-4">
                <div>
                  <div className="panel-kicker">EXECUTION PROTOCOL</div>
                  <h3 className="mt-2 text-xl font-semibold text-white">策略纪律矩阵</h3>
                </div>
                <ShieldCheck className="h-5 w-5 text-indigo-400" />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="discipline-tile border-red-400/15 bg-red-400/[0.04]">
                  <span className="text-[10px] text-slate-500">观察目标</span>
                  <strong className="mt-2 font-mono text-xl text-red-400">+5%</strong>
                </div>
                <div className="discipline-tile border-emerald-400/15 bg-emerald-400/[0.04]">
                  <span className="text-[10px] text-slate-500">单股风险线</span>
                  <strong className="mt-2 font-mono text-xl text-emerald-400">-6%</strong>
                </div>
                <div className="discipline-tile border-emerald-400/15 bg-emerald-400/[0.04]">
                  <span className="text-[10px] text-slate-500">组合风险线</span>
                  <strong className="mt-2 font-mono text-xl text-emerald-400">-4%</strong>
                </div>
              </div>

              <div className="mt-5 rounded-xl border border-slate-800/80 bg-slate-950/40 p-4">
                <div className="mb-3 flex items-center justify-between text-[10px] uppercase tracking-[0.15em] text-slate-600">
                  <span>Signal governance</span>
                  <span className="text-cyan-500">Rules locked</span>
                </div>
                <div className="space-y-3 text-xs text-slate-400">
                  <div className="flex items-center justify-between"><span>候选不足</span><span className="text-slate-200">保留现金，不强行满仓</span></div>
                  <div className="h-px bg-slate-800/70" />
                  <div className="flex items-center justify-between"><span>信号解释</span><span className="text-slate-200">因子分，不等于胜率</span></div>
                  <div className="h-px bg-slate-800/70" />
                  <div className="flex items-center justify-between"><span>执行原则</span><span className="text-slate-200">纪律优先于主观判断</span></div>
                </div>
              </div>
            </div>
          </section>

          <section id="weekly-signals" className="scroll-mt-5">
            <WeeklyAdvisor />
          </section>
        </main>

        <footer className="mt-5 flex flex-col items-center justify-between gap-3 border-t border-slate-900 px-1 py-5 text-[10px] tracking-wide text-slate-600 sm:flex-row">
          <div>QUANTAI RESEARCH TERMINAL · 东方财富公开市场数据</div>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5"><span className="h-1 w-1 rounded-full bg-cyan-500" /> 数据链路正常</span>
            <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3 w-3" /> 研究用途</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
