import assert from 'node:assert/strict'
import {
  buildReviewPreview,
  formatReviewPercent,
  hasReviewData,
  pickDefaultReviewItem,
  reviewBarColor,
} from './monthlyReview.js'

const rows = [
  { date: '2026-06-01', has_data: true, open: 988.61, high: 988.67, low: 970.63, close: 976.09, change_percent: -0.0127 },
  { date: '2026-06-02', has_data: true, open: 976.08, high: 988.76, low: 972.93, close: 981.08, change_percent: 0.0051 },
  { date: '2026-06-03', has_data: false, change_percent: null },
]

assert.equal(formatReviewPercent(0.0274), '+2.74%')
assert.equal(formatReviewPercent(-0.0357), '-3.57%')
assert.equal(formatReviewPercent(null), '--')
assert.equal(formatReviewPercent(undefined), '--')

assert.equal(reviewBarColor(rows[0]), '#e95a4f')
assert.equal(reviewBarColor(rows[1]), '#45a365')
assert.equal(reviewBarColor(rows[2]), '#d7d0c2')

assert.equal(hasReviewData(rows), true)
assert.equal(hasReviewData([{ date: '2026-06-01', has_data: false }]), false)
assert.equal(pickDefaultReviewItem(rows).date, '2026-06-02')
assert.equal(pickDefaultReviewItem([{ date: '2026-06-01', has_data: false }]), null)

assert.deepEqual(buildReviewPreview(rows[1], 'CNY/g'), {
  date: '2026-06-02',
  price: '981.08 CNY/g',
  range: '972.93 - 988.76 CNY/g',
  change: '+0.51%',
})
assert.deepEqual(buildReviewPreview(null, 'CNY/g'), {
  date: '--',
  price: '--',
  range: '--',
  change: '--',
})
