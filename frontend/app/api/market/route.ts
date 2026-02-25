import { NextResponse } from 'next/server'

const HEADERS = {
  'Referer': 'https://quote.eastmoney.com/',
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

const UT = 'fa5fd1943c7b386f172d6893dbbd1d0c'

// 批量指数行情
async function getIndices() {
  const url = `https://push2.eastmoney.com/api/qt/ulist.np/get?secids=1.000001,0.399001,0.399006&fields=f1,f2,f3,f4,f5,f6,f7,f8,f12,f14&ut=${UT}`
  const res = await fetch(url, { headers: HEADERS, cache: 'no-store' })
  const data = await res.json()
  if (data.rc !== 0 || !data.data?.diff) return []
  return data.data.diff.map((d: any) => ({
    code: d.f12,
    name: d.f14,
    current: d.f2 / 100,
    change: d.f4 / 100,
    changePercent: d.f3 / 100,
    volume: d.f5,
    amount: d.f6,
    amplitude: d.f7 / 100,
    turnover: d.f8 / 100,
  }))
}

// 板块资金流入排行(行业)
async function getSectors() {
  const url = `https://push2.eastmoney.com/api/qt/clist/get?cb=j&pn=1&pz=10&po=1&np=1&ut=${UT}&fltt=2&invt=2&fid=f62&fs=m:90+t:2+f:!50&fields=f12,f14,f2,f3,f62,f184`
  const headers = { 'Referer': 'https://data.eastmoney.com/', 'User-Agent': 'Mozilla/5.0' }
  const res = await fetch(url, { headers, cache: 'no-store' })
  const text = await res.text()
  const jsonStr = text.replace(/^j\(/, '').replace(/\);?$/, '')
  const data = JSON.parse(jsonStr)
  if (data.rc !== 0 || !data.data?.diff) return []
  
  // 过滤掉一级大类板块（通常净流入金额远大于细分行业）
  const bigCategories = new Set(['电子','有色金属','通信','基础化工','建筑装饰','机械设备','电力设备','汽车','计算机','医药生物','食品饮料','银行','非银金融','房地产','公用事业','交通运输','轻工制造','纺织服饰','商贸零售','社会服务','传媒','综合','农林牧渔','钢铁','煤炭','石油石化','环保','美容护理','国防军工','建筑材料'])
  
  return data.data.diff
    .filter((d: any) => !bigCategories.has(d.f14))
    .slice(0, 10)
    .map((d: any) => ({
      code: d.f12,
      name: d.f14,
      change: d.f3,  // fltt=2 已格式化，直接是百分比
      flow: d.f62,  // 主力净流入(元)
      flowRate: d.f184,
    }))
}

export async function GET() {
  try {
    const [indices, sectors] = await Promise.all([getIndices(), getSectors()])
    return NextResponse.json({ success: true, indices, sectors, timestamp: new Date().toISOString() })
  } catch (e: any) {
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
