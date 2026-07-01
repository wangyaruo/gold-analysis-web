export function formatApiError(response, body) {
  try {
    const parsed = JSON.parse(body)
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail.trim()
    }
  } catch {
    // Fall back to the raw response body below.
  }
  return `${response.status} ${response.statusText}: ${body}`
}
