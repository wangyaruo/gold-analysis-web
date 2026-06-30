export const REVIEW_COLORS = {
  up: '#45a365',
  down: '#e95a4f',
  flat: '#c89a2b',
  empty: '#d7d0c2',
}

export function formatReviewPercent(value) {
  if (value == null || value === '') return '--'
  const n = Number(value)
  if (!Number.isFinite(n)) return '--'
  const percent = n * 100
  return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`
}

export function reviewBarColor(item, themeColor = REVIEW_COLORS.flat) {
  if (!item?.has_data) return REVIEW_COLORS.empty
  const change = Number(item.change_percent)
  if (change > 0) return REVIEW_COLORS.up
  if (change < 0) return REVIEW_COLORS.down
  return themeColor || REVIEW_COLORS.flat
}

export function hasReviewData(items = []) {
  return items.some((item) => item?.has_data)
}

export function pickDefaultReviewItem(items = []) {
  const dataItems = items.filter((item) => item?.has_data)
  return dataItems.length ? dataItems[dataItems.length - 1] : null
}

export function buildReviewPreview(item, unit = 'CNY/g') {
  if (!item?.has_data) {
    return {
      date: '--',
      price: '--',
      range: '--',
      change: '--',
    }
  }
  return {
    date: item.date || '--',
    price: `${Number(item.close).toFixed(2)} ${unit}`,
    range: `${Number(item.low).toFixed(2)} - ${Number(item.high).toFixed(2)} ${unit}`,
    change: formatReviewPercent(item.change_percent),
  }
}
