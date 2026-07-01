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
const INTRADAY_SESSION_CUTOFF_HOUR = 6
const MAX_SAME_SESSION_GAP_MS = 20 * 60 * 60 * 1000
const ZHESHANG_SOURCE_KEY = 'jdjygold_zheshang'
const NATURAL_DAY_MINUTES = 24 * 60
const NATURAL_DAY_TICK_OFFSETS = [0, 6 * 60, 12 * 60, 18 * 60, NATURAL_DAY_MINUTES]
const SOURCE_TRADING_SESSIONS = {
  icbc: 'weekday_day',
  [ZHESHANG_SOURCE_KEY]: 'zheshang_weekly',
  hongyun_gold_reference: 'weekday_overnight',
}
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

function sourceSessionType(sourceKey) {
  return SOURCE_TRADING_SESSIONS[sourceKey] || null
}

function isZheshangSource(sourceKey) {
  return sourceKey === ZHESHANG_SOURCE_KEY
}

function minutesOfDay(d) {
  return d.getHours() * 60 + d.getMinutes()
}

function isMondayToFriday(d) {
  const day = d.getDay()
  return day >= 1 && day <= 5
}

function isTuesdayToSaturday(d) {
  const day = d.getDay()
  return day >= 2 && day <= 6
}

function previousDateKey(d) {
  const previous = new Date(d)
  previous.setDate(previous.getDate() - 1)
  return dateKey(previous)
}

function mondayDateKey(d) {
  const monday = new Date(d)
  const day = monday.getDay()
  const offset = day === 0 ? 6 : day - 1
  monday.setDate(monday.getDate() - offset)
  return dateKey(monday)
}

function startOfDate(d) {
  const date = new Date(d)
  date.setHours(0, 0, 0, 0)
  return date
}

function nextDateStart(d) {
  const date = startOfDate(d)
  date.setDate(date.getDate() + 1)
  return date
}

function withTime(date, hour, minute) {
  const d = new Date(date)
  d.setHours(hour, minute, 0, 0)
  return d
}

function sessionDateKey(d) {
  const sessionDate = new Date(d)
  if (sessionDate.getHours() < INTRADAY_SESSION_CUTOFF_HOUR) {
    sessionDate.setDate(sessionDate.getDate() - 1)
  }
  return dateKey(sessionDate)
}

function timeLabel(d) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function timeLabelWithSeconds(d) {
  return `${timeLabel(d)}:${pad(d.getSeconds())}`
}

