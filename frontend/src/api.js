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

export function getMarketSnapshot() {
  return request('/api/market/snapshot')
}

export function calculatePnl(payload) {
  return request('/api/portfolio/pnl', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
