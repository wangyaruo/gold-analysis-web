import assert from 'node:assert/strict'
import { buildTodayRange } from './dayRange.js'

const now = new Date('2026-06-29T16:30:00')

const candles = [
  { time: '2026-06-28T23:58:00', high: 999, low: 111, close: 555 },
  { time: '2026-06-29T09:30:00', high: 887.2, low: 886.4, close: 886.9 },
  { time: '2026-06-29T10:30:00', high: 888.1, low: 886.8, close: 887.6 },
  { time: '2026-06-30T00:01:00', high: 1000, low: 100, close: 600 },
]

assert.deepEqual(buildTodayRange(candles, 885.9, now), {
  low: 885.9,
  high: 888.1,
})

assert.deepEqual(buildTodayRange(candles, 889.2, now), {
  low: 886.4,
  high: 889.2,
})

assert.deepEqual(buildTodayRange(
  [{ time: '2026-06-29T16:00:00', high: 870, low: 866, close: 867 }],
  866.64,
  now,
  { low: 865.39, high: 881.56 },
), {
  low: 865.39,
  high: 881.56,
})

assert.deepEqual(buildTodayRange([], 882.2, now, { low: 865.39, high: 881.56 }), {
  low: 865.39,
  high: 882.2,
})

assert.equal(buildTodayRange([], 886.7, now), null)
