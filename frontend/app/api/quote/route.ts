import { NextResponse } from 'next/server'

const UT = 'fa5fd1943c7b386f172d6893dbbd1d0c'
const HEADERS = {
  'Referer': 'https://quote.eastmoney.com/',
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
}

// 代码→secid（沪A:1.6xx/5xx, 深A:0.0xx/3xx, 指数0.399xxx/1.000xxx）
function toSecid(code: string): string {
  if (code.startsWith('6') || code.startsWith('5') || code.startsWith('688')) return `1.${code}`
  if (code.startsWith('399')) return `0.${code}`
  if (code === '000001') return `1.${code}` // 上证指数特殊处理
  return `0.${code}`
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const codes = (searchParams.get('codes') || '').split(',').map(c => c.trim()).filter(Boolean)
  if (codes.length === 0) return NextResponse.json({ success: false, data: [] })

  const secids = codes.map(toSecid).join(',')

  // 使用 ulist.np/get + fltt=2：f9/f115/f23 在此接口能正确返回 PE/PB
  const url = `https://push2.eastmoney.com/api/qt/ulist.np/get`
    + `?secids=${encodeURIComponent(secids)}`
    + `&fields=f12,f14,f2,f3,f4,f5,f6,f8,f15,f16,f17,f18,f9,f115,f23,f20,f21`
    + `&fltt=2&ut=${UT}`

  try {
    const res = await fetch(url, { headers: HEADERS, cache: 'no-store' })
    const json = await res.json()
    const diff: any[] = json?.data?.diff ?? []
    if (!diff.length) return NextResponse.json({ success: false, data: [] })

    const safeFloat = (v: any, def = 0): number => {
      if (v === null || v === undefined || v === '-') return def
      const n = parseFloat(v)
      return isNaN(n) ? def : n
    }

    const quotes = diff.map((d: any) => {
      const price     = safeFloat(d.f2)
      const high      = safeFloat(d.f15, price)
      const low       = safeFloat(d.f16, price)
      const preClose  = safeFloat(d.f18, price)
      return {
        code:          d.f12,
        name:          d.f14,
        current:       price,
        percent:       safeFloat(d.f3),
        chg:           safeFloat(d.f4),
        high,
        low,
        open:          safeFloat(d.f17, price),
        last_close:    preClose,
        volume:        safeFloat(d.f5),
        amount:        safeFloat(d.f6),
        turnover_rate: d.f8 != null ? safeFloat(d.f8) : null,
        // 基本面（fltt=2 直接是真实值，非 ×100）
        pe_ttm:        d.f115 ? safeFloat(d.f115) : null,
        pe:            d.f9   ? safeFloat(d.f9)   : null,
        pb:            d.f23  ? safeFloat(d.f23)  : null,
        market_cap:    d.f20  ? safeFloat(d.f20)  : null,
      }
    })

    return NextResponse.json({ success: true, data: quotes })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
