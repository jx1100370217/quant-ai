import { NextResponse } from 'next/server'

const UT = 'fa5fd1943c7b386f172d6893dbbd1d0c'
const HEADERS = { 'Referer': 'https://quote.eastmoney.com/', 'User-Agent': 'Mozilla/5.0' }

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code') || '600183'
  const klt = searchParams.get('klt') || '101'
  const lmt = searchParams.get('lmt') || '60'

  const market = code.startsWith('6') || code === '000001' ? '1' : '0'
  const secid = `${market}.${code}`
  const url = `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${secid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57&klt=${klt}&fqt=1&end=20500101&lmt=${lmt}&ut=${UT}`
  
  try {
    const res = await fetch(url, { headers: HEADERS, cache: 'no-store' })
    const data = await res.json()
    if (data.rc !== 0 || !data.data?.klines) return NextResponse.json({ success: false, data: [] })
    
    const klines = data.data.klines.map((k: string) => {
      const p = k.split(',')
      return { date: p[0], open: +p[1], close: +p[2], high: +p[3], low: +p[4], volume: +p[5], amount: +p[6], change: +((+p[2] - +p[1]) / +p[1] * 100).toFixed(2) }
    })
    return NextResponse.json({ success: true, name: data.data.name, code: data.data.code, klines })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
