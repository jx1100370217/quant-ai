import { NextResponse } from 'next/server'

const UT = 'fa5fd1943c7b386f172d6893dbbd1d0c'
const HEADERS = { 'Referer': 'https://quote.eastmoney.com/', 'User-Agent': 'Mozilla/5.0' }

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const codes = searchParams.get('codes') || ''
  
  // 用雪球接口批量查，更简单
  const symbols = codes.split(',').map(c => {
    const market = c.startsWith('6') || c === '000001' ? 'SH' : 'SZ'
    return `${market}${c}`
  }).join(',')
  
  try {
    const res = await fetch(`https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol=${symbols}`, {
      headers: { 'User-Agent': 'Mozilla/5.0' }, cache: 'no-store'
    })
    const data = await res.json()
    if (!data.data) return NextResponse.json({ success: false, data: [] })
    
    const quotes = data.data.map((d: any) => ({
      code: d.symbol?.replace(/^(SH|SZ)/, ''),
      symbol: d.symbol,
      current: d.current,
      percent: d.percent,
      chg: d.chg,
      high: d.high,
      low: d.low,
      open: d.open,
      last_close: d.last_close,
      volume: d.volume,
      amount: d.amount,
      turnover_rate: d.turnover_rate,
    }))
    return NextResponse.json({ success: true, data: quotes })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
