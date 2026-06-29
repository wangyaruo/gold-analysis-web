<script setup>
import {computed, onMounted, onUnmounted, reactive, ref} from 'vue'
import {
  Activity,
  AlertTriangle,
  Calculator,
  ChevronRight,
  Clock3,
  Database,
  Gauge,
  Globe,
  LineChart,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from 'lucide-vue-next'
import PriceChart from './components/PriceChart.vue'
import SentimentGauge from './components/SentimentGauge.vue'
import {calculatePnl, getKlines, getMarketSnapshot, getPublicConfig} from './api'

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
const klinesLoading = ref(false)
const selectedPeriod = ref('1day')
const periodOptions = [
  {key: '1min', label: '分线'},
  {key: '1h', label: '时线'},
  {key: '5h', label: '5小时线'},
  {key: '1day', label: '日线'},
  {key: '1month', label: '月线'},
]
const klineUnit = ref('CNY/g')
const klineTimer = ref(null)
const portfolio = reactive({
  buy_price: 540,
  quantity: 1,
})

const refreshSeconds = computed(() => snapshot.value?.refresh_seconds || publicConfig.value?.realtime?.frontend_refresh_seconds || 10)
const maxDelaySeconds = computed(() => snapshot.value?.max_data_delay_seconds || publicConfig.value?.realtime?.max_data_delay_seconds || 5)
const currentPrice = computed(() => snapshot.value?.price?.display_value || snapshot.value?.price?.value || 0)
const rawPrice = computed(() => snapshot.value?.price?.value || 0)
const displayUnit = computed(() => snapshot.value?.price?.display_unit || 'CNY/g')
const sourceUnit = computed(() => snapshot.value?.price?.unit || 'USD/oz')
const sourceOptions = computed(() => publicConfig.value?.data_sources?.options || [])
const priceSource = computed(() => snapshot.value?.price?.source || '--')
const stopLoss = computed(() => snapshot.value?.indicators?.stop_loss?.display_stop_loss || snapshot.value?.indicators?.stop_loss?.stop_loss || null)
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

const priceChange = computed(() => {
  const history = snapshot.value?.history || []
  if (history.length < 2) return {value: 0, percent: 0}
  const latest = Number(history[history.length - 1].display_price ?? history[history.length - 1].price)
  const prev = Number(history[history.length - 2].display_price ?? history[history.length - 2].price)
  const value = latest - prev
  const percent = prev ? (value / prev) * 100 : 0
  return {value, percent}
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
  const score = Number(sentiment.value.score || 0)
  return Math.max(0, Math.min(100, Math.round(50 + score * 9)))
})

const gaugeMood = computed(() => {
  const v = gaugeValue.value
  if (v >= 80) return '极度看多'
  if (v >= 60) return '偏多'
  if (v > 40) return '中性'
  if (v > 20) return '偏空'
  return '极度看空'
})

const sentimentScoreText = computed(() => {
  const s = Number(sentiment.value.score || 0)
  return `${s >= 0 ? '+' : ''}${s}`
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

async function loadConfig() {
  publicConfig.value = await getPublicConfig()
  const defaults = publicConfig.value.portfolio_defaults || {}
  portfolio.buy_price = Number(defaults.buy_price || portfolio.buy_price)
  portfolio.quantity = Number(defaults.quantity || portfolio.quantity)
  selectedSource.value = publicConfig.value.data_sources?.active || sourceOptions.value[0]?.key || ''
}

async function loadKlines() {
  klinesLoading.value = true
  try {
    const data = await getKlines(selectedPeriod.value)
    klines.value = data.candles || []
    klineUnit.value = data.display_unit || 'CNY/g'
    syncLastCandle()
  } catch (error) {
    klines.value = []
  } finally {
    klinesLoading.value = false
  }
}

async function selectPeriod(key) {
  if (selectedPeriod.value === key) return
  selectedPeriod.value = key
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

async function refreshSnapshot() {
  loading.value = true
  errorMessage.value = ''
  try {
    snapshot.value = await getMarketSnapshot(selectedSource.value)
    connected.value = true
    lastUpdated.value = new Date()
    nextRefreshAt.value = new Date(Date.now() + refreshSeconds.value * 1000)
    syncLastCandle()
    await updatePnl({silent: true})
  } catch (error) {
    connected.value = false
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
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
  klineTimer.value = window.setInterval(loadKlines, 60 * 1000)
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (error) {
    errorMessage.value = error.message
  }
  await refreshSnapshot()
  await loadKlines()
  scheduleRefresh()
})

onUnmounted(() => {
  if (timer.value) window.clearInterval(timer.value)
  if (klineTimer.value) window.clearInterval(klineTimer.value)
})
</script>

<template>
  <div class="page">
    <main class="app-shell">
      <header class="topbar">
        <div class="brand">
          <div class="brand-logo">
            <svg viewBox="0 0 48 48" width="46" height="46" aria-hidden="true">
              <defs>
                <linearGradient id="bar-g" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#f4d885"/>
                  <stop offset="55%" stop-color="#e0b24a"/>
                  <stop offset="100%" stop-color="#bd8a1a"/>
                </linearGradient>
              </defs>
              <g stroke="#a9790f" stroke-width="0.8" stroke-linejoin="round">
                <path d="M11 26 l8 -3 l8 3 l-8 3 z" fill="url(#bar-g)"/>
                <path d="M21 26 l8 -3 l8 3 l-8 3 z" fill="url(#bar-g)"/>
                <path d="M16 20 l8 -3 l8 3 l-8 3 z" fill="url(#bar-g)"/>
              </g>
            </svg>
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
        <article class="card price-card">
          <p class="card-label">当前黄金价格</p>
          <div class="price-row">
            <span class="price-value" data-testid="current-price">{{ currentPrice ? currentPrice.toFixed(2) : '--' }}</span>
            <span class="price-unit">{{ displayUnit }}</span>
          </div>
          <div class="price-meta">
            <span><Clock3 :size="13"/> {{ formattedTime }}</span>
            <span>刷新间隔 {{ refreshSeconds }}s</span>
            <span>数据延迟值 {{ maxDelaySeconds }}s</span>
            <span>原始 {{ rawPrice ? rawPrice.toFixed(2) : '--' }} {{ sourceUnit }}</span>
            <span>源 {{ priceSource }}</span>
          </div>
          <div class="gold-decor" aria-hidden="true">
            <svg viewBox="0 0 120 90">
              <defs>
                <linearGradient id="decor-g" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#fbe9b8"/>
                  <stop offset="60%" stop-color="#e8c25c"/>
                  <stop offset="100%" stop-color="#cc9a26"/>
                </linearGradient>
              </defs>
              <g stroke="#c79a2e" stroke-width="1" stroke-linejoin="round">
                <path d="M30 64 l22 -8 l22 8 l-22 8 z" fill="url(#decor-g)"/>
                <path d="M56 64 l22 -8 l22 8 l-22 8 z" fill="url(#decor-g)"/>
                <path d="M43 48 l22 -8 l22 8 l-22 8 z" fill="url(#decor-g)"/>
              </g>
            </svg>
          </div>
        </article>

        <article class="card advice-card">
          <div class="card-head">
            <span class="head-with-icon"><span class="card-icon gold"><ShieldCheck :size="16"/></span><span class="card-label">结构化建议</span></span>
          </div>
          <div class="advice-action" :class="`advice-${recommendation.action}`" data-testid="recommendation-action">
            {{ recommendationLabel }}
          </div>
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
                <select v-model="selectedSource" data-testid="price-source-select" @change="refreshSnapshot">
                  <option v-for="source in sourceOptions" :key="source.key" :value="source.key">
                    {{ source.label }}{{ source.requires_api_key ? ' · 需密钥' : '' }}
                  </option>
                </select>
              </label>
            </div>
          </div>
          <PriceChart :candles="klines" :history="snapshot?.history || []" :stop-loss="stopLoss" :unit="klineUnit" :period="selectedPeriod"/>
        </article>

        <article class="card stoploss-card">
          <div class="card-head">
            <span class="head-with-icon"><span class="card-icon gold"><ShieldCheck :size="16"/></span><span class="card-label">实时止损位</span></span>
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
          <SentimentGauge :value="gaugeValue" :mood="gaugeMood"/>
          <div class="sentiment-delta">情绪分 {{ sentimentScoreText }} <TrendingUp :size="13"/></div>
          <div class="sentiment-legend">
            <span class="legend-key"><span class="dot l1"></span>极度看空</span>
            <span class="legend-key"><span class="dot l2"></span>看空</span>
            <span class="legend-key"><span class="dot l3"></span>中性</span>
            <span class="legend-key"><span class="dot l4"></span>看多</span>
            <span class="legend-key"><span class="dot l5"></span>极度看多</span>
          </div>
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

      <footer class="risk-footer">
        <span>市场有风险，投资需谨慎。数据仅供参考，不构成投资建议。</span>
      </footer>
    </main>
  </div>
</template>
