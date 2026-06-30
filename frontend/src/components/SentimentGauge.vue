<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  SENTIMENT_SEGMENTS,
  buildSentimentPreview,
  getSentimentSegment,
  getSentimentSegmentByKey,
} from '../utils/sentimentGauge.js'

echarts.use([GaugeChart, TooltipComponent, CanvasRenderer])

const props = defineProps({
  value: { type: Number, default: 50 },
  mood: { type: String, default: '中性' },
  sentiment: { type: Object, default: () => ({}) },
})

const chartShell = ref(null)
const chartEl = ref(null)
const lockedKey = ref('')
const hoverKey = ref('')
let chartInstance = null

const safeValue = computed(() => Math.max(0, Math.min(100, Number(props.value) || 0)))
const currentSegment = computed(() => getSentimentSegment(safeValue.value))
const activeKey = computed(() => hoverKey.value || lockedKey.value || currentSegment.value.key)
const activeSegment = computed(() => getSentimentSegmentByKey(activeKey.value) || currentSegment.value)
const score = computed(() => Number(props.sentiment?.score || 0))
const positiveHits = computed(() => props.sentiment?.positive_hits || [])
const negativeHits = computed(() => props.sentiment?.negative_hits || [])
const articleCount = computed(() => Number(props.sentiment?.article_count || 0))
const preview = computed(() => buildSentimentPreview({
  value: safeValue.value,
  score: score.value,
  articleCount: articleCount.value,
  positiveHits: positiveHits.value,
  negativeHits: negativeHits.value,
  segmentKey: activeKey.value,
}))
const isLocked = computed(() => Boolean(lockedKey.value))

function withAlpha(hex, alpha) {
  const clean = String(hex).replace('#', '')
  const r = parseInt(clean.slice(0, 2), 16)
  const g = parseInt(clean.slice(2, 4), 16)
  const b = parseInt(clean.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function segmentColor(segment) {
  if (!activeKey.value || segment.key === activeKey.value) return segment.color
  return withAlpha(segment.color, 0.3)
}

function buildOption() {
  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: `${preview.value.title}<br/>情绪指数 ${Math.round(safeValue.value)}<br/>情绪分 ${preview.value.scoreText}`,
    },
    series: [{
      type: 'gauge',
      min: 0,
      max: 100,
      startAngle: 180,
      endAngle: 0,
      center: ['50%', '78%'],
      radius: '106%',
      splitNumber: 4,
      axisLine: {
        roundCap: true,
        lineStyle: {
          width: 12,
          color: SENTIMENT_SEGMENTS.map((segment) => [segment.max / 100, segmentColor(segment)]),
        },
      },
      pointer: {
        show: true,
        length: '62%',
        width: 4,
        itemStyle: {
          color: currentSegment.value.color,
        },
      },
      anchor: {
        show: true,
        size: 7,
        itemStyle: {
          color: currentSegment.value.color,
          borderColor: '#fff8e8',
          borderWidth: 2,
        },
      },
      axisTick: { show: false },
      splitLine: {
        distance: -16,
        length: 7,
        lineStyle: {
          color: '#fff8e8',
          width: 2,
        },
      },
      axisLabel: {
        distance: -2,
        color: '#8b8171',
        fontSize: 9,
        formatter: (value) => String(Math.round(value)),
      },
      detail: { show: false },
      data: [{ value: safeValue.value, name: preview.value.title }],
    }],
  }
}

function renderChart() {
  if (!chartInstance) return
  chartInstance.setOption(buildOption(), true)
}

function initChart() {
  if (!chartEl.value || chartInstance) return
  chartInstance = echarts.init(chartEl.value, null, { renderer: 'canvas' })
  renderChart()
}

function keyFromPointer(event) {
  if (!chartShell.value) return ''
  const rect = chartShell.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100))
  return getSentimentSegment(ratio).key
}

function previewSegment(key) {
  hoverKey.value = key
}

function clearPreview() {
  hoverKey.value = ''
}

function toggleSegment(key) {
  lockedKey.value = lockedKey.value === key || key === currentSegment.value.key ? '' : key
  hoverKey.value = ''
}

function handleChartMove(event) {
  previewSegment(keyFromPointer(event))
}

