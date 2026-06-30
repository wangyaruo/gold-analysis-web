import assert from 'node:assert/strict'
import {
  AXIS_TICK_COUNT,
  Y_AXIS_TICK_COUNT,
  buildAxisLabelLookup,
  buildAxisLabelIndexes,
  buildAxisLabelTexts,
  buildIntradayTimeline,
  buildIntradayViewportRange,
  buildViewportResetKey,
  buildVisibleExtrema,
  buildZoomMinValueSpan,
  buildYAxisScale,
  buildYAxisScaleForRange,
  formatDataZoomLabel,
  formatFullTime,
} from './chartAxis.js'

const rows = (times) => times.map((time) => ({ time }))
const hourlyRows = (count) => rows(Array.from({ length: count }, (_, i) => {
  const d = new Date('2026-06-26T06:00:00')
  d.setHours(d.getHours() + i)
  return d.toISOString()
}))
const minuteRows = (count) => rows(Array.from({ length: count }, (_, i) => {
  const d = new Date('2026-06-29T14:45:00')
  d.setMinutes(d.getMinutes() + i)
  return d.toISOString()
}))
const dailyRows = (count) => rows(Array.from({ length: count }, (_, i) => {
  const d = new Date('2026-05-31T00:00:00')
  d.setDate(d.getDate() + i)
  return d.toISOString()
}))
const monthlyRows = (count) => rows(Array.from({ length: count }, (_, i) => {
  const d = new Date('2025-11-01T00:00:00')
  d.setMonth(d.getMonth() + i)
  return d.toISOString()
}))

function assertFixedTickGap(data, indexes, period, expectedGap) {
  assert.equal(indexes.length, AXIS_TICK_COUNT, `${period} should show 10 x-axis ticks`)
  indexes.slice(1).forEach((index, i) => {
    const prev = new Date(data[indexes[i]].time)
    const current = new Date(data[index].time)
    if (period === '1month') {
      assert.equal(monthGap(prev, current), expectedGap, `${period} tick gap should be ${expectedGap} month`)
      return
    }
    assert.equal(current.getTime() - prev.getTime(), expectedGap, `${period} tick gap should be fixed`)
  })
}

function monthGap(start, end) {
  return (end.getFullYear() - start.getFullYear()) * 12 + end.getMonth() - start.getMonth()
}

assert.equal(AXIS_TICK_COUNT, 10)
assert.equal(Y_AXIS_TICK_COUNT, 7)

for (const [period, data] of [
  ['1h', hourlyRows(24)],
  ['1day', dailyRows(30)],
  ['1month', monthlyRows(18)],
]) {
  const indexes = [...buildAxisLabelIndexes(data, period)]
  const expectedGap = period === '1min'
    ? 15 * 60 * 1000
    : period === '1h'
      ? 60 * 60 * 1000
      : period === '1day'
        ? 24 * 60 * 60 * 1000
        : 1
  assertFixedTickGap(data, indexes, period, expectedGap)
}

const intradayReferenceRows = rows([
  '2026-06-29T09:10:00',
  '2026-06-29T10:25:00',
  '2026-06-29T13:00:00',
  '2026-06-29T16:40:00',
  '2026-06-29T18:00:00',
  '2026-06-29T20:20:00',
  '2026-06-29T22:30:00',
])
const intradayLookup = buildAxisLabelLookup(intradayReferenceRows, '1min')
assert.deepEqual([...intradayLookup.textByValue.values()], ['6月29日\n09:10', '13:00', '18:00', '22:30'])

const intradayOffMinuteRows = rows([
  '2026-06-29T09:11:00',
  '2026-06-29T12:58:00',
  '2026-06-29T18:03:00',
  '2026-06-29T22:28:00',
])
const intradayOffMinuteLookup = buildAxisLabelLookup(intradayOffMinuteRows, '1min')
assert.deepEqual([...intradayOffMinuteLookup.textByValue.values()], ['6月29日\n09:11', '12:58', '18:03', '22:28'])

const partialIntradayTimeline = buildIntradayTimeline([
  { time: '2026-06-29T16:45:00', open: 876, high: 876.1, low: 875.9, close: 876 },
  { time: '2026-06-29T17:27:00', open: 875.8, high: 876, low: 875.7, close: 875.9 },
])
assert.equal(partialIntradayTimeline.data[0].time, '2026-06-29T16:45:00.000')
assert.equal(partialIntradayTimeline.data[partialIntradayTimeline.data.length - 1].time, '2026-06-29T17:27:00.000')
assert.equal(partialIntradayTimeline.data.length, 43)
assert.equal(partialIntradayTimeline.sessionOpen, '2026-06-29T16:45:00.000')
assert.equal(partialIntradayTimeline.sessionClose, '2026-06-29T17:27:00.000')
assert.equal(partialIntradayTimeline.data[0].close, 876)
assert.equal(partialIntradayTimeline.data[42].close, 875.9)
assert.equal(partialIntradayTimeline.data[30].close, undefined)

