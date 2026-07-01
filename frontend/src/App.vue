<script setup>
import {computed, onMounted, onUnmounted, reactive, ref} from 'vue'
import {
  Activity,
  AlertTriangle,
  Bell,
  Calculator,
  ChevronRight,
  Clock3,
  Database,
  Gauge,
  Globe,
  LineChart,
  Mail,
  Newspaper,
  RefreshCw,
  Save,
  Send,
  TrendingUp,
  Trash2,
} from 'lucide-vue-next'
import PriceChart from './components/PriceChart.vue'
import SentimentGauge from './components/SentimentGauge.vue'
import ThirtyDayReviewChart from './components/ThirtyDayReviewChart.vue'
import {
  calculatePnl,
  createAlertRule,
  deleteAlertRule,
  getAlertRules,
  getKlines,
  getMarketSnapshot,
  getMonthlyReviews,
  getPublicConfig,
  sendTestEmail,
  updateAlertRule,
} from './api'
import goldBarsHero from './assets/ui/gold-bars-hero.jpg'
import goldMarketWave from './assets/ui/gold-market-wave.jpg'
import goldShieldChart from './assets/ui/gold-shield-chart.png'
import goldTrendIcon from './assets/ui/gold-trend-icon.png'
import {buildPredictedDailyRange, buildTodayRange} from './utils/dayRange'
import {recordRealtimeTick} from './utils/realtimeTicks'
import {sentimentScoreToGaugeValue} from './utils/sentimentGauge'

const snapshot = ref(null)
const publicConfig = ref(null)
const loading = ref(false)
const connected = ref(true)
const errorMessage = ref('')
const lastUpdated = ref(null)
const nextRefreshAt = ref(null)
const timer = ref(null)
const pnl = ref(null)
const selectedSource = ref('')
const klines = ref([])
const realtimeTicks = ref([])
const klinesLoading = ref(false)
const monthlyReviews = ref([])
const monthlyReviewLoading = ref(false)
const selectedPeriod = ref('1min')
const klineResetKey = ref(0)
const periodOptions = [
  {key: '1min', label: '分线'},
  {key: '1day', label: '日线'},
  {key: '1month', label: '月线'},
]
const klineUnit = ref('CNY/g')
const klineTimer = ref(null)
const portfolio = reactive({
  buy_price: 540,
  quantity: 1,
})
const alertRules = ref([])
const alertRuleId = ref(null)
const alertLoading = ref(false)
const alertSaving = ref(false)
const alertStatus = ref('')
const alertForm = reactive({
  enabled: true,
  source: '',
  recipient_email: '',
  target_high_price: null,
  target_low_price: null,
  notify_on_custom_high: false,
  notify_on_custom_low: false,
  notify_on_predicted_high: true,
  notify_on_predicted_low: true,
})
const pageBackgroundStyle = {'--page-wave-image': `url(${goldMarketWave})`}
const priceCardStyle = {'--price-card-image': `url(${goldBarsHero})`}

const refreshSeconds = computed(() => snapshot.value?.refresh_seconds || publicConfig.value?.realtime?.frontend_refresh_seconds || 2)
const maxDelaySeconds = computed(() => snapshot.value?.max_data_delay_seconds || publicConfig.value?.realtime?.max_data_delay_seconds || 5)
const currentPrice = computed(() => snapshot.value?.price?.display_value || snapshot.value?.price?.value || 0)
const rawPrice = computed(() => snapshot.value?.price?.value || 0)
const displayUnit = computed(() => snapshot.value?.price?.display_unit || 'CNY/g')
const sourceUnit = computed(() => snapshot.value?.price?.unit || 'USD/oz')
const sourceOptions = computed(() => publicConfig.value?.data_sources?.options || [])
const priceSource = computed(() => snapshot.value?.price?.source || '--')
const stopLoss = computed(() => snapshot.value?.indicators?.stop_loss?.display_stop_loss || snapshot.value?.indicators?.stop_loss?.stop_loss || null)
const todayRange = computed(() => buildTodayRange(klines.value, currentPrice.value, new Date(), snapshot.value?.today_range))
const predictedDailyRange = computed(() => {
  const backendRange = snapshot.value?.predicted_range
  if (backendRange?.low && backendRange?.high) return backendRange
  return buildPredictedDailyRange(
    currentPrice.value,
    0.02,
    klines.value,
    new Date(),
    snapshot.value?.today_range,
  )
})
const activeRealtimeTicks = computed(() => realtimeTicks.value.filter((tick) => tick.sourceKey === selectedSource.value))
const recommendation = computed(() => snapshot.value?.recommendation || {
  action: 'hold',
  confidence: 0,
  reasons: [],
  risks: []
})
const sentiment = computed(() => snapshot.value?.sentiment || {
  label: 'neutral',
  score: 0,
  positive_hits: [],
  negative_hits: []
})

