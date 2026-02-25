import { NextResponse } from 'next/server'

const UT = 'fa5fd1943c7b386f172d6893dbbd1d0c'

// 获取板块成分股（按涨幅排序）
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const sectorCode = searchParams.get('code') || 'BK0477'
  const pz = searchParams.get('limit') || '10'

  const url = `https://push2.eastmoney.com/api/qt/clist/get?cb=j&pn=1&pz=${pz}&po=1&np=1&ut=${UT}&fltt=2&invt=2&fid=f3&fs=b:${sectorCode}&fields=f12,f14,f2,f3,f62,f184,f15,f16,f17,f5,f6`
  const headers = { 'Referer': 'https://quote.eastmoney.com/', 'User-Agent': 'Mozilla/5.0' }

  try {
    const res = await fetch(url, { headers, cache: 'no-store' })
    const text = await res.text()
    const jsonStr = text.replace(/^j\(/, '').replace(/\);?$/, '')
    const data = JSON.parse(jsonStr)
    if (data.rc !== 0 || !data.data?.diff) return NextResponse.json({ success: false, stocks: [] })

    // fltt=2 表示已经格式化好的数据，不需要再÷100
    const stocks = data.data.diff.map((d: any) => ({
      code: d.f12,
      name: d.f14,
      price: d.f2,
      changePct: d.f3,
      mainNetInflow: d.f62,
      mainInflowRate: d.f184,
      high: d.f15,
      low: d.f16,
      open: d.f17,
      volume: d.f5,
      amount: d.f6,
    }))
    return NextResponse.json({ success: true, stocks })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
