<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  GraphicComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  buildReviewPreview,
  formatReviewPercent,
  hasReviewData,
  pickDefaultReviewItem,
  reviewBarColor,
} from '../utils/monthlyReview.js'

echarts.use([
  BarChart,
  PieChart,
  GridComponent,
  GraphicComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = defineProps({
  review: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  theme: { type: String, default: '' },
})

const dailyEl = ref(null)
const pieEl = ref(null)
const weeklyEl = ref(null)
const selectedItem = ref(null)
let dailyChart = null
let pieChart = null
let weeklyChart = null

const items = computed(() => props.review?.items || [])
const summary = computed(() => props.review?.summary || {})
const weekly = computed(() => props.review?.weekly || [])
const unit = computed(() => props.review?.unit || 'CNY/g')
const themeColor = computed(() => props.theme || props.review?.theme || '#c89a2b')
const hasData = computed(() => hasReviewData(items.value))
const selectedPreview = computed(() => buildReviewPreview(selectedItem.value, unit.value))

function shortDate(raw) {
  const parts = String(raw || '').split('-')
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : raw
}

function itemTooltip(item) {
  if (!item?.has_data) {
    return `<div style="font-weight:700">${item?.date || '--'}</div><div>暂无数据</div>`
  }
  return `<div style="font-weight:700;margin-bottom:4px">${item.date}</div>
    <div>开 ${Number(item.open).toFixed(2)} ${unit.value}</div>
    <div>高 ${Number(item.high).toFixed(2)} ${unit.value}</div>
    <div>低 ${Number(item.low).toFixed(2)} ${unit.value}</div>
    <div>收 ${Number(item.close).toFixed(2)} ${unit.value}</div>
    <div>日涨跌 ${formatReviewPercent(item.change_percent)}</div>
    <div>日内最大涨幅 ${formatReviewPercent(item.intraday_range_percent)}</div>`
}

function markPointFor(day, name, color) {
  if (!day?.date) return null
  return {
    name,
    coord: [shortDate(day.date), Number(day.change_percent) * 100],
    value: formatReviewPercent(day.change_percent),
    itemStyle: { color },
    label: {
      color,
      fontWeight: 800,
      backgroundColor: 'rgba(255,255,255,0.92)',
      borderColor: color,
      borderWidth: 1,
      borderRadius: 6,
      padding: [4, 7],
    },
  }
}

function buildDailyOption() {
  const dates = items.value.map((item) => shortDate(item.date))
  const values = items.value.map((item) => (item.has_data ? Number(item.change_percent) * 100 : 0))
  const markData = [
    markPointFor(summary.value.best_day, '最高', '#45a365'),
    markPointFor(summary.value.worst_day, '最低', '#e95a4f'),
  ].filter(Boolean)
  return {
    animation: false,
    grid: { left: 32, right: 16, top: 34, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#eadfc9',
      textStyle: { color: '#332918', fontSize: 12 },
      formatter: (params) => itemTooltip(items.value[params?.[0]?.dataIndex]),
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#eadfc9' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#8b8171',
        fontSize: 10,
        interval: (index) => index === 0 || index === dates.length - 1 || index % 4 === 0,
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#8b8171', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#f0e8dc' } },
    },
    series: [{
      name: '每日涨跌幅',
      type: 'bar',
      data: items.value.map((item, index) => ({
        value: values[index],
        itemStyle: { color: reviewBarColor(item, themeColor.value) },
      })),
      barMaxWidth: 12,
      markPoint: { symbol: 'circle', symbolSize: 8, data: markData },
    }],
  }
}

function buildPieOption() {
  const up = Number(summary.value.up_days || 0)
  const down = Number(summary.value.down_days || 0)
  const flat = Number(summary.value.flat_days || 0)
  const trading = Number(summary.value.trading_days || 0)
  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: (param) => `${param.name}: ${param.value}天 (${param.percent}%)`,
    },
    legend: {
      bottom: 0,
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#8b8171', fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['52%', '74%'],
      center: ['50%', '44%'],
      label: { show: false },
      data: [
        { name: '上涨', value: up, itemStyle: { color: '#45a365' } },
        { name: '下跌', value: down, itemStyle: { color: '#e95a4f' } },
        { name: '平盘', value: flat, itemStyle: { color: themeColor.value } },
      ].filter((item) => item.value > 0),
    }],
    graphic: [{
      type: 'text',
      left: 'center',
      top: '38%',
      style: {
        text: `${trading}天\n交易日`,
        textAlign: 'center',
        fill: '#3a2b18',
        fontSize: 18,
        fontWeight: 800,
        lineHeight: 26,
      },
    }],
  }
}

