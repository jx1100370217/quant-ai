import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const TIMEOUT_MS = 180_000 // 3分钟（16 agent 并发 + 数据获取，需要足够余量）

// Next.js fetch 不支持 AbortSignal.timeout，用 Promise.race 代替
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
      `${BACKEND_URL}/api/agents/market-picks`,
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
    // AbortController abort → DOMException: The operation was aborted / AbortError
    if (e?.name === 'AbortError' || e?.name === 'TimeoutError') {
      return NextResponse.json(
        { success: false, error: `选股分析超时（>${Math.round(TIMEOUT_MS / 1000)}s），后端可能正在高负载，请稍后点击"重新选股"` },
        { status: 503 }
      )
    }
    // 连接被拒绝（backend未启动）
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