const confidencePercent = computed(() => Math.round((recommendation.value.confidence || 0) * 100))

const recommendationLabel = computed(() => {
  switch (recommendation.value.action) {
    case 'buy':
      return '建议买入'
    case 'sell':
      return '建议卖出'
    default:
      return '暂不买入'
  }
})

const recommendationDesc = computed(() => {
  if (recommendation.value.reasons?.length) return recommendation.value.reasons[0]
  if (recommendation.value.action === 'buy') return '多项指标共振，市场具备上行动能。'
  if (recommendation.value.action === 'sell') return '风险信号增强，建议规避短期回调。'
  return '市场处于震荡上行阶段，建议等待更明确的入场信号。'
})

// 情绪指数 0-100
const gaugeValue = computed(() => {
  return sentimentScoreToGaugeValue(sentiment.value.score)
})

const gaugeMood = computed(() => {
  const v = gaugeValue.value
  if (v >= 80) return '极度看多'
  if (v >= 60) return '偏多'
  if (v > 40) return '中性'
  if (v > 20) return '偏空'
  return '极度看空'
})

const newsIcons = [LineChart, Globe, TrendingUp, Activity]
const newsItems = computed(() => {
  const articles = snapshot.value?.news?.articles || publicConfig.value?.news?.demo_articles || []
  return articles.slice(0, 4).map((item, index) => ({
    id: item.id ?? index,
    title: item.title || item.headline || '黄金市场动态',
    sentiment: item.sentiment || 'positive',
    time: item.published_at || item.time || '',
    icon: newsIcons[index % newsIcons.length],
  }))
})

const connectionLabel = computed(() => {
  if (loading.value) return '更新中'
  if (!connected.value) return '连接中断'
  return '已连接'
})

const connectionClass = computed(() => {
  if (loading.value) return 'status-loading'
  if (!connected.value) return 'status-error'
  return 'status-ok'
})

const formattedTime = computed(() => {
  if (!lastUpdated.value) return '等待数据'
  const d = lastUpdated.value
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
})

const activeSourceLabel = computed(() => {
  const found = sourceOptions.value.find((item) => item.key === selectedSource.value)
  return found?.label || snapshot.value?.price?.source || selectedSource.value || '--'
})

const alertSmtpLabel = computed(() => {
  if (publicConfig.value?.alerts?.smtp_configured) return 'SMTP 已配置'
  return 'SMTP 未配置'
})

const alertBreakoutStep = computed(() => publicConfig.value?.alerts?.predicted_breakout_step_cny_g || 2)

async function loadConfig() {
  publicConfig.value = await getPublicConfig()
  const defaults = publicConfig.value.portfolio_defaults || {}
  portfolio.buy_price = Number(defaults.buy_price || portfolio.buy_price)
  portfolio.quantity = Number(defaults.quantity || portfolio.quantity)
  selectedSource.value = publicConfig.value.data_sources?.active || sourceOptions.value[0]?.key || ''
  alertForm.source = publicConfig.value.alerts?.default_source || selectedSource.value
}

async function loadKlines() {
  klinesLoading.value = true
  try {
    const data = await getKlines(selectedPeriod.value, selectedSource.value)
    klines.value = data.candles || []
    klineUnit.value = data.display_unit || 'CNY/g'
    syncLastCandle()
  } catch (error) {
    klines.value = []
  } finally {
    klinesLoading.value = false
  }
}

