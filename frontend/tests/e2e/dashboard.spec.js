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

const factorsPayload = {
  generated_at: '2026-07-02T10:00:00+08:00',
  basis: '银行积存金 CNY/g',
  overall_bias: { signal: 'positive', score: 1.8 },
  items: [
    {
      key: 'bank_price',
      label: '银行积存金',
      value: 552.05,
      change: 4.7,
      unit: 'CNY/g',
      signal: 'positive',
      strength: 4.7,
      source_name: '工商银行积存金',
      updated_at: '2026-07-02T10:00:00+08:00',
      explanation: '当前银行报价较前值上行，对人民币计价积存金偏利好。',
      status: 'ok',
    },
    {
      key: 'real_yield',
      label: '美国实际利率',
      value: 2.16,
      change: -0.02,
      unit: '%',
      signal: 'positive',
      strength: 2.0,
      source_name: 'FRED DFII10',
      updated_at: '2026-06-29',
      explanation: '实际利率下行会降低持有黄金的机会成本。',
      status: 'ok',
    },
    {
      key: 'usd_index',
      label: '美元指数',
      value: 120.89,
      change: -0.17,
      unit: '',
      signal: 'positive',
      strength: 1.7,
      source_name: 'FRED DTWEXBGS',
      updated_at: '2026-06-26',
      explanation: '美元走弱通常减轻国际金价压力。',
      status: 'ok',
    },
    {
      key: 'usd_cny',
      label: '美元兑人民币',
      value: 6.798,
      change: 0.02,
      unit: '',
      signal: 'positive',
      strength: 1.5,
      source_name: 'FRED DEXCHUS',
      updated_at: '2026-06-26',
      explanation: '美元兑人民币上行会抬高人民币计价黄金。',
      status: 'ok',
    },
    {
      key: 'sge_au9999',
      label: '上金所Au99.99',
      value: 890,
      change: 8,
      unit: 'CNY/g',
      signal: 'positive',
      strength: 1.3,
      source_name: '上海黄金交易所',
      updated_at: '2026-07-02',
      explanation: '境内黄金现货上行，对银行积存金报价形成支撑。',
      status: 'ok',
    },
    {
      key: 'vix',
      label: '避险波动率',
      value: 16.45,
      change: -1.2,
      unit: '',
      signal: 'negative',
      strength: 1.1,
      source_name: 'FRED VIXCLS',
      updated_at: '2026-06-30',
      explanation: '波动率回落代表避险需求降温。',
      status: 'ok',
    },
    {
      key: 'central_bank_news',
      label: '央行购金',
      value: null,
      change: null,
      unit: '',
      signal: 'positive',
      strength: 0.7,
      source_name: 'NewsAPI',
      updated_at: '2026-07-02T10:00:00+08:00',
      explanation: '新闻命中央行购金关键词。',
      status: 'ok',
    },
    {
      key: 'xau_usd',
      label: '国际金价',
      value: null,
      change: null,
      unit: 'USD/oz',
      signal: 'neutral',
      strength: 0,
      source_name: 'Twelve Data XAU/USD',
      updated_at: null,
      explanation: '国际金价源未配置。',
      status: 'stale',
    },
    {
      key: 'inflation_expectation',
      label: '通胀预期',
      value: null,
      change: null,
      unit: '%',
      signal: 'neutral',
      strength: 0,
      source_name: 'FRED T10YIE',
      updated_at: null,
      explanation: '通胀预期数据延迟。',
      status: 'stale',
    },
    {
      key: 'rate_news',
      label: '利率新闻',
      value: null,
      change: null,
      unit: '',
      signal: 'neutral',
      strength: 0,
      source_name: 'NewsAPI',
      updated_at: null,
      explanation: '暂无明确利率新闻方向。',
      status: 'stale',
    },
    {
      key: 'fed_policy',
      label: '美联储政策',
      value: null,
      change: null,
      unit: '',
      signal: 'neutral',
      strength: 0,
      source_name: 'FRED/NewsAPI',
      updated_at: null,
      explanation: '政策数据延迟。',
      status: 'stale',
    },
    {
      key: 'risk_appetite',
      label: '风险偏好',
      value: null,
      change: null,
      unit: '',
      signal: 'neutral',
      strength: 0,
      source_name: 'FRED VIXCLS',
      updated_at: null,
      explanation: '风险偏好数据延迟。',
      status: 'stale',
    },
  ],
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
let factorRequestCount = 0
let klineRequestCount = 0
let latestKlineSource = ''
let latestFactorSource = ''
let alertRules = []
let testEmailCount = 0
let alertSessionToken = ''
let requestCodeCount = 0
let verifyCodeCount = 0
let lastAlertRulePayload = null
let lastAlertRuleSession = ''
let lastTestEmailPayload = null
let lastTestEmailSession = ''

test.beforeEach(async ({ page }) => {
  monthlyReviewsRequestCount = 0
  snapshotRequestCount = 0
  factorRequestCount = 0
  klineRequestCount = 0
  latestKlineSource = ''
  latestFactorSource = ''
  alertRules = []
  testEmailCount = 0
  alertSessionToken = ''
  requestCodeCount = 0
  verifyCodeCount = 0
  lastAlertRulePayload = null
  lastAlertRuleSession = ''
  lastTestEmailPayload = null
  lastTestEmailSession = ''

  await page.addInitScript(() => {
    window.localStorage.clear()
  })

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
    const session = request.headers()['x-alert-session'] || ''
    if (session !== alertSessionToken) {
      await route.fulfill({ status: 401, json: { detail: 'alert session is required' } })
      return
    }
    if (request.method() === 'GET') {
      await route.fulfill({ json: { rules: alertRules, smtp_configured: true } })
      return
    }
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData())
      lastAlertRulePayload = body
      lastAlertRuleSession = session
      const rule = {
        id: alertRules.length + 1,
        enabled: body.enabled ?? true,
        source: body.source || 'icbc',
        recipient_email: 'me***@example.com',
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

  await page.route('**/api/alerts/session/request-code', async (route) => {
    requestCodeCount += 1
    await route.fulfill({
      json: {
        sent: true,
        subscriber: { email: 'me***@example.com' },
      },
    })
  })

  await page.route('**/api/alerts/session/verify', async (route) => {
    verifyCodeCount += 1
    const body = JSON.parse(route.request().postData())
    expect(body.email).toBe('me@example.com')
    expect(body.code).toBe('123456')
    alertSessionToken = 'session-token-a'
    await route.fulfill({
      json: {
        session_token: alertSessionToken,
        subscriber: { email: 'me***@example.com' },
      },
    })
  })

  await page.route('**/api/alerts/test-email', async (route) => {
    lastTestEmailSession = route.request().headers()['x-alert-session'] || ''
    lastTestEmailPayload = JSON.parse(route.request().postData())
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

  await page.route('**/api/market/factors**', async (route) => {
    factorRequestCount += 1
    latestFactorSource = new URL(route.request().url()).searchParams.get('source') || ''
    await route.fulfill({
      json: factorsPayload,
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
  await expect(page.getByTestId('factor-board')).toContainText('黄金影响因子')
  await expect(page.getByTestId('factor-board')).toContainText('银行积存金')
  await expect(page.getByTestId('factor-board')).toContainText('利好')
  await expect(page.getByTestId('factor-board')).toContainText('避险波动率')
  await expect(page.getByTestId('factor-board')).toContainText('央行购金')
  await expect(page.getByTestId('factor-toggle')).toHaveCount(0)
  await expect(page.getByTestId('factor-list').locator('.factor-item')).toHaveCount(12)
  expect(factorRequestCount).toBe(1)
  expect(latestFactorSource).toBe('icbc')
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
  const viewportWidth = page.viewportSize().width
  expect(dashboardBox.width).toBeLessThanOrEqual(viewportWidth)
  const reviewTop = await page.locator('[data-testid="monthly-review"]').first().evaluate((node) => node.getBoundingClientRect().top)
  expect(reviewTop).toBeGreaterThan(700)
})

test('keeps the price range and dashboard readable on narrow browser widths', async ({ page }) => {
  await page.setViewportSize({ width: 651, height: 837 })
  await page.goto('/')

  await expect(page.getByTestId('current-price')).toContainText('552.05')

  const layout = await page.evaluate(() => {
    const dashboard = document.querySelector('.dashboard-screen')
    const priceCard = document.querySelector('.price-card')
    const adviceCard = document.querySelector('.advice-card')
    const rangeRow = document.querySelector('.price-range-row')
    const chips = Array.from(document.querySelectorAll('.price-range-chip'))

    const rectOf = (node) => {
      const rect = node.getBoundingClientRect()
      return {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
      }
    }

    return {
      viewportWidth: window.innerWidth,
      dashboard: rectOf(dashboard),
      priceCard: rectOf(priceCard),
      adviceCard: rectOf(adviceCard),
      rangeRow: rectOf(rangeRow),
      chips: chips.map(rectOf),
    }
  })

  expect(layout.dashboard.width).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.adviceCard.top).toBeGreaterThan(layout.priceCard.bottom - 1)
  expect(layout.rangeRow.right).toBeLessThanOrEqual(layout.priceCard.right + 1)
  expect(layout.rangeRow.left).toBeGreaterThanOrEqual(layout.priceCard.left - 1)
  expect(layout.chips).toHaveLength(4)

  for (const chip of layout.chips) {
    expect(chip.left).toBeGreaterThanOrEqual(layout.rangeRow.left - 1)
    expect(chip.right).toBeLessThanOrEqual(layout.rangeRow.right + 1)
    expect(chip.width).toBeGreaterThan(0)
    expect(chip.height).toBeGreaterThan(0)
  }
})

test('keeps the final factor row clear of the card edge in compact dashboard', async ({ page }) => {
  await page.setViewportSize({ width: 877, height: 751 })
  await page.goto('/')

  await expect(page.getByTestId('factor-board')).toContainText('黄金影响因子')

  const factorLayout = await page.evaluate(() => {
    const card = document.querySelector('[data-testid="factor-board"]')
    const items = Array.from(document.querySelectorAll('[data-testid="factor-board"] .factor-item'))
    const lastItem = items[items.length - 1]
    const rectOf = (node) => {
      const rect = node.getBoundingClientRect()
      return {
        top: rect.top,
        bottom: rect.bottom,
        height: rect.height,
      }
    }

    return {
      card: rectOf(card),
      lastItem: rectOf(lastItem),
      itemCount: items.length,
    }
  })

  expect(factorLayout.itemCount).toBe(12)
  expect(factorLayout.lastItem.bottom).toBeLessThanOrEqual(factorLayout.card.bottom - 8)
})

test('keeps the compact factor list high in the card at tablet widths', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 751 })
  await page.goto('/')

  await expect(page.getByTestId('factor-board')).toContainText('上金所Au99.99')

  const factorLayout = await page.evaluate(() => {
    const card = document.querySelector('[data-testid="factor-board"]')
    const firstItem = document.querySelector('[data-testid="factor-board"] .factor-item')
    const rectOf = (node) => {
      const rect = node.getBoundingClientRect()
      return {
        top: rect.top,
        bottom: rect.bottom,
      }
    }

    return {
      card: rectOf(card),
      firstItem: rectOf(firstItem),
    }
  })

  expect(factorLayout.firstItem.top).toBeLessThanOrEqual(factorLayout.card.top + 44)
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
  await expect(page.getByTestId('alert-panel')).toContainText('先验证邮箱')
  await page.getByTestId('alert-email').fill('me@example.com')
  await page.getByTestId('alert-request-code').click()
  await expect(page.getByTestId('alert-status')).toContainText('验证码已发送')
  expect(requestCodeCount).toBe(1)

  await page.getByTestId('alert-code').fill('123456')
  await page.getByTestId('alert-verify').click()
  await expect(page.getByTestId('alert-verified-email')).toContainText('me***@example.com')
  expect(verifyCodeCount).toBe(1)
  await expect(page.getByTestId('alert-panel')).toContainText('预设清仓价格')
  await expect(page.getByTestId('alert-panel')).toContainText('预设抄底价格')
  await expect(page.getByTestId('alert-panel')).toContainText('清仓价')
  await expect(page.getByTestId('alert-panel')).toContainText('抄底价')
  await expect(page.getByTestId('alert-enabled')).toBeChecked()
  await expect(page.getByTestId('alert-custom-high')).toBeChecked()
  await expect(page.getByTestId('alert-custom-low')).toBeChecked()
  await expect(page.getByTestId('alert-predicted-high')).toBeChecked()
  await expect(page.getByTestId('alert-predicted-low')).toBeChecked()
  await page.getByTestId('alert-target-high').fill('900')
  await page.getByTestId('alert-target-low').fill('870')
  await page.getByTestId('alert-save').click()

  await expect(page.getByTestId('alert-status')).toContainText('已保存')
  expect(lastAlertRuleSession).toBe('session-token-a')
  expect(lastAlertRulePayload.recipient_email).toBeUndefined()
  expect(alertRules[0].recipient_email).toBe('me***@example.com')
  expect(alertRules[0].target_high_price).toBe(900)
  expect(alertRules[0].notify_on_custom_high).toBe(true)

  await page.getByTestId('alert-test-email').click()

  await expect(page.getByTestId('alert-status')).toContainText('测试邮件已发送')
  expect(testEmailCount).toBe(1)
  expect(lastTestEmailSession).toBe('session-token-a')
  expect(lastTestEmailPayload.recipient_email).toBeUndefined()
})
