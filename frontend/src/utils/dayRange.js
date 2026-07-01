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

function positiveNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : null
}

function average(values) {
  const validValues = values.filter((value) => value !== null)
  if (!validValues.length) return null
  return validValues.reduce((sum, value) => sum + value, 0) / validValues.length
}

function todayCandles(candles, now) {
  const today = dateKey(now)
  return (candles || []).filter((candle) => dateKey(candle.time) === today)
}

function firstOpeningPrice(candles) {
  for (const candle of candles) {
    const open = positiveNumber(candle.open)
    if (open !== null) return open

    const close = positiveNumber(candle.close)
    if (close !== null) return close
  }
  return null
}

function typicalPrice(candle) {
  return average([
    positiveNumber(candle.high),
    positiveNumber(candle.low),
    positiveNumber(candle.close),
  ])
}

function sourceRangeMidpoint(sourceRange) {
  if (!sourceRange) return null
  const low = positiveNumber(sourceRange.low)
  const high = positiveNumber(sourceRange.high)
  if (low === null || high === null) return null
  return (low + high) / 2
}

function predictionBasis(currentPrice, candles, now, sourceRange) {
  const candlesForToday = todayCandles(candles, now)
  const openingPrice = firstOpeningPrice(candlesForToday)
  const intradayAverage = average(candlesForToday.map(typicalPrice))
  const stableAverage = intradayAverage ?? sourceRangeMidpoint(sourceRange)

  if (openingPrice !== null && stableAverage !== null) {
    return openingPrice * 0.6 + stableAverage * 0.4
  }

  return stableAverage ?? openingPrice ?? positiveNumber(currentPrice)
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

function roundPrice(value) {
  return Math.round(Number(value) * 100) / 100
}

export function buildPredictedDailyRange(currentPrice, rangePercent = 0.02, candles = [], now = new Date(), sourceRange = null) {
  const price = predictionBasis(currentPrice, candles, now, sourceRange)
  const range = Number(rangePercent)
  if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(range) || range <= 0) {
    return null
  }

  const low = (2 * price) / (2 + range)
  const high = low * (1 + range)
  const observedRange = buildTodayRange(candles, currentPrice, now, sourceRange)
  return {
    low: roundPrice(observedRange ? Math.min(low, observedRange.low) : low),
    high: roundPrice(observedRange ? Math.max(high, observedRange.high) : high),
    rangePercent: range,
  }
}