function localIsoMinute(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${timeLabel(d)}:00.000`
}

function localIsoSecond(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${timeLabelWithSeconds(d)}.000`
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

function finiteNumberOrNull(value) {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
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
  const lastPoint = visiblePoints[visiblePoints.length - 1]

  INTRADAY_REFERENCE_TIMES.forEach((reference) => {
    const target = intradayTargetTime(baseDate, reference)
    const index = nearestUnusedDataIndex(visiblePoints, target, usedIndexes)
    if (index == null) return
    usedIndexes.add(index)
    ticks.push({ index, time: minuteTick(visiblePoints.find((point) => point.index === index)?.time || target) })
  })

  if (!usedIndexes.has(lastPoint.index)) {
    ticks.push({ index: lastPoint.index, time: minuteTick(lastPoint.time) })
  }

  return ticks.sort((a, b) => a.index - b.index)
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

function isIntradayTradingTime(time, sourceKey) {
  const sessionType = sourceSessionType(sourceKey)
  if (!sessionType) return true

  const minute = minutesOfDay(time)

  if (sessionType === 'weekday_day') {
    return isMondayToFriday(time) && minute >= 9 * 60 + 10 && minute <= 22 * 60 + 30
  }

  if (sessionType === 'zheshang_weekly') {
    const day = time.getDay()
    if (day === 1) return minute >= 9 * 60
    if (day >= 2 && day <= 5) return true
    if (day === 6) return minute <= 2 * 60 + 30
    return false
  }

  if (sessionType === 'weekday_overnight') {
    const daySession = isMondayToFriday(time) && minute >= 9 * 60 + 10
    const overnightSession = isTuesdayToSaturday(time) && minute <= 2 * 60
    return daySession || overnightSession
  }

  return true
}

function sourceAwareSessionKey(time, sourceKey) {
  const sessionType = sourceSessionType(sourceKey)
  if (!sessionType) return null

  const minute = minutesOfDay(time)

  if (sessionType === 'weekday_day') {
    return `weekday_day:${dateKey(time)}`
  }

  if (sessionType === 'zheshang_weekly') {
    return `zheshang_weekly:${mondayDateKey(time)}`
  }

  if (sessionType === 'weekday_overnight') {
    const key = minute <= 2 * 60 ? previousDateKey(time) : dateKey(time)
    return `weekday_overnight:${key}`
  }

  return null
}

function sourceSessionBounds(time, sourceKey) {
  const sessionType = sourceSessionType(sourceKey)
  if (!sessionType) return null

  const minute = minutesOfDay(time)

  if (sessionType === 'weekday_day') {
    const base = startOfDate(time)
    return {
      key: sourceAwareSessionKey(time, sourceKey),
      open: withTime(base, 9, 10),
      close: withTime(base, 22, 30),
    }
  }

  if (sessionType === 'zheshang_weekly') {
    const monday = startOfDate(time)
    const day = monday.getDay()
    const offset = day === 0 ? 6 : day - 1
    monday.setDate(monday.getDate() - offset)
    const saturday = new Date(monday)
    saturday.setDate(saturday.getDate() + 5)
    return {
      key: sourceAwareSessionKey(time, sourceKey),
      open: withTime(monday, 9, 0),
      close: withTime(saturday, 2, 30),
    }
  }

  if (sessionType === 'weekday_overnight') {
    const openDate = startOfDate(time)
    if (minute <= 2 * 60) {
      openDate.setDate(openDate.getDate() - 1)
    }
    const closeDate = new Date(openDate)
    closeDate.setDate(closeDate.getDate() + 1)
    return {
      key: sourceAwareSessionKey(time, sourceKey),
      open: withTime(openDate, 9, 10),
      close: withTime(closeDate, 2, 0),
    }
  }

  return null
}

function shouldSplitIntradaySession(previousTime, currentTime, sourceKey) {
  if (!previousTime || !currentTime) return false
  const previousSessionKey = sourceAwareSessionKey(previousTime, sourceKey)
  const currentSessionKey = sourceAwareSessionKey(currentTime, sourceKey)
  if (previousSessionKey && currentSessionKey) {
    return previousSessionKey !== currentSessionKey
  }
  if (sessionDateKey(previousTime) !== sessionDateKey(currentTime)) return true
  return currentTime.getTime() - previousTime.getTime() > MAX_SAME_SESSION_GAP_MS
}

function buildIntradayBreakRow(previousTime, currentTime) {
  let breakTime = new Date(previousTime)
  breakTime.setMinutes(breakTime.getMinutes() + 1, 0, 0)
  if (breakTime >= currentTime) {
    breakTime = new Date((previousTime.getTime() + currentTime.getTime()) / 2)
  }
  return {
    time: localIsoMinute(minuteTick(breakTime)),
    open: null,
    high: null,
    low: null,
    close: null,
    isBreak: true,
  }
}

function resolveOptionDate(raw) {
  const parsed = raw ? parseTime(raw) : null
  return parsed || new Date()
}

function decorateNaturalDayRow(row, sessionKey, dayStart, isBoundaryEnd = false) {
  return {
    ...row,
    displaySessionType: 'natural_day',
    displaySessionKey: sessionKey,
    naturalDayStart: localIsoMinute(dayStart),
    axisLabelOverride: isBoundaryEnd ? '24:00' : undefined,
  }
}

function buildZheshangNaturalDayTimeline(barByMinute, options = {}) {
  const dayByKey = new Map()

  function ensureDay(dayStart) {
    const key = dateKey(dayStart)
    if (!dayByKey.has(key)) {
      dayByKey.set(key, {
        key,
        open: startOfDate(dayStart),
        close: nextDateStart(dayStart),
        bars: new Map(),
      })
    }
    return dayByKey.get(key)
  }

  Array.from(barByMinute.values()).forEach((bar) => {
    const time = parseTime(bar.time)
    if (!time) return
    const day = ensureDay(startOfDate(time))
    day.bars.set(bar.time, bar)
  })

  const defaultDayStart = startOfDate(resolveOptionDate(options.now))
  const defaultDayKey = dateKey(defaultDayStart)
  ensureDay(defaultDayStart)

  const days = Array.from(dayByKey.values()).sort((a, b) => a.open - b.open)
  const timeline = []
  const sessions = []
  let previousClose = null
  let latestSession = null

  days.forEach((day) => {
    const sessionKey = `zheshang_day:${day.key}`
    if (previousClose) {
      timeline.push(buildIntradayBreakRow(previousClose, day.open))
    }

    const startIndex = timeline.length
    for (let cursor = new Date(day.open); cursor <= day.close; cursor.setMinutes(cursor.getMinutes() + 1)) {
      const time = localIsoMinute(cursor)
      const isBoundaryEnd = cursor.getTime() === day.close.getTime()
      const bar = isBoundaryEnd ? null : day.bars.get(time)
      const emptyRow = {
        time,
        open: null,
        high: null,
        low: null,
        close: null,
      }
      timeline.push(decorateNaturalDayRow(bar || emptyRow, sessionKey, day.open, isBoundaryEnd))
    }

    const endIndex = timeline.length - 1
    const session = {
      startIndex,
      endIndex,
      sessionOpen: localIsoMinute(day.open),
      sessionClose: localIsoMinute(day.close),
    }
    if (day.key === defaultDayKey) latestSession = session
    sessions.push(session)
    previousClose = day.close
  })

  latestSession = latestSession || sessions[sessions.length - 1] || null
  return { data: timeline, sessions, latestSession }
}

function buildScheduledIntradayTimeline(barByMinute, sourceKey) {
  const sessionByKey = new Map()
  Array.from(barByMinute.values()).forEach((bar) => {
    const time = parseTime(bar.time)
    const bounds = time ? sourceSessionBounds(time, sourceKey) : null
    if (!bounds?.key) return
    if (!sessionByKey.has(bounds.key)) {
      sessionByKey.set(bounds.key, { ...bounds, bars: new Map() })
    }
    sessionByKey.get(bounds.key).bars.set(bar.time, bar)
  })

  const scheduledSessions = Array.from(sessionByKey.values()).sort((a, b) => a.open - b.open)
  if (!scheduledSessions.length) {
    return { data: [], sessions: [] }
  }

  const timeline = []
  const sessions = []
  let previousClose = null

  scheduledSessions.forEach((session) => {
    if (previousClose) {
      timeline.push(buildIntradayBreakRow(previousClose, session.open))
    }

    const startIndex = timeline.length
    for (let cursor = new Date(session.open); cursor <= session.close; cursor.setMinutes(cursor.getMinutes() + 1)) {
      const time = localIsoMinute(cursor)
      timeline.push(session.bars.get(time) || {
        time,
        open: null,
        high: null,
        low: null,
        close: null,
        sessionKey: session.key,
      })
    }
    const endIndex = timeline.length - 1
    sessions.push({
      startIndex,
      endIndex,
      sessionOpen: localIsoMinute(session.open),
      sessionClose: localIsoMinute(session.close),
    })
    previousClose = session.close
  })

  return { data: timeline, sessions }
}

function addIntradaySession(sessions, data, startIndex, endIndex) {
  if (startIndex == null || endIndex == null || startIndex > endIndex) return
  const session = {
    startIndex,
    endIndex,
    sessionOpen: data[startIndex]?.time,
    sessionClose: data[endIndex]?.time,
  }
  if (data[startIndex]?.displaySessionKey) {
    session.sessionKey = data[startIndex].displaySessionKey
  }
  sessions.push(session)
}

function inferIntradaySessions(data, sourceKey) {
  const sessions = []
  let startIndex = null
  let lastRealIndex = null
  let previousTime = null
  let previousRowSessionKey = null

  data.forEach((item, index) => {
    if (item?.isBreak) {
      addIntradaySession(sessions, data, startIndex, lastRealIndex)
      startIndex = null
      lastRealIndex = null
      previousTime = null
      previousRowSessionKey = null
      return
    }

    const currentTime = parseTime(item?.time)
    if (!currentTime) return
    const currentRowSessionKey = item?.displaySessionKey || sourceAwareSessionKey(currentTime, sourceKey)

    if (sourceSessionType(sourceKey) && !item?.isBreak) {
      const shouldSplit = previousTime && (
        previousRowSessionKey && currentRowSessionKey
          ? previousRowSessionKey !== currentRowSessionKey
          : shouldSplitIntradaySession(previousTime, currentTime, sourceKey)
      )
      if (shouldSplit) {
        addIntradaySession(sessions, data, startIndex, lastRealIndex)
        startIndex = null
        lastRealIndex = null
      }

      if (startIndex == null) startIndex = index
      lastRealIndex = index
      previousTime = currentTime
      previousRowSessionKey = currentRowSessionKey
      return
    }

    if (!Number.isFinite(Number(item?.close))) return

    if (previousTime && shouldSplitIntradaySession(previousTime, currentTime, sourceKey)) {
      addIntradaySession(sessions, data, startIndex, lastRealIndex)
      startIndex = null
      lastRealIndex = null
    }

    if (startIndex == null) startIndex = index
    lastRealIndex = index
    previousTime = currentTime
  })

  addIntradaySession(sessions, data, startIndex, lastRealIndex)
  return sessions
}

function normalizeIntradayOptions(options = {}) {
  if (typeof options === 'string') return { sourceKey: options }
  return options || {}
}

export function buildIntradayTimeline(data, options = {}) {
  const normalizedOptions = normalizeIntradayOptions(options)
  const { sourceKey = '' } = normalizedOptions
  const points = data
    .map((item) => ({ item, time: parseTime(item.time) }))
    .filter(({ item, time }) => time && Number.isFinite(Number(item.close)) && isIntradayTradingTime(time, sourceKey))
    .sort((a, b) => a.time - b.time)

  const barByMinute = new Map()

  points.forEach(({ item, time }) => {
    const key = localIsoMinute(minuteTick(time))
    barByMinute.set(key, mergeMinuteBar(barByMinute.get(key) || { time: key }, item))
  })

  if (isZheshangSource(sourceKey)) {
    const scheduledTimeline = buildZheshangNaturalDayTimeline(barByMinute, normalizedOptions)
    const latestSession = scheduledTimeline.latestSession
    const { labelIndexes, labels } = buildAxisLabelLookup(scheduledTimeline.data, '1min')
    return {
      data: scheduledTimeline.data,
      labelIndexes,
      labels,
      sessions: scheduledTimeline.sessions,
      latestSession,
      sessionOpen: latestSession?.sessionOpen,
      sessionClose: latestSession?.sessionClose,
    }
  }

  if (!points.length) {
    return { data: [], labelIndexes: new Set(), labels: [] }
  }

  if (sourceSessionType(sourceKey)) {
    const scheduledTimeline = buildScheduledIntradayTimeline(barByMinute, sourceKey)
    const latestSession = scheduledTimeline.sessions[scheduledTimeline.sessions.length - 1] || null
    const { labelIndexes, labels } = buildAxisLabelLookup(scheduledTimeline.data, '1min')
    return {
      data: scheduledTimeline.data,
      labelIndexes,
      labels,
      sessions: scheduledTimeline.sessions,
      latestSession,
      sessionOpen: latestSession?.sessionOpen,
      sessionClose: latestSession?.sessionClose,
    }
  }

  const timeline = []
  const sessions = []
  let sessionStartIndex = null
  let previousTime = null
  let previousRealIndex = null

  Array.from(barByMinute.values())
    .sort((a, b) => parseTime(a.time) - parseTime(b.time))
    .forEach((bar) => {
      const currentTime = parseTime(bar.time)
      if (previousTime && shouldSplitIntradaySession(previousTime, currentTime, sourceKey)) {
        addIntradaySession(sessions, timeline, sessionStartIndex, previousRealIndex)
        timeline.push(buildIntradayBreakRow(previousTime, currentTime))
        sessionStartIndex = null
        previousRealIndex = null
      }

      if (sessionStartIndex == null) sessionStartIndex = timeline.length
      timeline.push(bar)
      previousTime = currentTime
      previousRealIndex = timeline.length - 1
    })

  addIntradaySession(sessions, timeline, sessionStartIndex, previousRealIndex)

  const latestSession = sessions[sessions.length - 1] || null
  const { labelIndexes, labels } = buildAxisLabelLookup(timeline, '1min')

  return {
    data: timeline,
    labelIndexes,
    labels,
    sessions,
    latestSession,
    sessionOpen: latestSession?.sessionOpen,
    sessionClose: latestSession?.sessionClose,
  }
}

function normalizeRealtimeSample(sample) {
  const time = parseTime(sample?.time || sample?.timestamp)
  const price = finiteNumberOrNull(sample?.price ?? sample?.display_price ?? sample?.close ?? sample?.value)
  if (!time || price == null) return null
  return { time, price }
}

function decorateRealtimeSample(row, sourceKey, time) {
  if (!isZheshangSource(sourceKey)) return row
  const dayStart = startOfDate(time)
  return decorateNaturalDayRow(row, `zheshang_day:${dateKey(dayStart)}`, dayStart)
}

export function mergeRealtimeSamplesIntoTimeline(data, samples = [], options = {}) {
  if (!Array.isArray(samples) || !samples.length) return data
  const { sourceKey = '' } = normalizeIntradayOptions(options)
  const rowByTime = new Map((Array.isArray(data) ? data : []).map((item) => [item.time, item]))

  samples.forEach((sample) => {
    const normalized = normalizeRealtimeSample(sample)
    if (!normalized || !isIntradayTradingTime(normalized.time, sourceKey)) return
    const time = localIsoSecond(normalized.time)
    const existing = rowByTime.get(time)
    const price = normalized.price
    const row = {
      ...(existing || {}),
      time,
      open: finiteNumberOrNull(existing?.open) ?? price,
      high: Math.max(finiteNumberOrNull(existing?.high) ?? price, price),
      low: Math.min(finiteNumberOrNull(existing?.low) ?? price, price),
      close: price,
      isRealtimeSample: true,
    }
    rowByTime.set(time, decorateRealtimeSample(row, sourceKey, normalized.time))
  })

  return Array.from(rowByTime.values()).sort((a, b) => {
    const left = parseTime(a.time)
    const right = parseTime(b.time)
    return Number(left || 0) - Number(right || 0)
  })
}

export function buildIntradayViewportRange(data, options = {}) {
  const { sourceKey = '' } = normalizeIntradayOptions(options)
  const n = data.length
  if (!n) return { start: 0, end: 0, focused: false }

  const finiteIndexes = []
  data.forEach((item, index) => {
    if (finiteNumberOrNull(item.close) != null) finiteIndexes.push(index)
  })
  if (!finiteIndexes.length) return { start: 0, end: n - 1, focused: false }

  const sessions = inferIntradaySessions(data, sourceKey)
  const defaultDayKey = isZheshangSource(sourceKey)
    ? `zheshang_day:${dateKey(startOfDate(resolveOptionDate(normalizeIntradayOptions(options).now)))}`
    : null
  const latestSession = defaultDayKey
    ? sessions.find((session) => session.sessionKey === defaultDayKey) || sessions[sessions.length - 1]
    : sessions[sessions.length - 1]
  if (!latestSession) return { start: finiteIndexes[0], end: finiteIndexes[finiteIndexes.length - 1], focused: false }

  const start = latestSession.startIndex
  const end = latestSession.endIndex
  return { start, end, focused: start > 0 || end < n - 1 }
}

export function buildIntradayLineSegments(data) {
  const segments = []
  let current = new Array(data.length).fill(null)
  let hasPoint = false

  function pushCurrent() {
    if (!hasPoint) return
    segments.push(current)
    current = new Array(data.length).fill(null)
    hasPoint = false
  }

  data.forEach((item, index) => {
    if (item?.isBreak) {
      pushCurrent()
      return
    }

    const close = finiteNumberOrNull(item?.close)
    if (close == null) return

    current[index] = close
    hasPoint = true
  })

  pushCurrent()
  return segments
}

export function findNearestFiniteClose(data, index) {
  if (!Array.isArray(data) || !data.length) return null
  const start = clampIndex(index, data.length - 1)
  for (let distance = 0; distance < data.length; distance += 1) {
    const leftIndex = start - distance
    if (leftIndex >= 0) {
      const left = finiteNumberOrNull(data[leftIndex]?.close)
      if (left != null) return { index: leftIndex, value: left }
    }
    const rightIndex = start + distance
    if (rightIndex !== leftIndex && rightIndex < data.length) {
      const right = finiteNumberOrNull(data[rightIndex]?.close)
      if (right != null) return { index: rightIndex, value: right }
    }
  }
  return null
}

export function buildLineTooltipHtml({ label, value, unit = 'CNY/g', decimals = 3, nearest = null } = {}) {
  const price = finiteNumberOrNull(value)
  const header = `<div style="font-weight:600;margin-bottom:3px">${label || ''}</div>`
  if (price != null) {
    return `${header}<div>价格 <b>${price.toFixed(decimals)}</b> ${unit}</div>`
  }
  const nearestPrice = finiteNumberOrNull(nearest?.value)
  const nearestLine = nearestPrice == null
    ? ''
    : `<div style="color:#9b8b63;margin-top:2px">最近价格 <b>${nearestPrice.toFixed(decimals)}</b> ${unit}</div>`
  return `${header}<div>该时间无交易数据</div>${nearestLine}`
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
    if (period === '1min' && data[index]?.isBreak) continue
    if (time) visiblePoints.push({ index, time })
  }

  if (!visiblePoints.length) return fallbackVisibleTicks(data, period, startIndex, endIndex)
  if (period === '1min' && isNaturalDayRange(data, startIndex, endIndex)) {
    return buildNaturalDayTicks(data, startIndex, endIndex)
  }
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

function isNaturalDayRange(data, startIndex, endIndex) {
  const first = data[startIndex]
  const last = data[endIndex]
  return first?.displaySessionType === 'natural_day'
    && last?.displaySessionType === 'natural_day'
    && first.displaySessionKey
    && first.displaySessionKey === last.displaySessionKey
    && endIndex - startIndex >= NATURAL_DAY_MINUTES
}

function buildNaturalDayTicks(data, startIndex, endIndex) {
  const ticks = []
  NATURAL_DAY_TICK_OFFSETS.forEach((offset) => {
    const index = startIndex + offset
    if (index > endIndex || !data[index]) return
    const time = parseTime(data[index].time)
    if (!time) return
    ticks.push({
      index,
      time,
      labelOverride: offset === 0
        ? `${chineseDateLabel(time)}\n00:00`
        : offset === NATURAL_DAY_MINUTES
          ? '24:00'
          : timeLabel(time),
    })
  })
  return ticks
}

function formatTickSequenceLabels(ticks, period) {
  const labels = []
  let lastDayKey = null
  let lastYear = null

  ticks.forEach(({ time, labelOverride }) => {
    if (labelOverride) {
      labels.push(labelOverride)
      return
    }
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
  const label = period === '1min' && d.getSeconds() !== 0 ? timeLabelWithSeconds(d) : timeLabel(d)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${label}`
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

export function buildZoomMinValueSpan(period, dataLength, options = {}) {
  const n = Number(dataLength)
  if (!Number.isFinite(n) || n <= 1) return 0
  const windowSize = Math.min(n, ZOOM_MIN_WINDOWS[period] || 7)
  const defaultSpan = Math.max(0, windowSize - 1)
  const visibleSpan = Number(options.visibleSpan)
  if (period === '1min' && Number.isFinite(visibleSpan)) {
    return Math.max(0, Math.min(defaultSpan, Math.floor(visibleSpan)))
  }
  return defaultSpan
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
    const highValue = finiteNumberOrNull(row?.high ?? row?.close)
    const lowValue = finiteNumberOrNull(row?.low ?? row?.close)

    if (highValue != null && (high == null || highValue > high.value)) {
      high = { index, value: highValue }
    }
    if (lowValue != null && (low == null || lowValue < low.value)) {
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

function normalizeYAxisOptions(tickCountOrOptions) {
  if (tickCountOrOptions && typeof tickCountOrOptions === 'object') {
    const tickCount = Number.isFinite(Number(tickCountOrOptions.tickCount))
      ? Math.max(2, Math.floor(Number(tickCountOrOptions.tickCount)))
      : Y_AXIS_TICK_COUNT
    const fixedInterval = Number(tickCountOrOptions.fixedInterval)
    const minInterval = Number(tickCountOrOptions.minInterval)
    const maxSplitNumber = Number(tickCountOrOptions.maxSplitNumber)
    return {
      tickCount,
      fixedInterval: Number.isFinite(fixedInterval) && fixedInterval > 0 ? fixedInterval : null,
      minInterval: Number.isFinite(minInterval) && minInterval > 0 ? minInterval : null,
      maxSplitNumber: Number.isFinite(maxSplitNumber) && maxSplitNumber > 0
        ? Math.floor(maxSplitNumber)
        : null,
    }
  }

  const tickCount = Number.isFinite(Number(tickCountOrOptions))
    ? Math.max(2, Math.floor(Number(tickCountOrOptions)))
    : Y_AXIS_TICK_COUNT
  return { tickCount, fixedInterval: null, minInterval: null, maxSplitNumber: null }
}

function buildFixedIntervalYAxisScale(allValues, fixedInterval, tickCount) {
  if (!allValues.length) {
    return { interval: fixedInterval, splitNumber: tickCount - 1 }
  }

  let minValue = Math.min(...allValues)
  let maxValue = Math.max(...allValues)
  const decimals = precisionFor(fixedInterval)

  if (minValue === maxValue) {
    minValue -= fixedInterval
    maxValue += fixedInterval
  }

  let min = roundTo(Math.floor(minValue / fixedInterval) * fixedInterval, decimals)
  let max = roundTo(Math.ceil(maxValue / fixedInterval) * fixedInterval, decimals)
  let splitNumber = Math.max(1, Math.round((max - min) / fixedInterval))
  max = roundTo(min + splitNumber * fixedInterval, decimals)

  return { min, max, interval: fixedInterval, splitNumber }
}

function readableIntervalAtLeast(value, minInterval) {
  const target = Math.max(Number(value) || 0, minInterval)
  const exponent = Math.floor(Math.log10(target))
  const base = 10 ** exponent
  return [1, 2, 5, 10].map((step) => step * base).find((step) => step >= target) || 10 * base
}

function buildAdaptiveIntervalYAxisScale(allValues, minInterval, maxSplitNumber, tickCount) {
  if (!allValues.length) {
    return { interval: minInterval, splitNumber: Math.min(tickCount - 1, maxSplitNumber) }
  }

  let minValue = Math.min(...allValues)
  let maxValue = Math.max(...allValues)
  if (minValue === maxValue) {
    minValue -= minInterval
    maxValue += minInterval
  }

  const maxSegments = Math.max(1, maxSplitNumber || tickCount - 1)
  let interval = readableIntervalAtLeast((maxValue - minValue) / maxSegments, minInterval)
  let decimals = precisionFor(interval)
  let min = roundTo(Math.floor(minValue / interval) * interval, decimals)
  let max = roundTo(Math.ceil(maxValue / interval) * interval, decimals)
  let splitNumber = Math.max(1, Math.round((max - min) / interval))

  let guard = 0
  while (splitNumber > maxSegments && guard < 8) {
    interval = readableIntervalAtLeast(interval * 1.01, minInterval)
    decimals = precisionFor(interval)
    min = roundTo(Math.floor(minValue / interval) * interval, decimals)
    max = roundTo(Math.ceil(maxValue / interval) * interval, decimals)
    splitNumber = Math.max(1, Math.round((max - min) / interval))
    guard += 1
  }

  max = roundTo(min + splitNumber * interval, decimals)
  return { min, max, interval, splitNumber }
}

// 纵坐标固定 7 个刻度 (6 段), 整齐间隔, 完整覆盖给定数值范围
export function buildYAxisScale(values, stopLoss = null, tickCountOrOptions = Y_AXIS_TICK_COUNT) {
  const { tickCount, fixedInterval, minInterval, maxSplitNumber } = normalizeYAxisOptions(tickCountOrOptions)
  const allValues = values
    .concat(stopLoss == null ? [] : [stopLoss])
    .map(finiteNumberOrNull)
    .filter((value) => value != null)

  if (fixedInterval != null) {
    return buildFixedIntervalYAxisScale(allValues, fixedInterval, tickCount)
  }
  if (minInterval != null) {
    return buildAdaptiveIntervalYAxisScale(allValues, minInterval, maxSplitNumber, tickCount)
  }

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
export function buildYAxisScaleForRange(data, startIdx, endIdx, stopLoss = null, tickCountOrOptions = Y_AXIS_TICK_COUNT) {
  const s = Math.max(0, Math.floor(startIdx))
  const e = Math.min(data.length - 1, Math.ceil(endIdx))
  const slice = data.slice(s, e + 1)
  const values = slice.flatMap((c) => [c.open, c.high, c.low, c.close])
  return buildYAxisScale(values, stopLoss, tickCountOrOptions)
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
