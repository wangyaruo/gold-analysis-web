import { expect, test } from '@playwright/test'

const snapshot = {
  price: {
    symbol: 'XAUUSD',
    value: 2368.42,
    unit: 'USD/oz',
    display_value: 552.05,
    display_unit: 'CNY/g',
    timestamp: new Date().toISOString(),
    source: 'e2e-fixture',
  },
  history: Array.from({ length: 30 }, (_, index) => ({
    index: index + 1,
    price: 2340 + index * 0.9 + Math.sin(index / 2) * 2,
    display_price: 545 + index * 0.2 + Math.sin(index / 2) * 0.4,
  })),
  indicators: {
    stop_loss: {
      indicator_type: 'SMA',
      period: 20,
      multiplier: 2,
      indicator_value: 2352.12,
      volatility: 5.2,
      stop_loss: 2341.72,
      display_stop_loss: 545.82,
      display_unit: 'CNY/g',
    },
    ma_cross: 'golden_cross',
    cross_strength: 0.014,
    bollinger: {
      breakout: 'upper',
      upper_band: 2362.3,
      lower_band: 2320.4,
    },
  },
  sentiment: {
    label: 'positive',
    score: 2,
    positive_hits: ['rallies', 'central bank buying'],
    negative_hits: [],
    article_count: 2,
  },
  recommendation: {
    action: 'buy',
    confidence: 1,
    reasons: ['MA golden cross', 'price broke above Bollinger upper band', 'news sentiment is positive'],
    risks: [],
  },
  predicted_range: {
    low: 545.84,
    high: 556.76,
    range_percent: 0.02,
    unit: 'CNY/g',
  },
  refresh_seconds: 2,
  max_data_delay_seconds: 5,
}

const klineBaseTime = new Date()
klineBaseTime.setHours(12, 0, 0, 0)

const klines = Array.from({ length: 60 }, (_, index) => {
  const close = 551 + index * 0.03 + Math.sin(index / 5) * 0.35
  const open = close - 0.08
  return {
    time: new Date(klineBaseTime.getTime() - (59 - index) * 60_000).toISOString(),
    open,
    high: close + 0.18,
    low: open - 0.16,
    close,
  }
})

const reviewItems = Array.from({ length: 30 }, (_, index) => {
  const day = index + 1
  const missing = [7, 14, 19, 20, 21, 28].includes(day)
  const date = `2026-06-${String(day).padStart(2, '0')}`
  if (missing) {
    return {
      date,
      has_data: false,
      source: 'none',
      open: null,
      high: null,
      low: null,
      close: null,
      change_percent: null,
      intraday_range_percent: null,
    }
  }
  const open = 980 - index * 3
  const change = day === 12 ? 0.0274 : day === 10 ? -0.0357 : (index % 3 === 0 ? 0.006 : -0.009)
  const close = open * (1 + change)
  return {
    date,
    has_data: true,
    source: 'seed',
    open,
    high: Math.max(open, close) + 4,
    low: Math.min(open, close) - 5,
    close,
    change_percent: change,
    intraday_range_percent: 0.018,
  }
})

const reviewPayload = {
  key: 'silver',
  source: 'silver',
  label: '白银30日行情',
  theme: '#7d8da1',
  unit: 'CNY/kg',
  days: 30,
  generated_at: '2026-07-01T09:00:00',
  has_seed: true,
  items: reviewItems,
  summary: {
    trading_days: 21,
    missing_days: 9,
    up_days: 8,
    down_days: 13,
    flat_days: 0,
    best_day: reviewItems[11],
    worst_day: reviewItems[9],
    cumulative_change_percent: -0.1117,
  },
  weekly: [
    { label: '第1周', start_date: '2026-06-01', end_date: '2026-06-07', change_percent: -0.0279, trading_days: 5 },
    { label: '第2周', start_date: '2026-06-08', end_date: '2026-06-14', change_percent: -0.0309, trading_days: 5 },
    { label: '第3周', start_date: '2026-06-15', end_date: '2026-06-21', change_percent: -0.011, trading_days: 4 },
    { label: '第4周', start_date: '2026-06-22', end_date: '2026-06-28', change_percent: -0.0238, trading_days: 5 },
    { label: '第5周', start_date: '2026-06-29', end_date: '2026-06-30', change_percent: -0.0019, trading_days: 2 },
  ],
}

