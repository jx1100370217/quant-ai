import { NextResponse } from 'next/server'
import { readFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

// 解析东方财富App的二进制Cookie文件（macOS binarycookies格式）
function readEastMoneyCookies(): Record<string, string> {
  const cookiePath = join(
    homedir(),
    'Library/Containers/com.eastmoney.explore/Data/Library/Cookies/Cookies.binarycookies'
  )
  try {
    const buf = readFileSync(cookiePath)
    if (buf.slice(0, 4).toString() !== 'cook') return {}

    const numPages = buf.readUInt32BE(4)
    const pageSizes: number[] = []
    for (let i = 0; i < numPages; i++) {
      pageSizes.push(buf.readUInt32BE(8 + i * 4))
    }

    let offset = 8 + numPages * 4
    const cookies: Record<string, string> = {}

    for (const pageSize of pageSizes) {
      const page = buf.slice(offset, offset + pageSize)
      offset += pageSize

      if (page.readUInt32BE(0) !== 0x00000100) continue
      const numCookies = page.readUInt32LE(4)

      for (let i = 0; i < numCookies; i++) {
        try {
          const cookieOffset = page.readUInt32LE(8 + i * 4)
          const cd = page.slice(cookieOffset)

          const urlOff = cd.readUInt32LE(16)
          const nameOff = cd.readUInt32LE(20)
          const valueOff = cd.readUInt32LE(28)

          const readStr = (off: number) => {
            const end = cd.indexOf(0, off)
            return cd.slice(off, end).toString('utf8')
          }

          const domain = readStr(urlOff)
          const name = readStr(nameOff)
          const value = readStr(valueOff)

          if (domain.includes('jyjqtxmix') || domain.includes('jywg')) {
            cookies[name] = value
          }
        } catch {}
      }
    }
    return cookies
  } catch {
    return {}
  }
}

export async function GET() {
  try {
    const cookies = readEastMoneyCookies()

    if (!cookies['jyweb_session']) {
      return NextResponse.json({ success: false, error: '东方财富App未登录或Cookie已过期，请打开App重新登录' }, { status: 401 })
    }

    const cookieStr = Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join('; ')

    const res = await fetch('https://jyjqtxmix.18.cn/Com/queryAssetAndPositionV1', {
      headers: {
        'Cookie': cookieStr,
        'Referer': 'https://jyjqtxmix.18.cn/Trade/Buy',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest',
      },
      cache: 'no-store',
    })

    const data = await res.json()

    if (!data.Data || !data.Data[0]) {
      return NextResponse.json({ success: false, error: '未获取到持仓数据' })
    }

    const acct = data.Data[0]
    // parseFloat(undefined/null/"") → NaN，用 || 0 防空
    const safeFloat = (v: any, fallback = 0): number => {
      const n = parseFloat(v)
      return isNaN(n) ? fallback : n
    }
    const safeInt = (v: any, fallback = 0): number => {
      const n = parseInt(v, 10)
      return isNaN(n) ? fallback : n
    }

    const positions = (acct.positions || []).map((p: any) => ({
      code: p.Zqdm,
      name: p.Zqmc || p.zqzwqc || p.Zqdm,
      shares: safeInt(p.Gfye),
      availableShares: safeInt(p.Kysl),
      cost: safeFloat(p.Cbjg),
      current: safeFloat(p.Zxjg),
      marketValue: safeFloat(p.Zxsz),
      pnl: safeFloat(p.Ljyk),
      pnlPct: safeFloat(p.Ykbl),
      todayPnl: safeFloat(p.Dryk),
      todayPnlPct: safeFloat(p.Drykbl),
    }))

    return NextResponse.json({
      success: true,
      data: {
        cash: safeFloat(acct.Zjye),
        totalAssets: safeFloat(acct.Zzc),
        totalMarketValue: safeFloat(acct.Zxsz),
        totalPnl: safeFloat(acct.Ljyk),
        todayPnl: safeFloat(acct.Dryk),
        positions,
      },
      updatedAt: new Date().toISOString(),
    })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
