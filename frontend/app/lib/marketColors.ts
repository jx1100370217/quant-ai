export type MarketDirection = 'up' | 'down' | 'flat'

export interface MarketTone {
  direction: MarketDirection
  text: string
  softText: string
  border: string
  background: string
}

const TONES: Record<MarketDirection, MarketTone> = {
  // A股行情惯例：上涨红、下跌绿。
  up: {
    direction: 'up',
    text: 'text-red-400',
    softText: 'text-red-300/70',
    border: 'border-red-500/30',
    background: 'bg-red-900/20',
  },
  down: {
    direction: 'down',
    text: 'text-green-400',
    softText: 'text-green-300/70',
    border: 'border-green-500/30',
    background: 'bg-green-900/20',
  },
  flat: {
    direction: 'flat',
    text: 'text-gray-400',
    softText: 'text-gray-400/70',
    border: 'border-gray-600/30',
    background: 'bg-gray-800/30',
  },
}

export function getMarketTone(value: number | null | undefined): MarketTone {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) {
    return TONES.flat
  }
  return value > 0 ? TONES.up : TONES.down
}

export function marketArrow(value: number | null | undefined): string {
  const direction = getMarketTone(value).direction
  return direction === 'up' ? '↑' : direction === 'down' ? '↓' : '—'
}