const platinumReviewPayload = {
  key: 'platinum',
  source: 'platinum',
  label: '铂金30日行情',
  theme: '#7f6bb2',
  unit: 'CNY/g',
  days: 30,
  generated_at: '2026-07-01T09:00:00',
  has_seed: true,
  items: reviewItems,
  summary: {
    trading_days: 24,
    missing_days: 6,
    up_days: 8,
    down_days: 16,
    flat_days: 0,
    best_day: reviewItems[11],
    worst_day: reviewItems[9],
    cumulative_change_percent: -0.1117,
  },
  weekly: [
    { label: '第1周', start_date: '2026-06-01', end_date: '2026-06-07', change_percent: -0.0279, trading_days: 6 },
    { label: '第2周', start_date: '2026-06-08', end_date: '2026-06-14', change_percent: -0.0309, trading_days: 6 },
    { label: '第3周', start_date: '2026-06-15', end_date: '2026-06-21', change_percent: -0.011, trading_days: 4 },
    { label: '第4周', start_date: '2026-06-22', end_date: '2026-06-28', change_percent: -0.0238, trading_days: 6 },
    { label: '第5周', start_date: '2026-06-29', end_date: '2026-06-30', change_percent: -0.0019, trading_days: 2 },
  ],
}

const icbcReviewItems = Array.from({ length: 30 }, (_, index) => {
  const day = index + 1
  const date = `2026-06-${String(day).padStart(2, '0')}`
  const flat = [6, 7, 13, 14, 20, 21, 27, 28].includes(day)
  const change = flat ? 0 : day === 30 ? 0.022 : day === 10 ? -0.0369 : (index % 4 === 0 ? 0.008 : -0.01)
  const open = 990 - index * 3.5
  const close = open * (1 + change)
  return {
    date,
    has_data: true,
    source: 'seed',
    open,
    high: Math.max(open, close) + 3,
    low: Math.min(open, close) - 4,
    close,
    change_percent: change,
    intraday_range_percent: Math.abs(change) + 0.01,
  }
})

const icbcReviewPayload = {
  key: 'gold',
  source: 'gold',
  label: '黄金30日行情',
  theme: '#c89a2b',
  unit: 'CNY/g',
  days: 30,
  generated_at: '2026-07-01T09:00:00',
  has_seed: true,
  items: icbcReviewItems,
  summary: {
    trading_days: 30,
    missing_days: 0,
    up_days: 7,
    down_days: 15,
    flat_days: 8,
    best_day: icbcReviewItems[29],
    worst_day: icbcReviewItems[9],
    cumulative_change_percent: -0.1055,
  },
  weekly: [
    { label: '第1周', start_date: '2026-06-01', end_date: '2026-06-07', change_percent: -0.0303, trading_days: 7 },
    { label: '第2周', start_date: '2026-06-08', end_date: '2026-06-14', change_percent: -0.0369, trading_days: 7 },
    { label: '第3周', start_date: '2026-06-15', end_date: '2026-06-21', change_percent: -0.0209, trading_days: 7 },
    { label: '第4周', start_date: '2026-06-22', end_date: '2026-06-28', change_percent: -0.0092, trading_days: 7 },
    { label: '第5周', start_date: '2026-06-29', end_date: '2026-06-30', change_percent: 0.0126, trading_days: 2 },
  ],
}

function emptyReview(source = 'yahoo_finance') {
  return {
    source,
    label: source,
    unit: 'CNY/g',
    days: 30,
    generated_at: '2026-07-01T09:00:00',
    has_seed: false,
    items: Array.from({ length: 30 }, (_, index) => ({
      date: `2026-06-${String(index + 1).padStart(2, '0')}`,
      has_data: false,
      source: 'none',
    })),
    summary: {
      trading_days: 0,
      missing_days: 30,
      up_days: 0,
      down_days: 0,
      flat_days: 0,
      best_day: null,
      worst_day: null,
      cumulative_change_percent: null,
    },
    weekly: [],
  }
}

const monthlyReviewsPayload = {
  days: 30,
  generated_at: '2026-07-01T09:00:00',
  items: [icbcReviewPayload, reviewPayload, platinumReviewPayload],
}

let monthlyReviewsRequestCount = 0
let snapshotRequestCount = 0
let klineRequestCount = 0
let latestKlineSource = ''
let alertRules = []
let testEmailCount = 0

