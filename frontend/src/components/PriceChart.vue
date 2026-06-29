<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  MarkLineComponent,
  CanvasRenderer,
])

const props = defineProps({
  candles: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] },
  stopLoss: { type: Number, default: null },
  unit: { type: String, default: 'CNY/g' },
  period: { type: String, default: '1day' },
})

const chartContainer = ref(null)
let chartInstance = null

// 短周期(分/时/5时)波动极小、价格颗粒粗,用折线更耐看;长周期(日/月)波动大,用蜡烛更专业
const useCandle = computed(() => props.period === '1day' || props.period === '1month')

const bars = computed(() => {
  if (props.candles.length) {
    return props.candles
      .map((c) => ({
        time: c.time,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      }))
      .filter((c) => Number.isFinite(c.close))
  }
  return props.history
    .map((p) => {
      const v = Number(p.display_price ?? p.price)
      return { time: p.timestamp || p.time, open: v, high: v, low: v, close: v }
    })
    .filter((c) => Number.isFinite(c.close))
})

function fmtTime(raw) {
  if (!raw) return ''
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw)
  const p = (n) => String(n).padStart(2, '0')
  if (props.period === '1month') return `${d.getFullYear()}-${p(d.getMonth() + 1)}`
  if (props.period === '1day') return `${p(d.getMonth() + 1)}-${p(d.getDate())}`
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const buildOption = () => {
  const data = bars.value
  const categories = data.map((c) => fmtTime(c.time))
  const ohlc = data.map((c) => [c.open, c.close, c.low, c.high])
  const closeLine = data.map((c) => c.close)
  const decimals = useCandle.value ? 2 : 3

  const markLine = props.stopLoss
    ? {
        symbol: 'none',
        silent: true,
        lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 },
        label: {
          formatter: `止损位 ${props.stopLoss.toFixed(2)}`,
          position: 'insideStartTop',
          color: '#ef4444',
          fontSize: 11,
        },
        data: [{ yAxis: props.stopLoss }],
      }
    : undefined

  const tooltipFormatter = (params) => {
    const k = params.find((p) => p.seriesName === 'K线')
    if (!k) {
      const p0 = params.find((p) => p.seriesName === '收盘') || params[0]
      const v = Array.isArray(p0.data) ? p0.data[1] : p0.data
      return `<div style="font-weight:600;margin-bottom:3px">${p0.axisValue}</div>
        <div>价格 <b>${Number(v).toFixed(decimals)}</b> ${props.unit}</div>`
    }
    const [open, close, low, high] = k.data.slice(1)
    const color = close >= open ? '#e23b3b' : '#1aa260'
    return `<div style="font-weight:600;margin-bottom:4px">${k.axisValue}</div>
      <div>开 <b>${open.toFixed(decimals)}</b></div>
      <div>高 <b>${high.toFixed(decimals)}</b></div>
      <div>低 <b>${low.toFixed(decimals)}</b></div>
      <div>收 <b style="color:${color}">${close.toFixed(decimals)}</b></div>
      <div style="color:#9b8b63;margin-top:2px">${props.unit}</div>`
  }

  const candleSeries = {
    name: 'K线',
    type: 'candlestick',
    data: ohlc,
    itemStyle: {
      color: '#e23b3b',
      color0: '#1aa260',
      borderColor: '#e23b3b',
      borderColor0: '#1aa260',
    },
    barMaxWidth: 16,
    markLine,
  }

  const lineSeries = {
    name: '收盘',
    type: 'line',
    data: closeLine,
    smooth: true,
    showSymbol: false,
    lineStyle: { color: '#d4a72c', width: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(212,167,44,0.28)' },
          { offset: 1, color: 'rgba(212,167,44,0.02)' },
        ],
      },
    },
    markLine,
  }

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    grid: { left: 8, right: 58, top: 16, bottom: 56, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: '#c79a2e' } },
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8d9b0',
      borderWidth: 1,
      textStyle: { color: '#3a3320', fontSize: 12 },
      formatter: tooltipFormatter,
    },
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: true,
      axisLine: { lineStyle: { color: '#e5ddc6' } },
      axisLabel: { color: '#9b8b63', fontSize: 11, hideOverlap: true },
      axisTick: { show: false },
    },
    yAxis: {
      scale: true,
      position: 'right',
      axisLine: { show: false },
      axisLabel: {
        color: '#9b8b63',
        fontSize: 11,
        formatter: (v) => (useCandle.value ? v.toFixed(0) : v.toFixed(2)),
      },
      splitLine: { lineStyle: { color: '#f0ebdd', type: 'dashed' } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100, zoomOnMouseWheel: true, moveOnMouseMove: true },
      {
        type: 'slider',
        height: 18,
        bottom: 16,
        borderColor: '#e8d9b0',
        fillerColor: 'rgba(212,167,44,0.12)',
        handleStyle: { color: '#d4a72c' },
        dataBackground: { lineStyle: { color: '#d4a72c' }, areaStyle: { color: 'rgba(212,167,44,0.15)' } },
        textStyle: { color: '#9b8b63', fontSize: 10 },
      },
    ],
    series: [useCandle.value ? candleSeries : lineSeries],
  }
}

const render = () => {
  if (!chartInstance) return
  chartInstance.setOption(buildOption(), true)
}

const handleResize = () => chartInstance && chartInstance.resize()

onMounted(() => {
  nextTick(() => {
    if (!chartContainer.value) return
    chartInstance = echarts.init(chartContainer.value, null, { renderer: 'canvas' })
    render()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  window.removeEventListener('resize', handleResize)
})

watch(() => [props.candles, props.stopLoss, props.period], () => {
  nextTick(render)
}, { deep: true })
</script>

<template>
  <div class="chart-shell" aria-label="黄金价格走势">
    <div v-if="!bars.length" class="chart-empty">暂无K线数据</div>
    <div ref="chartContainer" class="echart-box" :style="{ opacity: bars.length ? 1 : 0 }"></div>
  </div>
</template>

<style scoped>
.chart-shell {
  position: relative;
  width: 100%;
}
.echart-box {
  width: 100%;
  height: 340px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-soft, #9b8b63);
  font-size: 0.9rem;
  z-index: 2;
}
</style>