async function loadMonthlyReviews() {
  monthlyReviewLoading.value = true
  try {
    const data = await getMonthlyReviews(30)
    monthlyReviews.value = data.items || []
  } catch (error) {
    monthlyReviews.value = []
  } finally {
    monthlyReviewLoading.value = false
  }
}

function applyAlertRule(rule) {
  if (!rule) return
  alertRuleId.value = rule.id
  alertForm.enabled = rule.enabled !== false
  alertForm.source = rule.source || selectedSource.value
  alertForm.recipient_email = rule.recipient_email || ''
  alertForm.target_high_price = rule.target_high_price ?? null
  alertForm.target_low_price = rule.target_low_price ?? null
  alertForm.notify_on_custom_high = Boolean(rule.notify_on_custom_high)
  alertForm.notify_on_custom_low = Boolean(rule.notify_on_custom_low)
  alertForm.notify_on_predicted_high = rule.notify_on_predicted_high !== false
  alertForm.notify_on_predicted_low = rule.notify_on_predicted_low !== false
}

async function loadAlertRules() {
  alertLoading.value = true
  try {
    const data = await getAlertRules()
    alertRules.value = data.rules || []
    if (alertRules.value.length) {
      applyAlertRule(alertRules.value[0])
    }
  } catch (error) {
    alertStatus.value = '提醒规则暂不可用'
  } finally {
    alertLoading.value = false
  }
}

function alertPayload() {
  return {
    enabled: alertForm.enabled,
    source: alertForm.source || selectedSource.value,
    recipient_email: String(alertForm.recipient_email || '').trim(),
    target_high_price: alertForm.target_high_price === '' ? null : alertForm.target_high_price,
    target_low_price: alertForm.target_low_price === '' ? null : alertForm.target_low_price,
    notify_on_custom_high: alertForm.notify_on_custom_high,
    notify_on_custom_low: alertForm.notify_on_custom_low,
    notify_on_predicted_high: alertForm.notify_on_predicted_high,
    notify_on_predicted_low: alertForm.notify_on_predicted_low,
  }
}

async function saveAlertRule() {
  alertSaving.value = true
  alertStatus.value = ''
  try {
    const payload = alertPayload()
    const data = alertRuleId.value
      ? await updateAlertRule(alertRuleId.value, payload)
      : await createAlertRule(payload)
    applyAlertRule(data.rule)
    alertRules.value = [data.rule]
    alertStatus.value = '已保存'
  } catch (error) {
    alertStatus.value = error.message
  } finally {
    alertSaving.value = false
  }
}

async function sendAlertTest() {
  alertSaving.value = true
  alertStatus.value = ''
  try {
    await sendTestEmail({
      recipient_email: String(alertForm.recipient_email || '').trim(),
      source_label: activeSourceLabel.value,
      current_price: currentPrice.value,
      display_unit: displayUnit.value,
      predicted_range: predictedDailyRange.value,
      event_time: formattedTime.value,
    })
    alertStatus.value = '测试邮件已发送'
  } catch (error) {
    alertStatus.value = error.message
  } finally {
    alertSaving.value = false
  }
}

async function removeAlertRule() {
  if (!alertRuleId.value) {
    alertStatus.value = '暂无规则'
    return
  }
  alertSaving.value = true
  try {
    await deleteAlertRule(alertRuleId.value)
    alertRules.value = []
    alertRuleId.value = null
    alertStatus.value = '已删除'
  } catch (error) {
    alertStatus.value = error.message
  } finally {
    alertSaving.value = false
  }
}

async function selectPeriod(key) {
  if (selectedPeriod.value === key) return
  selectedPeriod.value = key
  await loadKlines()
}

async function resetKlineChart() {
  klineResetKey.value += 1
  await loadKlines()
}

// 用实时当前价更新最后一根K线的收盘/高/低,让图表跟着价格实时跳动
function syncLastCandle() {
  const price = currentPrice.value
  if (!price || !klines.value.length) return
  const arr = klines.value.slice()
  const last = {...arr[arr.length - 1]}
  last.close = Number(price)
  last.high = Math.max(Number(last.high), Number(price))
  last.low = Math.min(Number(last.low), Number(price))
  arr[arr.length - 1] = last
  klines.value = arr
}