test.beforeEach(async ({ page }) => {
  monthlyReviewsRequestCount = 0
  snapshotRequestCount = 0
  klineRequestCount = 0
  latestKlineSource = ''
  alertRules = []
  testEmailCount = 0

  await page.route('**/api/config/public', async (route) => {
    await route.fulfill({
      json: {
        realtime: { frontend_refresh_seconds: 2, max_data_delay_seconds: 5 },
        portfolio_defaults: { buy_price: 540, quantity: 2 },
        display: { currency: 'CNY', unit: 'g' },
        data_sources: {
          active: 'icbc',
          fallback: 'demo',
          options: [
            { key: 'icbc', label: '工商银行积存金', requires_api_key: false },
            { key: 'jdjygold_zheshang', label: '浙商银行积存金', requires_api_key: false },
          ],
        },
        alerts: {
          enabled: true,
          check_interval_seconds: 2,
          predicted_breakout_step_cny_g: 2,
          default_source: 'icbc',
          smtp_configured: true,
        },
      },
    })
  })

  await page.route('**/api/alerts/rules**', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') {
      await route.fulfill({ json: { rules: alertRules, smtp_configured: true } })
      return
    }
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData())
      const rule = {
        id: alertRules.length + 1,
        enabled: body.enabled ?? true,
        source: body.source || 'icbc',
        recipient_email: body.recipient_email,
        target_high_price: Number(body.target_high_price),
        target_low_price: Number(body.target_low_price),
        notify_on_custom_high: Boolean(body.notify_on_custom_high),
        notify_on_custom_low: Boolean(body.notify_on_custom_low),
        notify_on_predicted_high: Boolean(body.notify_on_predicted_high),
        notify_on_predicted_low: Boolean(body.notify_on_predicted_low),
        state: null,
      }
      alertRules = [rule]
      await route.fulfill({ json: { rule } })
      return
    }
    await route.fulfill({ json: { deleted: true } })
  })

  await page.route('**/api/alerts/test-email', async (route) => {
    testEmailCount += 1
    await route.fulfill({ json: { sent: true } })
  })

  await page.route('**/api/market/klines**', async (route) => {
    klineRequestCount += 1
    latestKlineSource = new URL(route.request().url()).searchParams.get('source') || ''
    await route.fulfill({
      json: {
        period: '1min',
        display_unit: 'CNY/g',
        candles: klines,
      },
    })
  })

  await page.route('**/api/market/monthly-reviews**', async (route) => {
    monthlyReviewsRequestCount += 1
    await route.fulfill({
      json: monthlyReviewsPayload,
    })
  })

  await page.route('**/api/market/snapshot**', async (route) => {
    snapshotRequestCount += 1
    const source = new URL(route.request().url()).searchParams.get('source') || 'icbc'
    await route.fulfill({
      json: {
        ...snapshot,
        price: {
          ...snapshot.price,
          source,
        },
      },
    })
  })

  await page.route('**/api/portfolio/pnl', async (route) => {
    const request = route.request()
    const body = JSON.parse(request.postData())
    const amount = (body.current_price - body.buy_price) * body.quantity
    const percent = (amount / (body.buy_price * body.quantity)) * 100
    await route.fulfill({
      json: {
        amount,
        percent,
      },
    })
  })
})

test('renders realtime market snapshot and recommendation', async ({ page }) => {
  await page.setViewportSize({ width: 690, height: 763 })
  await page.goto('/')

  await expect(page.getByTestId('connection-status')).toContainText('已连接')
  await expect(page.getByTestId('current-price')).toContainText('552.05')
  await expect(page.getByTestId('price-source-name')).toContainText('工商银行积存金')
  await expect(page.getByTestId('predicted-low')).toContainText('545.84')
  await expect(page.getByTestId('predicted-high')).toContainText('556.76')
  await expect(page.locator('.price-meta')).toContainText('刷新 2s')
  await expect(page.locator('.brand-logo-img')).toBeVisible()
  await expect(page.locator('.asset-icon-tile img')).toHaveCount(2)
  await expect(page.locator('.period-tab')).toHaveText(['分线', '日线', '月线'])
  await expect(page.locator('.chart-card canvas')).toBeVisible()
  await expect(page.getByTestId('recommendation-action')).toContainText('建议买入')
  await expect(page.getByTestId('stop-loss')).toContainText('545.82')
  await expect(page.getByTestId('sentiment-value')).toContainText('68')
  await expect(page.getByTestId('sentiment-mood')).toContainText('偏多')
  await expect(page.getByTestId('sentiment-preview')).toContainText('情绪分 +2')
  await expect(page.getByTestId('sentiment-preview')).toContainText('rallies')
  const dashboardBox = await page.locator('.dashboard-screen').boundingBox()
  expect(dashboardBox.height).toBeLessThanOrEqual(763)
  const reviewTop = await page.locator('[data-testid="monthly-review"]').first().evaluate((node) => node.getBoundingClientRect().top)
  expect(reviewTop).toBeGreaterThan(700)
})

