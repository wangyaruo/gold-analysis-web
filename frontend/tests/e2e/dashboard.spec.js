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
  refresh_seconds: 10,
  max_data_delay_seconds: 5,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/config/public', async (route) => {
    await route.fulfill({
      json: {
        realtime: { frontend_refresh_seconds: 10, max_data_delay_seconds: 5 },
        portfolio_defaults: { buy_price: 540, quantity: 2 },
        display: { currency: 'CNY', unit: 'g' },
        data_sources: {
          active: 'yahoo_finance',
          fallback: 'demo',
          options: [
            { key: 'yahoo_finance', label: 'Yahoo Finance GC=F', requires_api_key: false },
            { key: 'goldpriceapi', label: 'GoldAPI XAU/USD', requires_api_key: true },
            { key: 'demo', label: 'Demo Reference', requires_api_key: false },
          ],
        },
      },
    })
  })

  await page.route('**/api/market/snapshot**', async (route) => {
    const source = new URL(route.request().url()).searchParams.get('source') || 'yahoo_finance'
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
  await page.goto('/')

  await expect(page.getByTestId('connection-status')).toContainText('Connected')
  await expect(page.getByTestId('current-price')).toContainText('552.05')
  await expect(page.getByTestId('price-source-name')).toContainText('yahoo_finance')
  await expect(page.getByTestId('latest-chart-price')).toContainText('551.17')
  await expect(page.getByTestId('recommendation-action')).toContainText('建议买入')
  await expect(page.getByTestId('stop-loss')).toContainText('545.82')
})

test('switches market data source from the dashboard', async ({ page }) => {
  await page.goto('/')

  await page.getByTestId('price-source-select').selectOption('demo')

  await expect(page.getByTestId('price-source-name')).toContainText('demo')
})

test('calculates portfolio pnl from user inputs', async ({ page }) => {
  await page.goto('/')

  await page.getByTestId('buy-price').fill('540')
  await page.getByTestId('quantity').fill('3')
  await page.getByRole('button', { name: /计算/ }).click()

  await expect(page.getByTestId('pnl-amount')).toContainText('36.15')
})
