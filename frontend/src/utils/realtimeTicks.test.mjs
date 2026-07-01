import assert from 'node:assert/strict'
import { recordRealtimeTick } from './realtimeTicks.js'

const base = new Date('2026-07-01T10:00:10')

const first = recordRealtimeTick([], {
  sourceKey: 'icbc',
  time: '2026-07-01T10:00:00',
  price: 867.12,
}, { now: base, maxAgeMs: 60_000, maxPointsPerSource: 3 })

assert.deepEqual(first, [{
  sourceKey: 'icbc',
  time: '2026-07-01T10:00:00.000',
  price: 867.12,
}])

const pruned = recordRealtimeTick([
  { sourceKey: 'icbc', time: '2026-07-01T09:58:00', price: 866 },
  { sourceKey: 'icbc', time: '2026-07-01T09:59:40', price: 866.4 },
  { sourceKey: 'icbc', time: '2026-07-01T09:59:50', price: 866.8 },
  { sourceKey: 'icbc', time: '2026-07-01T10:00:00', price: 867 },
  { sourceKey: 'jdjygold_zheshang', time: '2026-07-01T10:00:00', price: 868 },
], {
  sourceKey: 'icbc',
  time: '2026-07-01T10:00:10',
  price: 867.2,
}, { now: base, maxAgeMs: 60_000, maxPointsPerSource: 3 })

assert.deepEqual(pruned, [
  { sourceKey: 'icbc', time: '2026-07-01T09:59:50.000', price: 866.8 },
  { sourceKey: 'icbc', time: '2026-07-01T10:00:00.000', price: 867 },
  { sourceKey: 'jdjygold_zheshang', time: '2026-07-01T10:00:00.000', price: 868 },
  { sourceKey: 'icbc', time: '2026-07-01T10:00:10.000', price: 867.2 },
])

const ignored = recordRealtimeTick(pruned, {
  sourceKey: 'icbc',
  time: '2026-07-01T10:00:12',
  price: Number.NaN,
}, { now: base })

assert.deepEqual(ignored, pruned)