function recordRealtimeSample(sampleTime = new Date()) {
  if (!selectedSource.value || !currentPrice.value) return
  realtimeTicks.value = recordRealtimeTick(realtimeTicks.value, {
    sourceKey: selectedSource.value,
    time: sampleTime,
    price: currentPrice.value,
  }, {
    now: sampleTime,
    maxAgeMs: 24 * 60 * 60 * 1000,
    maxPointsPerSource: 12_000,
  })
}

async function refreshSnapshot() {
  loading.value = true
  errorMessage.value = ''
  try {
    snapshot.value = await getMarketSnapshot(selectedSource.value)
    connected.value = true
    const now = new Date()
    lastUpdated.value = now
    nextRefreshAt.value = new Date(Date.now() + refreshSeconds.value * 1000)
    recordRealtimeSample(now)
    syncLastCandle()
    await updatePnl({silent: true})
  } catch (error) {
    connected.value = false
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function refreshMarketData() {
  await refreshSnapshot()
  await loadKlines()
}

async function updatePnl(options = {}) {
  if (!currentPrice.value) return
  try {
    pnl.value = await calculatePnl({
      buy_price: Number(portfolio.buy_price),
      quantity: Number(portfolio.quantity),
      current_price: currentPrice.value,
    })
  } catch (error) {
    if (!options.silent) {
      errorMessage.value = error.message
    }
  }
}

function scheduleRefresh() {
  timer.value = window.setInterval(refreshSnapshot, refreshSeconds.value * 1000)
  // K线历史每 60 秒整体重拉一次(后端有缓存,不会超额度);最新一根靠 syncLastCandle 实时跟价
  klineTimer.value = window.setInterval(() => {
    loadKlines()
    loadMonthlyReviews()
  }, 60 * 1000)
}

onMounted(async () => {
  try {
    await loadConfig()
    await loadAlertRules()
  } catch (error) {
    errorMessage.value = error.message
  }
  await refreshSnapshot()
  await loadKlines()
  await loadMonthlyReviews()
  scheduleRefresh()
})

onUnmounted(() => {
  if (timer.value) window.clearInterval(timer.value)
  if (klineTimer.value) window.clearInterval(klineTimer.value)
})
</script>

<template>
  <div class="page" :style="pageBackgroundStyle">
    <main class="app-shell">
      <section class="dashboard-screen">
        <header class="topbar">
          <div class="brand">
            <div class="brand-logo">
              <img :src="goldTrendIcon" alt="" class="brand-logo-img" aria-hidden="true">
            </div>
            <div class="brand-text">
              <h1>黄金市场实时价格分析</h1>
              <p class="subtitle">实时洞察 · 专业分析 · 智能决策</p>
            </div>
          </div>
          <div class="status-cluster">
            <div class="status-pill" :class="connectionClass" data-testid="connection-status">
              <RefreshCw v-if="loading" class="spin" :size="13"/>
              <span class="status-dot" v-else></span>
              <span>{{ connectionLabel }}</span>
            </div>
            <button class="icon-button" type="button" aria-label="刷新行情" title="刷新行情" @click="refreshSnapshot">
              <RefreshCw :size="17" :class="{ spin: loading }"/>
            </button>
          </div>
        </header>

        <section v-if="errorMessage" class="alert" role="alert">
          <AlertTriangle :size="18"/>
          <span>{{ errorMessage }}</span>
        </section>

        <!-- Row 1: price + recommendation -->
        <section class="row row-1">
        <article class="card price-card" :style="priceCardStyle">
          <div class="price-card-content">
            <div class="price-heading">
              <p class="card-label">当前黄金价格</p>
            </div>
            <div class="price-row">
              <span class="price-value" data-testid="current-price">{{ currentPrice ? currentPrice.toFixed(2) : '--' }}</span>
              <span class="price-unit">{{ displayUnit }}</span>
            </div>
            <div class="price-range-row" aria-label="今日价格区间">
              <span class="price-range-chip range-low">
                <span class="range-label">今日最低</span>
                <strong>{{ todayRange ? todayRange.low.toFixed(2) : '--' }}</strong>
                <span>{{ displayUnit }}</span>
              </span>
              <span class="price-range-chip range-high">
                <span class="range-label">今日最高</span>
                <strong>{{ todayRange ? todayRange.high.toFixed(2) : '--' }}</strong>
                <span>{{ displayUnit }}</span>
              </span>
              <span class="price-range-chip range-predict-low">
                <span class="range-label">预测低点</span>
                <strong data-testid="predicted-low">{{ predictedDailyRange ? predictedDailyRange.low.toFixed(2) : '--' }}</strong>
                <span>{{ displayUnit }}</span>
              </span>
              <span class="price-range-chip range-predict-high">
                <span class="range-label">预测高点</span>
                <strong data-testid="predicted-high">{{ predictedDailyRange ? predictedDailyRange.high.toFixed(2) : '--' }}</strong>
                <span>{{ displayUnit }}</span>
              </span>
            </div>
            <div class="price-meta">
              <span><Clock3 :size="13"/> {{ formattedTime }}</span>
              <span>刷新 {{ refreshSeconds }}s</span>
              <span>延迟阈值 {{ maxDelaySeconds }}s</span>
              <span>原始 {{ rawPrice ? rawPrice.toFixed(2) : '--' }} {{ sourceUnit }}</span>
              <span data-testid="price-source-name">渠道 {{ activeSourceLabel || priceSource }}</span>
            </div>
          </div>
        </article>

        <article class="card advice-card">
          <img :src="goldShieldChart" alt="" class="card-watermark advice-watermark" aria-hidden="true">
          <div class="card-head">
            <span class="head-with-icon">
              <span class="asset-icon-tile"><img :src="goldShieldChart" alt="" aria-hidden="true"></span>
              <span class="card-label">结构化建议</span>
            </span>
          </div>
          <div class="advice-action" :class="`advice-${recommendation.action}`" data-testid="recommendation-action">
            {{ recommendationLabel }}
          </div>
          <p class="advice-summary">{{ recommendationDesc }}</p>
          <div class="confidence">
            <div class="confidence-head">
              <span>置信度</span>
              <strong>{{ confidencePercent }}%</strong>
            </div>
            <div class="confidence-track">
              <div class="confidence-fill" :style="{ width: confidencePercent + '%' }"></div>
            </div>
          </div>
        </article>
        </section>

        <!-- Row 2: chart + stop-loss metrics -->
        <section class="row row-2">
        <article class="card chart-card">
          <div class="card-head">
            <div>
              <p class="card-label">价格图表</p>
              <h2 class="card-title">K线 · {{ periodOptions.find(p => p.key === selectedPeriod)?.label }}</h2>
            </div>
            <div class="chart-actions">
              <button
                type="button"
                class="chart-reset-button"
                data-testid="kline-reset-button"
                aria-label="复位K线图缩放"
                title="复位K线图缩放"
                :disabled="klinesLoading"
                @click="resetKlineChart"
              >
                <RefreshCw :size="14" :class="{ spin: klinesLoading }"/>
              </button>
              <div class="period-tabs">
                <button
                  v-for="p in periodOptions"
                  :key="p.key"
                  type="button"
                  class="period-tab"
                  :class="{ active: selectedPeriod === p.key }"
                  @click="selectPeriod(p.key)"
                >{{ p.label }}</button>
              </div>
              <label v-if="sourceOptions.length" class="select-pill">
                <Database :size="15"/>
                <select v-model="selectedSource" data-testid="price-source-select" @change="refreshMarketData">
                  <option v-for="source in sourceOptions" :key="source.key" :value="source.key">
                    {{ source.label }}{{ source.requires_api_key ? ' · 需密钥' : '' }}
                  </option>
                </select>
              </label>
            </div>
          </div>
          <PriceChart
            :candles="klines"
            :history="snapshot?.history || []"
            :stop-loss="stopLoss"
            :unit="klineUnit"
            :period="selectedPeriod"
            :source-key="selectedSource"
            :reset-key="klineResetKey"
            :realtime-ticks="activeRealtimeTicks"
          />
        </article>

        <article class="card stoploss-card">
          <img :src="goldShieldChart" alt="" class="card-watermark stoploss-watermark" aria-hidden="true">
          <div class="card-head">
            <span class="head-with-icon">
              <span class="asset-icon-tile"><img :src="goldShieldChart" alt="" aria-hidden="true"></span>
              <span class="card-label">实时止损位</span>
            </span>
          </div>
          <div class="stoploss-value" data-testid="stop-loss">{{ stopLoss ? stopLoss.toFixed(2) : '--' }}</div>
          <div class="metric-list">
            <div class="metric-row">
              <span class="metric-name">指标</span>
              <strong class="metric-value">{{ snapshot?.indicators?.stop_loss?.indicator_type || 'SMA' }}</strong>
            </div>
            <div class="metric-row">
              <span class="metric-name">周期</span>
              <strong class="metric-value">{{ snapshot?.indicators?.stop_loss?.period || 20 }}</strong>
            </div>
            <div class="metric-row">
              <span class="metric-name">条数</span>
              <strong class="metric-value">{{ snapshot?.history?.length || 0 }}</strong>
            </div>
            <div class="metric-row">
              <span class="metric-name">单位</span>
              <strong class="metric-value">{{ displayUnit }}</strong>
            </div>
          </div>
        </article>
        </section>

        <!-- Row 3: sentiment + news + pnl -->
        <section class="row row-3">
        <article class="card sentiment-card">
          <div class="card-head">
            <span class="head-with-icon"><span class="card-icon amber"><Gauge :size="16"/></span><span class="card-label">市场情绪</span></span>
          </div>
          <SentimentGauge :value="gaugeValue" :mood="gaugeMood" :sentiment="sentiment"/>
        </article>

        <article class="card news-card">
          <div class="card-head">
            <span class="head-with-icon"><span class="card-icon blue"><Newspaper :size="16"/></span><span class="card-label">新闻摘要</span></span>
          </div>
          <ul v-if="newsItems.length" class="news-list">
            <li v-for="item in newsItems" :key="item.id" class="news-item">
              <span class="news-icon" :class="`tag-${item.sentiment}`">
                <component :is="item.icon" :size="16"/>
              </span>
              <p class="news-title">{{ item.title }}</p>
              <span class="news-time">{{ item.time || '刚刚' }}</span>
            </li>
          </ul>
          <div v-else class="news-empty">
            <Newspaper :size="28"/>
            <span>暂无最新资讯</span>
          </div>
          <button class="link-button" type="button">查看更多 <ChevronRight :size="14"/></button>
        </article>

        <article class="card pnl-card">
          <div class="card-head">
            <span class="head-with-icon"><span class="card-icon green"><Calculator :size="16"/></span><span class="card-label">盈亏测算</span></span>
          </div>
          <form class="pnl-form" @submit.prevent="updatePnl">
            <label>
              <span>买入价 ({{ displayUnit }})</span>
              <input v-model.number="portfolio.buy_price" data-testid="buy-price" type="number" min="0.01" step="0.01"/>
            </label>
            <label>
              <span>持有数量 ({{ displayUnit.split('/')[1] || 'g' }})</span>
              <input v-model.number="portfolio.quantity" data-testid="quantity" type="number" min="0.0001" step="0.0001"/>
            </label>
            <button type="submit">
              <Calculator :size="16"/>
              计算盈亏
            </button>
          </form>
          <div class="pnl-result-grid">
            <div class="pnl-block">
              <p class="pnl-block-label">预期盈亏 ({{ displayUnit.split('/')[0] }})</p>
              <p class="pnl-amount" :class="{ positive: pnl?.amount >= 0, negative: pnl?.amount < 0 }" data-testid="pnl-amount">
                {{ pnl ? `${pnl.amount >= 0 ? '+' : ''}${pnl.amount.toFixed(2)}` : '--' }}
              </p>
            </div>
            <div class="pnl-block">
              <p class="pnl-block-label">预期收益率</p>
              <p class="pnl-percent" :class="{ positive: pnl?.amount >= 0, negative: pnl?.amount < 0 }" data-testid="pnl-percent">
                {{ pnl ? `${pnl.percent >= 0 ? '+' : ''}${pnl.percent.toFixed(2)}%` : '--' }}
              </p>
            </div>
          </div>
        </article>
        </section>
      </section>

      <section class="card alert-settings-section" data-testid="alert-panel">
        <div class="alert-settings-head">
          <div>
            <p class="card-label">邮件提醒</p>
            <h2 class="card-title">价格触达 · 预估边界突破</h2>
          </div>
          <div class="alert-state-pill">
            <Bell :size="14"/>
            <span>{{ alertSmtpLabel }}</span>
          </div>
        </div>
        <form class="alert-form" @submit.prevent="saveAlertRule">
          <label class="alert-field alert-field-email">
            <span>收件邮箱</span>
            <span class="alert-input-wrap">
              <Mail :size="15"/>
              <input
                v-model="alertForm.recipient_email"
                data-testid="alert-email"
                type="email"
                autocomplete="email"
                placeholder="name@example.com"
                required
              >
            </span>
          </label>
          <label class="alert-field">
            <span>行情源</span>
            <select v-model="alertForm.source" data-testid="alert-source">
              <option v-for="source in sourceOptions" :key="source.key" :value="source.key">
                {{ source.label }}
              </option>
            </select>
          </label>
          <label class="alert-field">
            <span>高价目标</span>
            <input v-model.number="alertForm.target_high_price" data-testid="alert-target-high" type="number" min="0.01" step="0.01">
          </label>
          <label class="alert-field">
            <span>低价目标</span>
            <input v-model.number="alertForm.target_low_price" data-testid="alert-target-low" type="number" min="0.01" step="0.01">
          </label>
          <div class="alert-switches">
            <label>
              <input v-model="alertForm.enabled" data-testid="alert-enabled" type="checkbox">
              <span>启用</span>
            </label>
            <label>
              <input v-model="alertForm.notify_on_custom_high" data-testid="alert-custom-high" type="checkbox">
              <span>高价</span>
            </label>
            <label>
              <input v-model="alertForm.notify_on_custom_low" data-testid="alert-custom-low" type="checkbox">
              <span>低价</span>
            </label>
            <label>
              <input v-model="alertForm.notify_on_predicted_high" data-testid="alert-predicted-high" type="checkbox">
              <span>预估高点</span>
            </label>
            <label>
              <input v-model="alertForm.notify_on_predicted_low" data-testid="alert-predicted-low" type="checkbox">
              <span>预估低点</span>
            </label>
          </div>
          <div class="alert-actions">
            <button type="submit" data-testid="alert-save" :disabled="alertSaving || alertLoading">
              <Save :size="15"/>
              保存
            </button>
            <button type="button" data-testid="alert-test-email" :disabled="alertSaving || !alertForm.recipient_email" @click="sendAlertTest">
              <Send :size="15"/>
              测试邮件
            </button>
            <button type="button" class="alert-delete-button" :disabled="alertSaving || !alertRuleId" @click="removeAlertRule">
              <Trash2 :size="15"/>
              删除
            </button>
          </div>
        </form>
        <div class="alert-settings-foot">
          <span data-testid="alert-status">{{ alertStatus || `预估边界每突破 ${alertBreakoutStep} ${displayUnit} 续发一次` }}</span>
          <span v-if="alertRuleId">规则 #{{ alertRuleId }}</span>
        </div>
      </section>

      <section class="card monthly-review-section" data-testid="monthly-reviews-panel">
        <div class="monthly-reviews-head">
          <div>
            <p class="card-label">30天行情</p>
            <h2 class="card-title">黄金 · 白银 · 铂金</h2>
          </div>
        </div>
        <div v-if="monthlyReviewLoading && !monthlyReviews.length" class="review-empty">30天行情加载中</div>
        <div v-else class="monthly-reviews-stack">
          <ThirtyDayReviewChart
            v-for="review in monthlyReviews"
            :key="review.key || review.source"
            :review="review"
            :theme="review.theme"
            :loading="monthlyReviewLoading"
          />
        </div>
      </section>

      <footer class="risk-footer">
        <span>市场有风险，投资需谨慎。数据仅供参考，不构成投资建议。</span>
      </footer>
    </main>
  </div>
</template>
