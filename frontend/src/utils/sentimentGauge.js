export const SENTIMENT_SEGMENTS = [
  {
    key: 'extreme_bearish',
    label: '极度看空',
    mood: '极度看空',
    min: 0,
    max: 20,
    color: '#d65b63',
    description: '负面信号密集，优先控制风险。',
  },
  {
    key: 'bearish',
    label: '看空',
    mood: '偏空',
    min: 20,
    max: 40,
    color: '#d29a48',
    description: '负面因素占优，等待情绪修复。',
  },
  {
    key: 'neutral',
    label: '中性',
    mood: '中性',
    min: 40,
    max: 60,
    color: '#d8c650',
    description: '多空信号接近，适合继续观察。',
  },
  {
    key: 'bullish',
    label: '看多',
    mood: '偏多',
    min: 60,
    max: 80,
    color: '#64b884',
    description: '正面线索占优，但仍需配合价格确认。',
  },
  {
    key: 'extreme_bullish',
    label: '极度看多',
    mood: '极度看多',
    min: 80,
    max: 100,
    color: '#279e78',
    description: '正面信号集中，关注追高风险。',
  },
]

export function sentimentScoreToGaugeValue(score) {
  const value = 50 + Number(score || 0) * 9
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function getSentimentSegment(value) {
  const n = Math.max(0, Math.min(100, Number(value) || 0))
  return SENTIMENT_SEGMENTS.find((item, index) => {
    if (index === SENTIMENT_SEGMENTS.length - 1) return n >= item.min && n <= item.max
    return n >= item.min && n < item.max
  }) || SENTIMENT_SEGMENTS[2]
}

export function getSentimentSegmentByKey(key) {
  return SENTIMENT_SEGMENTS.find((item) => item.key === key) || null
}

export function formatSentimentScore(score) {
  const n = Number(score || 0)
  return `${n >= 0 ? '+' : ''}${n}`
}

export function visibleSentimentHits(sentiment = {}, limit = 3) {
  const hits = [
    ...(sentiment.positive_hits || sentiment.positiveHits || []),
    ...(sentiment.negative_hits || sentiment.negativeHits || []),
  ]
  return hits.filter(Boolean).slice(0, limit)
}

export function buildSentimentPreview({
  value,
  score = 0,
  articleCount = 0,
  positiveHits = [],
  negativeHits = [],
  segmentKey = '',
}) {
  const segment = getSentimentSegmentByKey(segmentKey) || getSentimentSegment(value)
  const hits = visibleSentimentHits({ positiveHits, negativeHits })
  return {
    key: segment.key,
    title: segment.label,
    mood: getSentimentSegment(value).mood,
    color: segment.color,
    description: segment.description,
    scoreText: formatSentimentScore(score),
    articleText: `新闻样本 ${Number(articleCount || 0)} 条`,
    hits,
    hitsText: hits.length ? hits.join(' / ') : '暂无关键词命中',
  }
}
