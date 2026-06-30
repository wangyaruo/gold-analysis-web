export const AXIS_TICK_COUNT = 10
export const Y_AXIS_TICK_COUNT = 7

const pad = (n) => String(n).padStart(2, '0')
const TICK_STEPS = {
  '1min': { unit: 'minute', step: 15 },
  '1h': { unit: 'hour', step: 1 },
  '1day': { unit: 'day', step: 1 },
  '1month': { unit: 'month', step: 1 },
}

export function parseTime(raw) {
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d
}

export function monthDiff(start, end) {
  return (end.getFullYear() - start.getFullYear()) * 12 + end.getMonth() - start.getMonth()
}

function dateKey(d) {
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

function timeLabel(d) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function chineseDateLabel(d) {
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function shortDateLabel(d) {
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function clampIndex(index, max) {
  if (!Number.isFinite(index)) return 0
  return Math.max(0, Math.min(Math.round(index), max))
}

function floorToTick(date, period) {
  const d = new Date(date)
  d.setSeconds(0, 0)
  if (period === '1min') {
    d.setMinutes(Math.floor(d.getMinutes() / TICK_STEPS['1min'].step) * TICK_STEPS['1min'].step)
    return d
  }
  if (period === '1h') {
    d.setMinutes(0)
    return d
  }
  if (period === '1day') {
    d.setHours(0, 0, 0, 0)
    return d
  }
  if (period === '1month') {
    d.setDate(1)
    d.setHours(0, 0, 0, 0)
    return d
  }
  return d
}

function addTick(date, period, amount) {
  const d = new Date(date)
  const config = TICK_STEPS[period] || TICK_STEPS['1day']
  if (config.unit === 'minute') d.setMinutes(d.getMinutes() + config.step * amount)
  if (config.unit === 'hour') d.setHours(d.getHours() + config.step * amount)
  if (config.unit === 'day') d.setDate(d.getDate() + config.step * amount)
  if (config.unit === 'month') d.setMonth(d.getMonth() + config.step * amount)
  return d
}

function tickDistance(a, b) {
  return Math.abs(a.getTime() - b.getTime())
}

function fallbackVisibleIndexes(startIndex, endIndex) {
  const length = endIndex - startIndex + 1
  if (length <= AXIS_TICK_COUNT) {
    return new Set(Array.from({ length }, (_item, i) => startIndex + i))
  }
  const step = (length - 1) / (AXIS_TICK_COUNT - 1)
  return new Set(Array.from({ length: AXIS_TICK_COUNT }, (_item, i) => Math.round(startIndex + step * i)))
}

function nearestUnusedDataIndex(points, target, usedIndexes) {
  let best = null
  let bestDistance = Infinity
  points.forEach((point) => {
    if (usedIndexes.has(point.index)) return
    const distance = tickDistance(point.time, target)
    if (distance < bestDistance) {
      best = point.index
      bestDistance = distance
    }
  })
  return best
}

function fallbackVisibleTicks(data, period, startIndex, endIndex) {
  return [...fallbackVisibleIndexes(startIndex, endIndex)].map((index) => ({
    index,
    time: floorToTick(parseTime(data[index]?.time) || new Date(), period),
  }))
}

function buildAxisTicks(data, period, range = {}) {
  if (!data.length) return []
  const maxIndex = data.length - 1
  const startIndex = clampIndex(range.startIndex ?? 0, maxIndex)
  const endIndex = Math.max(startIndex, clampIndex(range.endIndex ?? maxIndex, maxIndex))
  const visiblePoints = []

  for (let index = startIndex; index <= endIndex; index += 1) {
    const time = parseTime(data[index]?.time)
    if (time) visiblePoints.push({ index, time })
  }

  if (!visiblePoints.length) return fallbackVisibleTicks(data, period, startIndex, endIndex)
  if (visiblePoints.length <= AXIS_TICK_COUNT) {
    return visiblePoints.map((point) => ({ index: point.index, time: floorToTick(point.time, period) }))
  }

  const lastTime = visiblePoints[visiblePoints.length - 1].time
  const anchorEnd = floorToTick(lastTime, period)
  const usedIndexes = new Set()
  const ticks = []

  for (let offset = AXIS_TICK_COUNT - 1; offset >= 0; offset -= 1) {
    const time = addTick(anchorEnd, period, -offset)
    const index = nearestUnusedDataIndex(visiblePoints, time, usedIndexes)
    if (index == null) continue
    usedIndexes.add(index)
    ticks.push({ index, time })
  }

  return ticks.length ? ticks.sort((a, b) => a.index - b.index) : fallbackVisibleTicks(data, period, startIndex, endIndex)
}

function formatTickSequenceLabels(ticks, period) {
  const labels = []
  let lastDayKey = null
  let lastYear = null

  ticks.forEach(({ time }) => {
    if (period === '1month') {
      const year = time.getFullYear()
      labels.push(lastYear === null || year !== lastYear ? `${year}\n${time.getMonth() + 1}月` : `${time.getMonth() + 1}月`)
      lastYear = year
      return
    }
    if (period === '1day') {
      const year = time.getFullYear()
      labels.push(lastYear === null || year !== lastYear ? `${year}\n${shortDateLabel(time)}` : shortDateLabel(time))
      lastYear = year
      return
    }
    const key = dateKey(time)
    labels.push(key !== lastDayKey ? `${chineseDateLabel(time)}\n${timeLabel(time)}` : timeLabel(time))
    lastDayKey = key
  })

  return labels
}

export function formatFullTime(raw, period) {
  const d = parseTime(raw)
  if (!d) return raw ? String(raw) : ''
  if (period === '1month') return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (period === '1day') return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${timeLabel(d)}`
}

export function formatDataZoomLabel(raw, period) {
  const d = parseTime(raw)
  if (!d) return raw ? String(raw) : ''
  if (period === '1month') return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
  if (period === '1day') return shortDateLabel(d)
  return `${shortDateLabel(d)} ${timeLabel(d)}`
}

// 根据当前可见窗口生成固定刻度:
// 分线每 15 分钟, 时线每 1 小时, 日线每 1 天, 月线每 1 个月; 数据足够时固定 10 个。
export function buildAxisLabelIndexes(data, period, range = {}) {
  return new Set(buildAxisTicks(data, period, range).map((tick) => tick.index))
}

export function buildAxisLabelTexts(data, period, labelIndexes = buildAxisLabelIndexes(data, period)) {
  const labels = new Array(data.length).fill('')
  let lastDayKey = null
  let lastYear = null

  data.forEach((item, index) => {
    if (!labelIndexes.has(index)) return
    const current = parseTime(item.time)
    if (!current) {
      labels[index] = item.time ? String(item.time) : ''
      return
    }
    if (period === '1month') {
      const year = current.getFullYear()
      labels[index] = lastYear === null || year !== lastYear
        ? `${year}\n${current.getMonth() + 1}月`
        : `${current.getMonth() + 1}月`
      lastYear = year
      return
    }
    if (period === '1day') {
      const year = current.getFullYear()
      labels[index] = lastYear === null || year !== lastYear
        ? `${year}\n${shortDateLabel(current)}`
        : shortDateLabel(current)
      lastYear = year
      return
    }
    // 1min / 1h: 显示时间, 跨天的第一格补上日期
    const key = dateKey(current)
    labels[index] = key !== lastDayKey
      ? `${chineseDateLabel(current)}\n${timeLabel(current)}`
      : timeLabel(current)
    lastDayKey = key
  })

  return labels
}

export function buildAxisLabelLookup(data, period, range = {}) {
  const ticks = buildAxisTicks(data, period, range)
  const tickLabels = formatTickSequenceLabels(ticks, period)
  const labelIndexes = new Set(ticks.map((tick) => tick.index))
  const labels = new Array(data.length).fill('')
  const values = new Set()
  const textByValue = new Map()

  ticks.forEach((tick, tickIndex) => {
    const { index } = tick
    const text = tickLabels[tickIndex] || ''
    const value = formatFullTime(data[index]?.time, period)
    if (!value) return
    labels[index] = text
    values.add(value)
    textByValue.set(value, text)
  })

  return { labelIndexes, labels, values, textByValue }
}

export function axisLabelRotate() {
  return 0
}

function niceCeil(value) {
  if (!Number.isFinite(value) || value <= 0) return 1
  const exponent = Math.floor(Math.log10(value))
  const fraction = value / 10 ** exponent
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10
  return niceFraction * 10 ** exponent
}

function precisionFor(value) {
  if (!Number.isFinite(value)) return 0
  if (value >= 1) return 2
  if (value >= 0.01) return 3
  return 4
}

function roundTo(value, decimals) {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

// 纵坐标固定 7 个刻度 (6 段), 整齐间隔, 完整覆盖给定数值范围
export function buildYAxisScale(values, stopLoss = null) {
  const allValues = values
    .concat(stopLoss == null ? [] : [stopLoss])
    .map(Number)
    .filter(Number.isFinite)

  if (!allValues.length) {
    return { splitNumber: Y_AXIS_TICK_COUNT - 1 }
  }

  let minValue = Math.min(...allValues)
  let maxValue = Math.max(...allValues)
  if (minValue === maxValue) {
    const padding = Math.max(Math.abs(minValue) * 0.002, 1)
    minValue -= padding
    maxValue += padding
  }

  const segments = Y_AXIS_TICK_COUNT - 1
  let interval = niceCeil((maxValue - minValue) / segments)
  let decimals = precisionFor(interval)
  let min = roundTo(Math.floor(minValue / interval) * interval, decimals)
  let max = roundTo(min + interval * segments, decimals)

  let guard = 0
  while (max < maxValue && guard < 6) {
    interval = niceCeil(interval + interval * 0.5)
    decimals = precisionFor(interval)
    min = roundTo(Math.floor(minValue / interval) * interval, decimals)
    max = roundTo(min + interval * segments, decimals)
    guard += 1
  }

  return { min, max, interval, splitNumber: segments }
}

// 给定可见区间 [startIdx, endIdx], 用区间内 OHLC 重算纵轴 (拖动时调用)
export function buildYAxisScaleForRange(data, startIdx, endIdx, stopLoss = null) {
  const s = Math.max(0, Math.floor(startIdx))
  const e = Math.min(data.length - 1, Math.ceil(endIdx))
  const slice = data.slice(s, e + 1)
  const values = slice.flatMap((c) => [c.open, c.high, c.low, c.close])
  return buildYAxisScale(values, stopLoss)
}

export function formatYAxisValue(value, interval) {
  if (!Number.isFinite(Number(value))) return value
  if (interval >= 10) return Number(value).toFixed(0)
  if (interval >= 1) {
    const text = Number(value).toFixed(2)
    return text.endsWith('.00') ? text.slice(0, -3) : text
  }
  return Number(value).toFixed(3)
}