function handleChartClick(event) {
  const key = keyFromPointer(event)
  if (key) toggleSegment(key)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  nextTick(() => {
    initChart()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
  window.removeEventListener('resize', handleResize)
})

watch([safeValue, activeKey, score, positiveHits, negativeHits, articleCount], () => {
  nextTick(() => {
    initChart()
    renderChart()
    handleResize()
  })
}, { deep: true })
</script>

<template>
  <section
    class="sentiment-gauge"
    data-testid="sentiment-gauge"
    :style="{ '--sentiment-active': activeSegment.color }"
  >
    <div
      ref="chartShell"
      class="sentiment-chart-shell"
      role="button"
      tabindex="0"
      aria-label="市场情绪交互仪表盘"
      @mousemove="handleChartMove"
      @mouseleave="clearPreview"
      @click="handleChartClick"
    >
      <div ref="chartEl" class="sentiment-chart"></div>
      <div class="sentiment-readout">
        <strong data-testid="sentiment-value">{{ Math.round(safeValue) }}</strong>
        <span data-testid="sentiment-mood">{{ currentSegment.mood || mood }}</span>
      </div>
    </div>

    <div class="sentiment-preview" data-testid="sentiment-preview">
      <div class="sentiment-preview-head">
        <span>{{ preview.title }}</span>
        <strong>情绪分 {{ preview.scoreText }}</strong>
      </div>
      <p>{{ preview.description }}</p>
      <div class="sentiment-hit-row" :class="{ empty: !preview.hits.length }">
        <span v-if="!preview.hits.length">{{ preview.hitsText }}</span>
        <span v-for="hit in preview.hits" v-else :key="hit" class="sentiment-hit">{{ hit }}</span>
      </div>
      <small>{{ preview.articleText }}<span v-if="isLocked"> · 已锁定</span></small>
    </div>

    <div class="sentiment-zone-grid" aria-label="情绪区间">
      <button
        v-for="segment in SENTIMENT_SEGMENTS"
        :key="segment.key"
        type="button"
        class="sentiment-zone"
        :class="{ active: segment.key === activeKey, current: segment.key === currentSegment.key }"
        :style="{ '--zone-color': segment.color }"
        :data-testid="`sentiment-zone-${segment.key}`"
        @mouseenter="previewSegment(segment.key)"
        @mouseleave="clearPreview"
        @click="toggleSegment(segment.key)"
      >
        {{ segment.label }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.sentiment-gauge {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 6px 9px;
  width: 100%;
  min-width: 0;
}

.sentiment-chart-shell {
  position: relative;
  width: 96px;
  height: 78px;
  cursor: pointer;
  outline: none;
}

.sentiment-chart {
  width: 100%;
  height: 100%;
}

.sentiment-chart-shell:focus-visible {
  border-radius: 8px;
  box-shadow: 0 0 0 3px rgba(201, 150, 35, 0.24);
}

.sentiment-readout {
  position: absolute;
  left: 50%;
  bottom: 0;
  display: grid;
  justify-items: center;
  transform: translateX(-50%);
  pointer-events: none;
}

.sentiment-readout strong {
  color: var(--sentiment-active);
  font-size: 1.22rem;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.sentiment-readout span {
  margin-top: 1px;
  color: var(--ink-soft);
  font-size: 0.62rem;
  font-weight: 800;
  white-space: nowrap;
}

.sentiment-preview {
  min-width: 0;
  align-self: stretch;
  padding: 7px 8px;
  border: 1px solid rgba(218, 190, 132, 0.55);
  border-radius: 8px;
  background: rgba(255, 250, 239, 0.7);
}

.sentiment-preview-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink);
  font-size: 0.72rem;
  font-weight: 800;
}

.sentiment-preview-head strong {
  color: var(--sentiment-active);
  white-space: nowrap;
}

.sentiment-preview p {
  display: -webkit-box;
  margin: 3px 0 5px;
  color: var(--ink-soft);
  font-size: 0.62rem;
  line-height: 1.25;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sentiment-hit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  min-height: 18px;
}

.sentiment-hit-row.empty {
  align-items: center;
  color: var(--ink-muted);
  font-size: 0.6rem;
}

.sentiment-hit {
  max-width: 88px;
  padding: 2px 5px;
  overflow: hidden;
  border-radius: 6px;
  background: rgba(37, 158, 118, 0.1);
  color: #17775b;
  font-size: 0.58rem;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sentiment-preview small {
  display: block;
  margin-top: 4px;
  color: var(--ink-muted);
  font-size: 0.58rem;
}

.sentiment-zone-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
}

.sentiment-zone {
  min-width: 0;
  padding: 4px 2px;
  border: 1px solid rgba(218, 190, 132, 0.5);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.64);
  color: var(--ink-soft);
  font-size: 0.56rem;
  font-weight: 800;
  line-height: 1;
  cursor: pointer;
}

.sentiment-zone.active,
.sentiment-zone:hover {
  border-color: var(--zone-color);
  background: color-mix(in srgb, var(--zone-color) 14%, white);
  color: var(--zone-color);
}

.sentiment-zone.current::after {
  content: "";
  display: block;
  width: 16px;
  height: 2px;
  margin: 3px auto 0;
  border-radius: 999px;
  background: var(--zone-color);
}

@media (max-width: 620px) {
  .sentiment-gauge {
    grid-template-columns: 108px minmax(0, 1fr);
  }

  .sentiment-chart-shell {
    width: 108px;
    height: 84px;
  }
}
</style>