function buildWeeklyOption() {
  return {
    animation: false,
    grid: { left: 34, right: 16, top: 26, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: (params) => {
        const index = params?.[0]?.dataIndex ?? 0
        const item = weekly.value[index]
        return `<div style="font-weight:700">${item.label}</div>
          <div>${item.start_date} - ${item.end_date}</div>
          <div>表现 ${formatReviewPercent(item.change_percent)}</div>
          <div>交易日 ${item.trading_days}天</div>`
      },
    },
    xAxis: {
      type: 'category',
      data: weekly.value.map((item) => item.label),
      axisLine: { lineStyle: { color: '#eadfc9' } },
      axisTick: { show: false },
      axisLabel: { color: '#8b8171', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#8b8171', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#f0e8dc' } },
    },
    series: [{
      name: '周度表现',
      type: 'bar',
      data: weekly.value.map((item) => {
        const value = item.change_percent == null ? 0 : Number(item.change_percent) * 100
        return {
          value,
          itemStyle: { color: value > 0 ? '#45a365' : value < 0 ? '#e95a4f' : themeColor.value },
        }
      }),
      barMaxWidth: 42,
    }],
  }
}

function render() {
  if (!dailyChart || !pieChart || !weeklyChart) return
  if (!hasData.value) return
  dailyChart.setOption(buildDailyOption(), true)
  pieChart.setOption(buildPieOption(), true)
  weeklyChart.setOption(buildWeeklyOption(), true)
}

function initCharts() {
  if (!dailyEl.value || !pieEl.value || !weeklyEl.value) return
  if (!dailyChart) {
    dailyChart = echarts.init(dailyEl.value, null, { renderer: 'canvas' })
    dailyChart.on('click', (params) => {
      const item = items.value[params.dataIndex]
      if (item?.has_data) selectedItem.value = item
    })
  }
  if (!pieChart) pieChart = echarts.init(pieEl.value, null, { renderer: 'canvas' })
  if (!weeklyChart) weeklyChart = echarts.init(weeklyEl.value, null, { renderer: 'canvas' })
}

function handleResize() {
  dailyChart?.resize()
  pieChart?.resize()
  weeklyChart?.resize()
}

onMounted(() => {
  nextTick(() => {
    initCharts()
    render()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  dailyChart?.dispose()
  pieChart?.dispose()
  weeklyChart?.dispose()
  dailyChart = null
  pieChart = null
  weeklyChart = null
  window.removeEventListener('resize', handleResize)
})

watch(items, () => {
  selectedItem.value = pickDefaultReviewItem(items.value)
  nextTick(() => {
    initCharts()
    render()
    handleResize()
  })
}, { deep: true, immediate: true })

watch(themeColor, () => {
  nextTick(() => {
    render()
  })
})
</script>

<template>
  <section class="monthly-review" data-testid="monthly-review" :style="{ '--review-theme': themeColor }">
    <div class="review-head">
      <div>
        <p class="card-label">30天数据预览</p>
        <h2>{{ review?.label || '当前渠道' }}</h2>
      </div>
      <div class="review-summary-strip">
        <span>交易 {{ summary.trading_days || 0 }} 天</span>
        <span class="review-up">上涨 {{ summary.up_days || 0 }} 天</span>
        <span class="review-down">下跌 {{ summary.down_days || 0 }} 天</span>
        <span>缺失 {{ summary.missing_days || 0 }} 天</span>
      </div>
    </div>

    <div v-if="loading" class="review-empty">30天复盘加载中</div>
    <div v-else-if="!hasData" class="review-empty" data-testid="monthly-review-empty">
      暂无30天复盘数据
    </div>
    <div v-show="!loading && hasData" class="review-grid">
      <article class="review-panel review-daily">
        <div class="review-panel-head">
          <strong>每日涨跌幅</strong>
          <span>单位：%</span>
        </div>
        <div ref="dailyEl" class="review-chart"></div>
      </article>

      <article class="review-panel review-pie">
        <div class="review-panel-head">
          <strong>涨跌天数占比</strong>
          <span>{{ formatReviewPercent(summary.cumulative_change_percent) }}</span>
        </div>
        <div ref="pieEl" class="review-chart"></div>
        <div class="review-preview" data-testid="monthly-review-preview">
          <span>{{ selectedPreview.date }}</span>
          <strong>{{ selectedPreview.change }}</strong>
          <span>{{ selectedPreview.price }}</span>
          <span>{{ selectedPreview.range }}</span>
        </div>
      </article>

      <article class="review-panel review-weekly">
        <div class="review-panel-head">
          <strong>周度表现</strong>
          <span>单位：%</span>
        </div>
        <div ref="weeklyEl" class="review-chart"></div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.monthly-review {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 3px solid var(--review-theme);
  padding-top: 12px;
}

.review-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}

.review-head h2 {
  margin: 3px 0 0;
  font-size: 1.02rem;
  line-height: 1.2;
  color: var(--review-theme);
}

.review-summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  font-size: 0.78rem;
  color: var(--ink-soft);
}

.review-summary-strip span {
  padding: 5px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--line);
}

.review-up {
  color: var(--green);
}

.review-down {
  color: var(--red);
}

.review-grid {
  display: grid;
  grid-template-columns: 1.35fr 1fr 1.35fr;
  gap: 12px;
}

.review-panel {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--review-theme) 8%, #fff), rgba(255, 255, 255, 0.82));
  padding: 12px;
}

.review-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--ink);
  font-size: 0.88rem;
}

.review-panel-head span {
  color: var(--ink-soft);
  font-size: 0.76rem;
}

.review-chart {
  width: 100%;
  height: 220px;
}

.review-preview {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 10px;
  padding: 9px 10px;
  border-radius: 8px;
  background: var(--bg-soft);
  color: var(--ink-soft);
  font-size: 0.76rem;
}

.review-preview strong {
  color: var(--ink);
}

.review-empty {
  display: grid;
  place-items: center;
  min-height: 190px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  color: var(--ink-soft);
  background: rgba(255, 255, 255, 0.58);
}

@media (max-width: 920px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