const timelineWithEarlyOpen = buildIntradayTimeline([
  { time: '2026-06-29T09:11:00', open: 865, high: 866, low: 864, close: 865.5 },
])
assert.equal(timelineWithEarlyOpen.data[0].time, '2026-06-29T09:11:00.000')
assert.equal(timelineWithEarlyOpen.data[timelineWithEarlyOpen.data.length - 1].time, '2026-06-29T09:11:00.000')

const timelineWithMidnightFeed = buildIntradayTimeline([
  { time: '2026-06-29T00:00:00', open: 880, high: 880, low: 880, close: 880 },
  { time: '2026-06-29T09:10:00', open: 865, high: 866, low: 864, close: 865.5 },
])
assert.equal(timelineWithMidnightFeed.data[0].time, '2026-06-29T00:00:00.000')
assert.equal(timelineWithMidnightFeed.data[timelineWithMidnightFeed.data.length - 1].time, '2026-06-29T09:10:00.000')

const timelineAcrossMidnight = buildIntradayTimeline([
  { time: '2026-06-29T09:00:00', open: 865, high: 866, low: 864, close: 865.5 },
  { time: '2026-06-30T01:30:00', open: 878, high: 879, low: 877, close: 878.5 },
])
assert.equal(timelineAcrossMidnight.data[0].time, '2026-06-29T09:00:00.000')
assert.equal(timelineAcrossMidnight.data[timelineAcrossMidnight.data.length - 1].time, '2026-06-30T01:30:00.000')
assert.equal(timelineAcrossMidnight.data.length, 991)

const shortIntradayRange = buildIntradayViewportRange(buildIntradayTimeline([
  { time: '2026-06-29T17:46:00', open: 875, high: 875, low: 875, close: 875 },
  { time: '2026-06-29T19:33:00', open: 879, high: 879, low: 879, close: 879 },
]).data)
assert.deepEqual(shortIntradayRange, { start: 0, end: 107, focused: false })

const fullIntradayRange = buildIntradayViewportRange(buildIntradayTimeline([
  { time: '2026-06-29T09:10:00', open: 865, high: 866, low: 864, close: 865.5 },
  { time: '2026-06-29T18:00:00', open: 878, high: 879, low: 877, close: 878.5 },
]).data)
assert.deepEqual(fullIntradayRange, { start: 0, end: 530, focused: false })

const extremaRows = [
  { time: '2026-06-29T09:10:00', open: 867, high: 869.1, low: 863.43, close: 866.5 },
  { time: '2026-06-29T13:00:00', open: 870, high: 873.2, low: 869.3, close: 871.1 },
  { time: '2026-06-29T15:30:00', open: 878, high: 880.25, low: 876.2, close: 879.4 },
  { time: '2026-06-29T17:20:00', open: 876, high: 877.8, low: 875.4, close: 876.6 },
]
assert.deepEqual(buildVisibleExtrema(extremaRows, 0, 3), {
  high: { index: 2, value: 880.25 },
  low: { index: 0, value: 863.43 },
})
assert.deepEqual(buildVisibleExtrema(extremaRows, 1, 3), {
  high: { index: 2, value: 880.25 },
  low: { index: 1, value: 869.3 },
})

