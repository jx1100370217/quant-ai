import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function GET() {
  try {
    // 只调用一次 overview 接口（已包含 indices + sectors + flow）
    const res = await fetch(`${BACKEND_URL}/api/market/overview`, { cache: 'no-store' })
    const data = await res.json()

    if (!data?.success || !data?.data) {
      return NextResponse.json({ success: false, error: 'Backend returned no data' }, { status: 502 })
    }

    const raw = data.data

    // 转换 indices 格式
    const indices = raw.indices
      ? Object.values(raw.indices).map((d: any) => ({
          code: d.code,
          name: d.name,
          current: d.price,
          change: d.change,
          changePercent: d.change_pct,
          volume: d.volume,
          amount: d.amount,
          amplitude: d.amplitude,
          turnover: d.turnover_rate,
        }))
      : []

    // 转换 sectors 格式
    const sectors = Array.isArray(raw.sectors)
      ? raw.sectors.slice(0, 10).map((d: any) => ({
          code: d.code || '',
          name: d.name,
          change: d.change_pct,
          flow: d.net_inflow,
          flowRate: d.inflow_rate,
        }))
      : []

    return NextResponse.json({
      success: true,
      indices,
      sectors,
      timestamp: new Date().toISOString(),
    })
  } catch (e: any) {
    return NextResponse.json(
      { success: false, error: e.message || 'fetch failed' },
      { status: 500 }
    )
  }
}
