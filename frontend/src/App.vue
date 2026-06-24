<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  Activity,
  AlertTriangle,
  Calculator,
  Clock3,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  WifiOff,
} from 'lucide-vue-next'
import PriceChart from './components/PriceChart.vue'
import { calculatePnl, getMarketSnapshot, getPublicConfig } from './api'

const snapshot = ref(null)
const publicConfig = ref(null)
const loading = ref(false)
const connected = ref(true)
const errorMessage = ref('')
const lastUpdated = ref(null)
const nextRefreshAt = ref(null)
const timer = ref(null)
const pnl = ref(null)
const portfolio = reactive({
  buy_price: 2300,
  quantity: 1,
})

const refreshSeconds = computed(() => snapshot.value?.refresh_seconds || publicConfig.value?.realtime?.frontend_refresh_seconds || 10)
const currentPrice = computed(() => snapshot.value?.price?.value || 0)
const stopLoss = computed(() => snapshot.value?.indicators?.stop_loss?.stop_loss || null)
const recommendation = computed(() => snapshot.value?.recommendation || { action: 'hold', confidence: 0, reasons: [], risks: [] })
const sentiment = computed(() => snapshot.value?.sentiment || { label: 'neutral', score: 0, positive_hits: [], negative_hits: [] })

const connectionLabel = computed(() => {
  if (loading.value) return 'Updating'
  if (!connected.value) return 'Interrupted'
  return 'Connected'
})

const connectionClass = computed(() => {
  if (loading.value) return 'status-loading'
  if (!connected.value) return 'status-error'
  return 'status-ok'
})

async function loadConfig() {
  publicConfig.value = await getPublicConfig()
  const defaults = publicConfig.value.portfolio_defaults || {}
  portfolio.buy_price = Number(defaults.buy_price || portfolio.buy_price)
  portfolio.quantity = Number(defaults.quantity || portfolio.quantity)
}

async function refreshSnapshot() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getMarketSnapshot()
    snapshot.value = result
    connected.value = true
    lastUpdated.value = new Date()
    nextRefreshAt.value = new Date(Date.now() + refreshSeconds.value * 1000)
    await updatePnl()
  } catch (error) {
    connected.value = false
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function updatePnl() {
  if (!currentPrice.value) return
  pnl.value = await calculatePnl({
    buy_price: Number(portfolio.buy_price),
    quantity: Number(portfolio.quantity),
    current_price: currentPrice.value,
  })
}

function scheduleRefresh() {
  timer.value = window.setInterval(refreshSnapshot, refreshSeconds.value * 1000)
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (error) {
    errorMessage.value = error.message
  }
  await refreshSnapshot()
  scheduleRefresh()
})

