function dateKey(value) {
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

function numericValues(candle) {
  return [candle.low, candle.high, candle.open, candle.close]
    .map(Number)
    .filter(Number.isFinite)
}

export function buildTodayRange(candles, currentPrice, now = new Date(), sourceRange = null) {
  if (sourceRange) {
    const low = Number(sourceRange.low)
    const high = Number(sourceRange.high)
    const current = Number(currentPrice)
    const values = [low, high].filter(Number.isFinite)
    if (Number.isFinite(current)) values.push(current)
    if (values.length) {
      return {
        low: Math.min(...values),
        high: Math.max(...values),
      }
    }
  }

  const today = dateKey(now)
  const values = []

  for (const candle of candles || []) {
    if (dateKey(candle.time) !== today) continue
    values.push(...numericValues(candle))
  }

  if (!values.length) return null

  const current = Number(currentPrice)
  if (Number.isFinite(current)) values.push(current)

  return {
    low: Math.min(...values),
    high: Math.max(...values),
  }
}
