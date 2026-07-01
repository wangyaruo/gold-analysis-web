import { formatApiError } from './utils/apiErrors.js'

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
    throw new Error(formatApiError(response, body))
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

export function getMarketFactors(source) {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  const query = params.toString()
  return request(`/api/market/factors${query ? `?${query}` : ''}`)
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

function alertSessionHeaders(sessionToken) {
  return sessionToken ? {'X-Alert-Session': sessionToken} : {}
}

export function requestAlertCode(email) {
  return request('/api/alerts/session/request-code', {
    method: 'POST',
    body: JSON.stringify({email}),
  })
}

export function verifyAlertCode(email, code) {
  return request('/api/alerts/session/verify', {
    method: 'POST',
    body: JSON.stringify({email, code}),
  })
}

export function getAlertRules(sessionToken) {
  return request('/api/alerts/rules', {
    headers: alertSessionHeaders(sessionToken),
  })
}

export function createAlertRule(payload, sessionToken) {
  return request('/api/alerts/rules', {
    method: 'POST',
    headers: alertSessionHeaders(sessionToken),
    body: JSON.stringify(payload),
  })
}

export function updateAlertRule(id, payload, sessionToken) {
  return request(`/api/alerts/rules/${id}`, {
    method: 'PUT',
    headers: alertSessionHeaders(sessionToken),
    body: JSON.stringify(payload),
  })
}

export function deleteAlertRule(id, sessionToken) {
  return request(`/api/alerts/rules/${id}`, {
    method: 'DELETE',
    headers: alertSessionHeaders(sessionToken),
  })
}

export function sendTestEmail(payload, sessionToken) {
  return request('/api/alerts/test-email', {
    method: 'POST',
    headers: alertSessionHeaders(sessionToken),
    body: JSON.stringify(payload),
  })
}
