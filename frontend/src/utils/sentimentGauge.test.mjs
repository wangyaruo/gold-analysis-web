import assert from 'node:assert/strict'
import {
  buildSentimentPreview,
  getSentimentSegment,
  sentimentScoreToGaugeValue,
  visibleSentimentHits,
} from './sentimentGauge.js'

assert.equal(sentimentScoreToGaugeValue(2), 68)
assert.equal(sentimentScoreToGaugeValue(-8), 0)
assert.equal(sentimentScoreToGaugeValue(9), 100)

assert.equal(getSentimentSegment(12).label, '极度看空')
assert.equal(getSentimentSegment(35).label, '看空')
assert.equal(getSentimentSegment(50).label, '中性')
assert.equal(getSentimentSegment(68).label, '看多')
assert.equal(getSentimentSegment(88).label, '极度看多')

assert.deepEqual(
  visibleSentimentHits({
    positive_hits: ['rallies', 'central bank buying', 'rate cut', 'safe haven demand'],
    negative_hits: ['strong dollar'],
  }),
  ['rallies', 'central bank buying', 'rate cut'],
)

const preview = buildSentimentPreview({
  value: 68,
  score: 2,
  articleCount: 2,
  positiveHits: ['rallies', 'central bank buying'],
  negativeHits: [],
})
assert.equal(preview.title, '看多')
assert.equal(preview.mood, '偏多')
assert.equal(preview.scoreText, '+2')
assert.equal(preview.articleText, '新闻样本 2 条')
assert.equal(preview.hitsText, 'rallies / central bank buying')

const emptyPreview = buildSentimentPreview({
  value: 50,
  score: 0,
  articleCount: 0,
  positiveHits: [],
  negativeHits: [],
})
assert.equal(emptyPreview.hitsText, '暂无关键词命中')
assert.equal(emptyPreview.articleText, '新闻样本 0 条')
