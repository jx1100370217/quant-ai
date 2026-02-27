import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const TIMEOUT_MS = 300_000 // 5分钟（持仓数多时 LLM 顺序执行）

function fetchWithTimeout(url: string, options: RequestInit, ms: number) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer))
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const res = await fetchWithTimeout(
      `${BACKEND_URL}/api/agents/analyze-holdings`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        cache: 'no-store',
      },
      TIMEOUT_MS
    )

    if (!res.ok) {
      const err = await res.text().catch(() => res.statusText)
      return NextResponse.json(
        { success: false, error: `后端错误 ${res.status}: ${err}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (e: any) {
    if (e?.name === 'AbortError' || e?.name === 'TimeoutError') {
      return NextResponse.json(
        { success: false, error: '持仓分析超时，请稍后重试' },
        { status: 503 }
      )
    }
    if (e?.code === 'ECONNREFUSED' || e?.cause?.code === 'ECONNREFUSED') {
      return NextResponse.json(
        { success: false, error: '无法连接后端，请确认 backend 已启动（cd backend && python main.py）' },
        { status: 503 }
      )
    }
    return NextResponse.json(
      { success: false, error: e?.message || '未知错误' },
      { status: 500 }
    )
  }
}
