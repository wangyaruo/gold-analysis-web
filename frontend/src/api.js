function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8318'
  }

  const { protocol, hostname } = window.location
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://127.0.0.1:8318'
  }

  return `${protocol}//${hostname}:8318`
}

const API_BASE_URL = resolveApiBaseUrl()
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'change-me-local-token'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_TOKEN}`,
      ...(options.headers || {}),
    },
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${body}`)
  }

  return response.json()
}

export function getPublicConfig() {
  return request('/api/config/public')
}

export function getMarketSnapshot(source) {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  const query = params.toString()
  return request(`/api/market/snapshot${query ? `?${query}` : ''}`)
}

export function getKlines(period, source) {
  const params = new URLSearchParams()
  if (period) params.set('period', period)
  if (source) params.set('source', source)
  const query = params.toString()
  return request(`/api/market/klines${query ? `?${query}` : ''}`)
}

export function getMonthlyReview(source, days = 30) {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (days) params.set('days', String(days))
  const query = params.toString()
  return request(`/api/market/monthly-review${query ? `?${query}` : ''}`)
}

export function getMonthlyReviews(days = 30) {
  const params = new URLSearchParams()
  if (days) params.set('days', String(days))
  const query = params.toString()
  return request(`/api/market/monthly-reviews${query ? `?${query}` : ''}`)
}

export function getPeriods() {
  return request('/api/market/periods')
}

export function calculatePnl(payload) {
  return request('/api/portfolio/pnl', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getAlertRules() {
  return request('/api/alerts/rules')
}

export function createAlertRule(payload) {
  return request('/api/alerts/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAlertRule(id, payload) {
  return request(`/api/alerts/rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAlertRule(id) {
  return request(`/api/alerts/rules/${id}`, {
    method: 'DELETE',
  })
}

export function sendTestEmail(payload) {
  return request('/api/alerts/test-email', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
