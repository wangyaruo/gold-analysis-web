function parseTime(raw) {
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d
}

function localIsoSecond(date) {
  const d = new Date(date)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.000`
}

function normalizeTick(tick) {
  const time = parseTime(tick?.time || tick?.timestamp)
  const price = Number(tick?.price ?? tick?.display_price ?? tick?.close ?? tick?.value)
  if (!time || !Number.isFinite(price)) return null
  return {
    sourceKey: tick?.sourceKey || '',
    time: localIsoSecond(time),
    price,
  }
}

export function recordRealtimeTick(existingTicks, tick, options = {}) {
  const normalizedTick = normalizeTick(tick)
  if (!normalizedTick) return Array.isArray(existingTicks) ? existingTicks : []

  const now = parseTime(options.now) || new Date()
  const maxAgeMs = Number.isFinite(Number(options.maxAgeMs)) ? Number(options.maxAgeMs) : 24 * 60 * 60 * 1000
  const maxPointsPerSource = Number.isFinite(Number(options.maxPointsPerSource))
    ? Math.max(1, Math.floor(Number(options.maxPointsPerSource)))
    : 12_000
  const cutoff = now.getTime() - maxAgeMs
  const byKey = new Map()

  ;[...(Array.isArray(existingTicks) ? existingTicks : []), normalizedTick].forEach((raw) => {
    const item = normalizeTick(raw)
    if (!item) return
    const time = parseTime(item.time)
    if (!time || time.getTime() < cutoff) return
    byKey.set(`${item.sourceKey}::${item.time}`, item)
  })

  const grouped = new Map()
  Array.from(byKey.values()).forEach((item) => {
    if (!grouped.has(item.sourceKey)) grouped.set(item.sourceKey, [])
    grouped.get(item.sourceKey).push(item)
  })

  return Array.from(grouped.values())
    .flatMap((items) => items
      .sort((a, b) => Number(parseTime(a.time)) - Number(parseTime(b.time)))
      .slice(-maxPointsPerSource))
    .sort((a, b) => {
      const byTime = Number(parseTime(a.time)) - Number(parseTime(b.time))
      return byTime || a.sourceKey.localeCompare(b.sourceKey)
    })
}
