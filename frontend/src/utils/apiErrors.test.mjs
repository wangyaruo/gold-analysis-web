import assert from 'node:assert/strict'

import { formatApiError } from './apiErrors.js'

const response = { status: 502, statusText: 'Bad Gateway' }

assert.equal(
  formatApiError(response, '{"detail":"SMTP服务器已登录，但发信阶段被服务商断开。"}'),
  'SMTP服务器已登录，但发信阶段被服务商断开。',
)

assert.equal(
  formatApiError(response, 'plain failure'),
  '502 Bad Gateway: plain failure',
)

console.log('apiErrors tests passed')
