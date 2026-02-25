'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal, ChevronRight, RotateCw } from 'lucide-react'

export interface LogEntry {
  time: string
  agent: string
  color: string
  message: string
}

interface AgentChatProps {
  logs: LogEntry[]
  running: boolean
  onReanalyze: () => void
}

export default function AgentChat({ logs, running, onReanalyze }: AgentChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="cyber-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Terminal className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold">分析日志</h2>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onReanalyze}
            disabled={running}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-300
              ${running
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40'
              }`}
          >
            <RotateCw className={`w-3.5 h-3.5 ${running ? 'animate-spin' : ''}`} />
            <span>{running ? '分析中...' : '重新分析'}</span>
          </button>
          <div className="flex items-center space-x-1">
            <div className={`w-2 h-2 rounded-full ${running ? 'bg-yellow-400' : 'bg-green-400'} animate-pulse`} />
            <span className="text-xs text-gray-500">{running ? '运行中' : '就绪'}</span>
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="h-[350px] overflow-y-auto scrollbar-thin bg-black/30 rounded-lg p-3 font-mono text-xs space-y-1">
        {logs.length === 0 && !running && (
          <div className="flex items-center justify-center h-full text-gray-600">
            点击「重新分析」开始实时分析
          </div>
        )}
        {logs.map((log, idx) => (
          <div key={idx} className="flex items-start space-x-2 animate-fade-in">
            <span className="text-gray-600 shrink-0">{log.time}</span>
            <span className={`shrink-0 ${log.color}`}>[{log.agent}]</span>
            <span className="text-gray-300">{log.message}</span>
          </div>
        ))}
        {running && (
          <div className="flex items-center space-x-1 text-cyan-500">
            <ChevronRight className="w-3 h-3 animate-pulse" />
            <span className="animate-pulse">_</span>
          </div>
        )}
      </div>
    </div>
  )
}