onUnmounted(() => {
  if (timer.value) window.clearInterval(timer.value)
})
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">XAU/USD Real-Time Desk</p>
        <h1>黄金市场实时价格分析</h1>
      </div>
      <div class="status-cluster">
        <div class="status-pill" :class="connectionClass" data-testid="connection-status">
          <RefreshCw v-if="loading" class="spin" :size="16" />
          <WifiOff v-else-if="!connected" :size="16" />
          <ShieldCheck v-else :size="16" />
          <span>{{ connectionLabel }}</span>
        </div>
        <button class="icon-button" type="button" aria-label="刷新行情" title="刷新行情" @click="refreshSnapshot">
          <RefreshCw :size="18" />
        </button>
      </div>
    </header>

    <section v-if="errorMessage" class="alert" role="alert">
      <AlertTriangle :size="18" />
      <span>{{ errorMessage }}</span>
    </section>

    <section class="price-band">
      <div class="price-main">
        <p class="label">当前黄金价格</p>
        <div class="price-row">
          <span class="price-value" data-testid="current-price">
            {{ currentPrice ? currentPrice.toFixed(2) : '--' }}
          </span>
          <span class="currency">USD/oz</span>
        </div>
        <div class="meta-row">
          <span><Clock3 :size="15" /> {{ lastUpdated ? lastUpdated.toLocaleTimeString() : '等待数据' }}</span>
          <span>刷新间隔 {{ refreshSeconds }}s</span>
          <span>数据延迟阈值 {{ snapshot?.max_data_delay_seconds || 5 }}s</span>
        </div>
      </div>
      <div class="recommendation" :class="`recommendation-${recommendation.action}`">
        <div class="label">结构化推荐</div>
        <strong data-testid="recommendation-action">{{ recommendation.action === 'buy' ? '建议买入' : '暂不买入' }}</strong>
        <span>置信度 {{ Math.round((recommendation.confidence || 0) * 100) }}%</span>
      </div>
    </section>

    <section class="dashboard-grid">
      <article class="panel chart-panel">
        <div class="panel-header">
          <div>
            <p class="label">价格图表</p>
            <h2>折线 + K线视图</h2>
          </div>
          <Activity :size="20" />
        </div>
        <PriceChart :history="snapshot?.history || []" :stop-loss="stopLoss" />
      </article>

      <article class="panel metrics-panel">
        <div class="panel-header">
          <div>
            <p class="label">实时止损点</p>
            <h2 data-testid="stop-loss">{{ stopLoss ? stopLoss.toFixed(2) : '--' }}</h2>
          </div>
          <ShieldCheck :size="20" />
        </div>
        <dl class="metric-list">
          <div>
            <dt>指标</dt>
            <dd>{{ snapshot?.indicators?.stop_loss?.indicator_type || 'SMA' }}</dd>
          </div>
          <div>
            <dt>周期</dt>
            <dd>{{ snapshot?.indicators?.stop_loss?.period || 20 }}</dd>
          </div>
          <div>
            <dt>乘数</dt>
            <dd>{{ snapshot?.indicators?.stop_loss?.multiplier || 2 }}</dd>
          </div>
          <div>
            <dt>波动率</dt>
            <dd>{{ snapshot?.indicators?.stop_loss?.volatility?.toFixed?.(2) || '--' }}</dd>
          </div>
        </dl>
      </article>

      <article class="panel signal-panel">
        <div class="panel-header">
          <div>
            <p class="label">信号组合</p>
            <h2>{{ snapshot?.indicators?.ma_cross || 'none' }}</h2>
          </div>
          <TrendingUp :size="20" />
        </div>
        <div class="signal-list">
          <div>
            <span>交叉幅度</span>
            <strong>{{ ((snapshot?.indicators?.cross_strength || 0) * 100).toFixed(2) }}%</strong>
          </div>
          <div>
            <span>布林突破</span>
            <strong>{{ snapshot?.indicators?.bollinger?.breakout || 'none' }}</strong>
          </div>
          <div>
            <span>新闻情绪</span>
            <strong>{{ sentiment.label }} ({{ sentiment.score }})</strong>
          </div>
        </div>
        <div class="chips">
          <span v-for="reason in recommendation.reasons" :key="reason" class="chip chip-good">{{ reason }}</span>
          <span v-for="risk in recommendation.risks" :key="risk" class="chip chip-risk">{{ risk }}</span>
        </div>
      </article>

      <article class="panel pnl-panel">
        <div class="panel-header">
          <div>
            <p class="label">盈亏分析</p>
            <h2 data-testid="pnl-amount">{{ pnl ? pnl.amount.toFixed(2) : '--' }}</h2>
          </div>
          <Calculator :size="20" />
        </div>
        <form class="pnl-form" @submit.prevent="updatePnl">
          <label>
            买入价
            <input v-model.number="portfolio.buy_price" data-testid="buy-price" type="number" min="0.01" step="0.01" />
          </label>
          <label>
            持有数量
            <input v-model.number="portfolio.quantity" data-testid="quantity" type="number" min="0.0001" step="0.0001" />
          </label>
          <button type="submit">
            <Calculator :size="16" />
            计算
          </button>
        </form>
        <p class="pnl-percent" :class="{ positive: pnl?.amount >= 0, negative: pnl?.amount < 0 }">
          {{ pnl ? `${pnl.percent.toFixed(2)}%` : '--' }}
        </p>
      </article>
    </section>
  </main>
</template>
