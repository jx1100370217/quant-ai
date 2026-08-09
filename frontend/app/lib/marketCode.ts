export type MarketCode = {
  code: string
  market?: 'SH' | 'SZ' | 'BJ'
}

/**
 * 解析 A 股代码。指数等存在同号歧义的证券必须显式携带市场，
 * 例如上证指数用 000001.SH，裸 000001 始终表示平安银行。
 */
export function splitMarketCode(input: string): MarketCode {
  const value = input.trim().toUpperCase()
  const suffix = value.match(/^(\d{6})\.(SH|SZ|BJ)$/)
  if (suffix) return { code: suffix[1], market: suffix[2] as MarketCode['market'] }

  const prefix = value.match(/^(SH|SZ|BJ)\.?(\d{6})$/)
  if (prefix) return { code: prefix[2], market: prefix[1] as MarketCode['market'] }

  return { code: value }
}

export function toEastmoneySecid(input: string): string {
  const { code, market } = splitMarketCode(input)
  const marketId = market ? (market === 'SH' ? '1' : '0') : (/^[56]/.test(code) ? '1' : '0')
  return `${marketId}.${code}`
}