const hourly = rows([
  '2026-06-29T00:00:00',
  '2026-06-29T01:00:00',
  '2026-06-29T02:00:00',
  '2026-06-29T03:00:00',
  '2026-06-29T04:00:00',
  '2026-06-29T05:00:00',
  '2026-06-29T06:00:00',
  '2026-06-29T07:00:00',
  '2026-06-29T08:00:00',
  '2026-06-29T09:00:00',
])
const hourlyIndexes = buildAxisLabelIndexes(hourly, '1h')
assert.deepEqual([...hourlyIndexes], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
assert.deepEqual(buildAxisLabelTexts(hourly, '1h', hourlyIndexes), [
  '6月29日\n00:00',
  '01:00',
  '02:00',
  '03:00',
  '04:00',
  '05:00',
  '06:00',
  '07:00',
  '08:00',
  '09:00',
])

const crossDay = rows([
  '2026-06-29T21:00:00',
  '2026-06-29T22:00:00',
  '2026-06-29T23:00:00',
  '2026-06-30T00:00:00',
  '2026-06-30T01:00:00',
  '2026-06-30T02:00:00',
])
const crossDayIndexes = buildAxisLabelIndexes(crossDay, '1h')
assert.deepEqual([...crossDayIndexes], [0, 1, 2, 3, 4, 5])
assert.deepEqual(buildAxisLabelTexts(crossDay, '1h', crossDayIndexes), [
  '6月29日\n21:00',
  '22:00',
  '23:00',
  '6月30日\n00:00',
  '01:00',
  '02:00',
])

const daily = rows([
  '2026-06-27T00:00:00',
  '2026-06-28T00:00:00',
  '2026-06-29T00:00:00',
])
const dailyIndexes = buildAxisLabelIndexes(daily, '1day')
assert.deepEqual(buildAxisLabelTexts(daily, '1day', dailyIndexes), ['2026\n6/27', '6/28', '6/29'])

const monthly = rows([
  '2025-11-01T00:00:00',
  '2025-12-01T00:00:00',
  '2026-01-01T00:00:00',
  '2026-02-01T00:00:00',
  '2026-03-01T00:00:00',
])
const monthlyIndexes = buildAxisLabelIndexes(monthly, '1month')
assert.deepEqual(buildAxisLabelTexts(monthly, '1month', monthlyIndexes), ['2025\n11月', '12月', '2026\n1月', '2月', '3月'])

const visibleHourly = hourlyRows(24)
assert.deepEqual([...buildAxisLabelIndexes(visibleHourly, '1h', { startIndex: 4, endIndex: 13 })], [
  4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
])
const shiftedHourlyLookup = buildAxisLabelLookup(visibleHourly, '1h', { startIndex: 14, endIndex: 23 })
const shiftedFirstValue = formatFullTime(visibleHourly[14].time, '1h')
assert.equal(shiftedHourlyLookup.values.size, AXIS_TICK_COUNT)
assert.equal(shiftedHourlyLookup.values.has(shiftedFirstValue), true)
assert.equal(shiftedHourlyLookup.textByValue.get(shiftedFirstValue), '6月26日\n20:00')
assert.equal(shiftedHourlyLookup.values.has(formatFullTime(visibleHourly[0].time, '1h')), false)

const offsetHourly = rows(Array.from({ length: 10 }, (_, i) => {
  const d = new Date('2026-06-29T09:11:16')
  d.setHours(d.getHours() + i)
  return d.toISOString()
}))
const offsetHourlyLookup = buildAxisLabelLookup(offsetHourly, '1h')
assert.equal(offsetHourlyLookup.values.size, AXIS_TICK_COUNT)
assert.equal(offsetHourlyLookup.textByValue.get(formatFullTime(offsetHourly[0].time, '1h')), '6月29日\n09:00')
assert.equal(offsetHourlyLookup.textByValue.get(formatFullTime(offsetHourly[9].time, '1h')), '18:00')

const roughMonthly = rows([
  '2025-08-03T18:08:19',
  '2025-09-02T18:08:19',
  '2025-10-02T18:08:19',
  '2025-11-01T18:08:19',
  '2025-12-01T18:08:19',
  '2025-12-31T18:08:19',
  '2026-01-30T18:08:19',
  '2026-03-01T18:08:19',
  '2026-03-31T18:08:19',
  '2026-04-30T18:08:19',
  '2026-05-30T18:08:19',
  '2026-06-29T18:08:19',
])
const roughMonthlyLabels = [...buildAxisLabelLookup(roughMonthly, '1month').textByValue.values()]
assert.equal(roughMonthlyLabels.length, AXIS_TICK_COUNT)
assert.deepEqual(roughMonthlyLabels, ['2025\n9月', '10月', '11月', '12月', '2026\n1月', '2月', '3月', '4月', '5月', '6月'])

assert.equal(formatFullTime('2026-06-29T15:00:00', '1h'), '2026-06-29 15:00')
assert.equal(formatDataZoomLabel('2026-06-29T15:00:00', '1h'), '6/29 15:00')

assert.equal(buildViewportResetKey({ period: '1min', sourceKey: 'icbc' }), '1min::icbc')
assert.equal(buildViewportResetKey({ period: '1min', sourceKey: 'jdjygold_zheshang' }), '1min::jdjygold_zheshang')
assert.notEqual(
  buildViewportResetKey({ period: '1min', sourceKey: 'icbc' }),
  buildViewportResetKey({ period: '1min', sourceKey: 'jdjygold_zheshang' }),
)
assert.notEqual(
  buildViewportResetKey({ period: '1min', sourceKey: 'icbc' }),
  buildViewportResetKey({ period: '1day', sourceKey: 'icbc' }),
)

assert.equal(buildZoomMinValueSpan('1min', 200), 29)
assert.equal(buildZoomMinValueSpan('1day', 40), 6)
assert.equal(buildZoomMinValueSpan('1month', 40), 5)
assert.equal(buildZoomMinValueSpan('1day', 3), 2)

const yAxis = buildYAxisScale([884.12, 886.8, 890.97], 883.5)
assert.equal(yAxis.splitNumber, Y_AXIS_TICK_COUNT - 1)
assert.equal(yAxis.max - yAxis.min, yAxis.interval * (Y_AXIS_TICK_COUNT - 1))
assert.ok(yAxis.min <= 883.5)
assert.ok(yAxis.max >= 890.97)

const compactYAxis = buildYAxisScaleForRange(extremaRows, 0, 3, null, 4)
assert.equal(compactYAxis.splitNumber, 3)
assert.equal(compactYAxis.max - compactYAxis.min, compactYAxis.interval * 3)
assert.ok(compactYAxis.min <= 863.43)
assert.ok(compactYAxis.max >= 880.25)