test('updates sentiment preview when sentiment zones are clicked', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('sentiment-preview')).toContainText('看多')
  await page.getByTestId('sentiment-zone-bearish').click()

  await expect(page.getByTestId('sentiment-preview')).toContainText('看空')
  await expect(page.getByTestId('sentiment-preview')).toContainText('已锁定')

  await page.getByTestId('sentiment-zone-bullish').click()

  await expect(page.getByTestId('sentiment-preview')).toContainText('看多')
  await expect(page.getByTestId('sentiment-preview')).not.toContainText('已锁定')
})

test('switches the kline data source without changing 30 day commodity reviews', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('price-source-select')).toBeVisible()
  await expect(page.getByTestId('price-source-name')).toContainText('工商银行积存金')
  expect(monthlyReviewsRequestCount).toBe(1)

  const switchedKlineResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/market/klines' && url.searchParams.get('source') === 'jdjygold_zheshang'
  })
  await page.getByTestId('price-source-select').selectOption('jdjygold_zheshang')
  await switchedKlineResponse

  await expect(page.getByTestId('price-source-name')).toContainText('浙商银行积存金')
  expect(latestKlineSource).toBe('jdjygold_zheshang')
  expect(monthlyReviewsRequestCount).toBe(1)
  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('黄金30日行情')
  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('白银30日行情')
  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('铂金30日行情')
})

test('resets only the kline chart when reset control is clicked', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('kline-reset-button')).toBeVisible()
  const actionOrder = await page.locator('.chart-actions').evaluate((node) =>
    Array.from(node.children).map((child) => child.getAttribute('data-testid') || child.className)
  )
  expect(actionOrder[0]).toBe('kline-reset-button')
  expect(actionOrder[1]).toBe('period-tabs')

  const beforeKlines = klineRequestCount
  const beforeSnapshots = snapshotRequestCount
  const beforeReviews = monthlyReviewsRequestCount

  await page.getByTestId('kline-reset-button').click()

  await expect.poll(() => klineRequestCount).toBe(beforeKlines + 1)
  expect(snapshotRequestCount).toBe(beforeSnapshots)
  expect(monthlyReviewsRequestCount).toBe(beforeReviews)
})

test('shows gold silver and platinum 30 day reviews in one panel', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('黄金30日行情')
  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('白银30日行情')
  await expect(page.getByTestId('monthly-reviews-panel')).toContainText('铂金30日行情')
  await expect(page.locator('.monthly-review canvas')).toHaveCount(9)
  await expect(page.locator('[data-testid="monthly-review-preview"]').first()).toContainText('2026-06-30')
})

test('calculates portfolio pnl from user inputs', async ({ page }) => {
  await page.goto('/')

  await page.getByTestId('buy-price').fill('540')
  await page.getByTestId('quantity').fill('3')
  await page.getByRole('button', { name: /计算/ }).click()

  await expect(page.getByTestId('pnl-amount')).toContainText('36.15')
})

test('saves alert rule and sends test email', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByTestId('alert-panel')).toBeVisible()
  await expect(page.getByTestId('alert-panel')).toContainText('预设清仓价格')
  await expect(page.getByTestId('alert-panel')).toContainText('预设抄底价格')
  await expect(page.getByTestId('alert-panel')).toContainText('清仓价')
  await expect(page.getByTestId('alert-panel')).toContainText('抄底价')
  await expect(page.getByTestId('alert-enabled')).toBeChecked()
  await expect(page.getByTestId('alert-custom-high')).toBeChecked()
  await expect(page.getByTestId('alert-custom-low')).toBeChecked()
  await expect(page.getByTestId('alert-predicted-high')).toBeChecked()
  await expect(page.getByTestId('alert-predicted-low')).toBeChecked()
  await page.getByTestId('alert-email').fill('me@example.com')
  await page.getByTestId('alert-target-high').fill('900')
  await page.getByTestId('alert-target-low').fill('870')
  await page.getByTestId('alert-save').click()

  await expect(page.getByTestId('alert-status')).toContainText('已保存')
  expect(alertRules[0].recipient_email).toBe('me@example.com')
  expect(alertRules[0].target_high_price).toBe(900)
  expect(alertRules[0].notify_on_custom_high).toBe(true)

  await page.getByTestId('alert-test-email').click()

  await expect(page.getByTestId('alert-status')).toContainText('测试邮件已发送')
  expect(testEmailCount).toBe(1)
})
