export const AXIS_TICK_COUNT = 10
export const Y_AXIS_TICK_COUNT = 7

const pad = (n) => String(n).padStart(2, '0')
const TICK_STEPS = {
  '1min': { unit: 'minute', step: 15 },
  '1h': { unit: 'hour', step: 1 },
  '1day': { unit: 'day', step: 1 },
  '1month': { unit: 'month', step: 1 },
}
const INTRADAY_REFERENCE_TIMES = [
  { hour: 13, minute: 0 },
  { hour: 18, minute: 0 },
  { hour: 22, minute: 30 },
]
const ZOOM_MIN_WINDOWS = {
  '1min': 30,
  '1day': 7,
  '1month': 6,
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

function localIsoMinute(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${timeLabel(d)}:00.000`
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

function minuteTick(date) {
  const d = new Date(date)
  d.setSeconds(0, 0)
  return d
}

function intradayTargetTime(baseDate, { hour, minute }) {
  const d = new Date(baseDate)
  d.setHours(hour, minute, 0, 0)
  return d
}

function buildIntradayReferenceTicks(visiblePoints) {
  if (visiblePoints.length <= 4) {
    return visiblePoints.map((point) => ({ index: point.index, time: minuteTick(point.time) }))
  }

  const usedIndexes = new Set([visiblePoints[0].index])
  const ticks = [{ index: visiblePoints[0].index, time: minuteTick(visiblePoints[0].time) }]
  const baseDate = visiblePoints[0].time

  INTRADAY_REFERENCE_TIMES.forEach((reference) => {
    const target = intradayTargetTime(baseDate, reference)
    const index = nearestUnusedDataIndex(visiblePoints, target, usedIndexes)
    if (index == null) return
    usedIndexes.add(index)
    ticks.push({ index, time: minuteTick(visiblePoints.find((point) => point.index === index)?.time || target) })
  })

  return ticks.sort((a, b) => a.index - b.index)
}

function minutesBetween(start, end) {
  return Math.round((end.getTime() - start.getTime()) / 60000)
}

function mergeMinuteBar(existing, item) {
  const open = Number(item.open)
  const high = Number(item.high ?? item.close)
  const low = Number(item.low ?? item.close)
  const close = Number(item.close)
  const next = { ...existing }

  if (!Number.isFinite(next.open) && Number.isFinite(open)) next.open = open
  if (Number.isFinite(high)) next.high = Number.isFinite(next.high) ? Math.max(next.high, high) : high
  if (Number.isFinite(low)) next.low = Number.isFinite(next.low) ? Math.min(next.low, low) : low
  if (Number.isFinite(close)) next.close = close

  return next
}

export function buildIntradayTimeline(data) {
  const points = data
    .map((item) => ({ item, time: parseTime(item.time) }))
    .filter(({ item, time }) => time && Number.isFinite(Number(item.close)))
    .sort((a, b) => a.time - b.time)

  if (!points.length) {
    return { data: [], labelIndexes: new Set(), labels: [] }
  }

  const firstTime = minuteTick(points[0].time)
  const lastTime = minuteTick(points[points.length - 1].time)
  const start = firstTime
  const end = lastTime
  const barByMinute = new Map()

  points.forEach(({ item, time }) => {
    const key = localIsoMinute(minuteTick(time))
    barByMinute.set(key, mergeMinuteBar(barByMinute.get(key) || { time: key }, item))
  })

  const timeline = []
  for (let cursor = new Date(start); cursor <= end; cursor.setMinutes(cursor.getMinutes() + 1)) {
    const key = localIsoMinute(cursor)
    timeline.push(barByMinute.get(key) || { time: key })
  }

  const labelIndexes = new Set()
  const labels = new Array(timeline.length).fill('')
  const referenceDates = [
    start,
    ...INTRADAY_REFERENCE_TIMES.map((reference) => intradayTargetTime(start, reference)),
    end,
  ]
  let lastDayKey = null

  referenceDates.forEach((reference) => {
    if (reference < start || reference > end) return
    const index = minutesBetween(start, reference)
    const key = dateKey(reference)
    labels[index] = key !== lastDayKey ? `${chineseDateLabel(reference)}\n${timeLabel(reference)}` : timeLabel(reference)
    labelIndexes.add(index)
    lastDayKey = key
  })

  return {
    data: timeline,
    labelIndexes,
    labels,
    sessionOpen: localIsoMinute(start),
    sessionClose: localIsoMinute(end),
  }
}

export function buildIntradayViewportRange(data, options = {}) {
  const n = data.length
  if (!n) return { start: 0, end: 0, focused: false }

  const finiteIndexes = []
  data.forEach((item, index) => {
    if (Number.isFinite(Number(item.close))) finiteIndexes.push(index)
  })
  if (!finiteIndexes.length) return { start: 0, end: n - 1, focused: false }

  const first = finiteIndexes[0]
  const last = finiteIndexes[finiteIndexes.length - 1]
  const span = last - first + 1
  const fullDayThreshold = Number(options.fullDayThreshold ?? 240)
  if (span >= fullDayThreshold) return { start: 0, end: n - 1, focused: false }

  const minWindow = Math.min(n, Number(options.minWindow ?? 180))
  const padding = Number(options.padding ?? 30)
  const desiredWindow = Math.min(n, Math.max(minWindow, span + padding * 2))
  if (desiredWindow >= n) return { start: 0, end: n - 1, focused: false }
  const center = (first + last) / 2
  let start = Math.round(center - (desiredWindow - 1) / 2)
  start = Math.max(0, Math.min(start, n - desiredWindow))
  const end = start + desiredWindow - 1

  return { start, end, focused: true }
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
  if (period === '1min') return buildIntradayReferenceTicks(visiblePoints)
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

export function buildViewportResetKey({ period, sourceKey } = {}) {
  return `${period || ''}::${sourceKey || ''}`
}

export function buildZoomMinValueSpan(period, dataLength) {
  const n = Number(dataLength)
  if (!Number.isFinite(n) || n <= 1) return 0
  const windowSize = Math.min(n, ZOOM_MIN_WINDOWS[period] || 7)
  return Math.max(0, windowSize - 1)
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

export function buildVisibleExtrema(data, startIdx, endIdx) {
  if (!data.length) return { high: null, low: null }

  const start = Math.max(0, Math.floor(startIdx))
  const end = Math.min(data.length - 1, Math.ceil(endIdx))
  if (start > end) return { high: null, low: null }

  let high = null
  let low = null

  for (let index = start; index <= end; index += 1) {
    const row = data[index]
    const highValue = Number(row?.high ?? row?.close)
    const lowValue = Number(row?.low ?? row?.close)

    if (Number.isFinite(highValue) && (high == null || highValue > high.value)) {
      high = { index, value: highValue }
    }
    if (Number.isFinite(lowValue) && (low == null || lowValue < low.value)) {
      low = { index, value: lowValue }
    }
  }

  return { high, low }
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
export function buildYAxisScale(values, stopLoss = null, tickCount = Y_AXIS_TICK_COUNT) {
  const allValues = values
    .concat(stopLoss == null ? [] : [stopLoss])
    .map(Number)
    .filter(Number.isFinite)

  if (!allValues.length) {
    return { splitNumber: tickCount - 1 }
  }

  let minValue = Math.min(...allValues)
  let maxValue = Math.max(...allValues)
  if (minValue === maxValue) {
    const padding = Math.max(Math.abs(minValue) * 0.002, 1)
    minValue -= padding
    maxValue += padding
  }

  const segments = tickCount - 1
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
export function buildYAxisScaleForRange(data, startIdx, endIdx, stopLoss = null, tickCount = Y_AXIS_TICK_COUNT) {
  const s = Math.max(0, Math.floor(startIdx))
  const e = Math.min(data.length - 1, Math.ceil(endIdx))
  const slice = data.slice(s, e + 1)
  const values = slice.flatMap((c) => [c.open, c.high, c.low, c.close])
  return buildYAxisScale(values, stopLoss, tickCount)
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
