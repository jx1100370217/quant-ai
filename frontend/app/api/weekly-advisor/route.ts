import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const TIMEOUT_MS = 180_000 // 3 分钟（LLM 生成周报较慢）

function fetchWithTimeout(url: string, options: RequestInit, ms: number) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(timer))
}

// GET: 获取最新周报
export async function GET() {
  try {
    const res = await fetchWithTimeout(
      `${BACKEND_URL}/api/weekly-advisor/latest`,
      { cache: 'no-store' },
      30_000
    )

    if (res.status === 404) {
      return NextResponse.json({ success: false, error: 'NOT_FOUND' }, { status: 404 })
    }

    if (!res.ok) {
      const err = await res.text().catch(() => res.statusText)
      return NextResponse.json(
        { success: false, error: `后端错误 ${res.status}: ${err}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    // 后端返回 {success, data: {report}} — 透传 report 部分
    const report = data?.data ?? data
    return NextResponse.json({ success: true, data: report })
  } catch (e: any) {
    if (e?.name === 'AbortError' || e?.name === 'TimeoutError') {
      return NextResponse.json({ success: false, error: '请求超时' }, { status: 503 })
    }
    if (e?.code === 'ECONNREFUSED' || e?.cause?.code === 'ECONNREFUSED') {
      return NextResponse.json(
        { success: false, error: '无法连接后端，请确认 backend 已启动' },
        { status: 503 }
      )
    }
    return NextResponse.json({ success: false, error: e?.message || '未知错误' }, { status: 500 })
  }
}

// POST: 生成新周报
export async function POST() {
  try {
    const res = await fetchWithTimeout(
      `${BACKEND_URL}/api/weekly-advisor/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
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
    // 后端返回 {success, data: {report}} 或直接 {report} — 透传 report 部分
    const report = data?.data ?? data
    return NextResponse.json({ success: true, data: report })
  } catch (e: any) {
    if (e?.name === 'AbortError' || e?.name === 'TimeoutError') {
      return NextResponse.json(
        { success: false, error: '生成周报超时（可能仍在后台运行），请稍后刷新' },
        { status: 503 }
      )
    }
    if (e?.code === 'ECONNREFUSED' || e?.cause?.code === 'ECONNREFUSED') {
      return NextResponse.json(
        { success: false, error: '无法连接后端，请确认 backend 已启动' },
        { status: 503 }
      )
    }
    return NextResponse.json({ success: false, error: e?.message || '未知错误' }, { status: 500 })
  }
}
