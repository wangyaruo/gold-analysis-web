<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  buildAxisLabelLookup,
  buildIntradayTimeline,
  buildIntradayViewportRange,
  buildViewportResetKey,
  buildVisibleExtrema,
  buildYAxisScaleForRange,
  buildZoomMinValueSpan,
  formatDataZoomLabel,
  formatFullTime,
  formatYAxisValue,
} from '../utils/chartAxis.js'

echarts.use([
  CandlestickChart,
  LineChart,
  ScatterChart,
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
  sourceKey: { type: String, default: '' },
})

// 默认可见窗口(=约10个刻度宽). 月线放宽到 12 条, 避免粗略 30 天数据造成自然月标签重复。
const DEFAULT_WINDOW = { '1min': null, '1h': 10, '1day': 10, '1month': 12 }
const INTRADAY_Y_TICK_COUNT = 4

const chartContainer = ref(null)
let chartInstance = null
// 当前缩放窗口(数据索引), null 表示用默认(贴最右/最新)
let zoomStart = null
let zoomEnd = null

const useCandle = computed(() => props.period === '1day' || props.period === '1month')
const useIntradayProfile = computed(() => props.period === '1min')

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

// 默认窗口的起止索引(贴最新)
function defaultRange(data) {
  const n = data.length
  const win = DEFAULT_WINDOW[props.period] || 10
  const end = n - 1
  if (props.period === '1min') return buildIntradayViewportRange(data)
  const start = Math.max(0, end - win + 1)
  return { start, end }
}

function buildXAxisLabels(data, startIndex, endIndex) {
  const lookup = buildAxisLabelLookup(data, props.period, { startIndex, endIndex })
  return {
    showTimeTick: (_index, value) => lookup.values.has(value),
    formatTick: (value, index) => lookup.textByValue.get(value) || lookup.labels[index] || '',
  }
}

const buildOption = () => {
  const timeline = useIntradayProfile.value ? buildIntradayTimeline(bars.value) : null
  const data = timeline?.data || bars.value
  const n = data.length
  const categories = data.map((c) => formatFullTime(c.time, props.period))
  const ohlc = data.map((c) => [c.open, c.close, c.low, c.high])
  const closeLine = data.map((c) => (Number.isFinite(Number(c.close)) ? Number(c.close) : null))
  const decimals = useCandle.value ? 2 : 3

  // 可见窗口: 优先用用户拖动后的, 否则默认贴最新
  let vs = zoomStart
  let ve = zoomEnd
  if (vs == null || ve == null) {
    const r = defaultRange(data)
    vs = r.start
    ve = r.end
  }
  vs = Math.max(0, Math.min(vs, n - 1))
  ve = Math.max(vs, Math.min(ve, n - 1))
  const yStopLoss = useIntradayProfile.value ? null : props.stopLoss
  const yAxisScale = buildYAxisScaleForRange(
    data,
    vs,
    ve,
    yStopLoss,
    useIntradayProfile.value ? INTRADAY_Y_TICK_COUNT : undefined,
  )
  const startPct = n > 1 ? (vs / (n - 1)) * 100 : 0
  const endPct = n > 1 ? (ve / (n - 1)) * 100 : 100
  const { showTimeTick, formatTick } = buildXAxisLabels(data, vs, ve)
  const latestIndex = data.map((item) => item.close).findLastIndex((value) => Number.isFinite(Number(value)))
  const latestPoint = latestIndex >= 0
    ? { category: categories[latestIndex], value: Number(data[latestIndex].close) }
    : null
  const extrema = buildVisibleExtrema(data, vs, ve)

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
  const visibleMarkLine = useIntradayProfile.value ? undefined : markLine

  const tooltipFormatter = (params) => {
    const k = params.find((p) => p.seriesName === 'K线')
    if (!k) {
      const p0 = params.find((p) => p.seriesName === '收盘') || params[0]
      const v = Array.isArray(p0.data) ? p0.data[1] : p0.data
      if (!Number.isFinite(Number(v))) return ''
      const label = formatFullTime(data[p0.dataIndex]?.time || p0.axisValue, props.period)
      return `<div style="font-weight:600;margin-bottom:3px">${label}</div>
        <div>价格 <b>${Number(v).toFixed(decimals)}</b> ${props.unit}</div>`
    }
    const [open, close, low, high] = k.data.slice(1)
    const color = close >= open ? '#e23b3b' : '#1aa260'
    const label = formatFullTime(data[k.dataIndex]?.time || k.axisValue, props.period)
    return `<div style="font-weight:600;margin-bottom:4px">${label}</div>
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

  const highMarkerData = extrema.high
    ? [{
        value: [categories[extrema.high.index], extrema.high.value],
        markerLabel: Number(extrema.high.value).toFixed(2),
        label: { position: 'top', distance: 8 },
      }]
    : []
  const lowMarkerData = extrema.low
    ? [{
        value: [categories[extrema.low.index], extrema.low.value],
        markerLabel: Number(extrema.low.value).toFixed(2),
        label: { position: 'bottom', distance: 8 },
      }]
    : []

  function extremaSeries(name, markerData, color, backgroundColor, borderColor) {
    return {
      name,
      type: 'scatter',
      data: markerData,
      symbolSize: 1,
      silent: true,
      z: 5,
      itemStyle: { color: 'rgba(197, 138, 18, 0)' },
      label: {
        show: true,
        formatter: (param) => param.data?.markerLabel || '',
        color,
        fontSize: 13,
        fontWeight: 700,
        fontFamily: 'Inter, "Noto Sans SC", sans-serif',
        backgroundColor,
        borderColor,
        borderWidth: 1,
        borderRadius: 7,
        padding: [6, 10],
        shadowColor: 'rgba(28, 70, 46, 0.10)',
        shadowBlur: 10,
        shadowOffsetY: 3,
      },
      tooltip: { show: false },
    }
  }

  const highSeries = extremaSeries(
    '最高点',
    highMarkerData,
    '#b91c1c',
    'rgba(254, 226, 226, 0.96)',
    'rgba(248, 113, 113, 0.45)',
  )
  const lowSeries = extremaSeries(
    '最低点',
    lowMarkerData,
    '#15803d',
    'rgba(220, 252, 231, 0.96)',
    'rgba(74, 222, 128, 0.45)',
  )

  const invisibleTooltipSeries = {
    name: '高低点',
    type: 'scatter',
    data: [],
    symbolSize: 1,
    silent: true,
    tooltip: { show: false },
  }

  const latestScatterData = latestPoint ? [[latestPoint.category, latestPoint.value]] : []
  const latestHaloSeries = {
    name: '当前光晕',
    type: 'scatter',
    data: latestScatterData,
    symbol: 'circle',
    symbolSize: 26,
    silent: true,
    z: 3,
    itemStyle: {
      color: 'rgba(197, 138, 18, 0.20)',
      borderColor: 'rgba(197, 138, 18, 0.12)',
      borderWidth: 2,
    },
    tooltip: { show: false },
  }

  const latestDotSeries = {
    name: '当前点',
    type: 'scatter',
    data: latestScatterData,
    symbol: 'circle',
    symbolSize: 8,
    silent: true,
    z: 6,
    itemStyle: {
      color: '#c58a12',
      borderColor: '#f7dfaa',
      borderWidth: 2,
    },
    tooltip: { show: false },
  }

  const lineSeries = {
    name: '收盘',
    type: 'line',
    data: closeLine,
    smooth: useIntradayProfile.value ? 0.18 : true,
    showSymbol: false,
    connectNulls: true,
    z: 4,
    lineStyle: {
      color: useIntradayProfile.value ? '#c58a12' : '#d4a72c',
      width: useIntradayProfile.value ? 2.2 : 2,
      cap: 'round',
      join: 'round',
    },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: useIntradayProfile.value ? 'rgba(232, 169, 44, 0.52)' : 'rgba(212,167,44,0.28)' },
          { offset: 0.62, color: useIntradayProfile.value ? 'rgba(242, 193, 82, 0.20)' : 'rgba(212,167,44,0.09)' },
          { offset: 1, color: 'rgba(212,167,44,0.02)' },
        ],
      },
    },
    markLine: visibleMarkLine,
  }

  const minValueSpan = buildZoomMinValueSpan(props.period, n)
  const dataZoom = [
    {
      type: 'inside',
      start: startPct,
      end: endPct,
      zoomOnMouseWheel: true,
      moveOnMouseMove: false,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: true,
      minValueSpan,
    },
    {
      type: 'slider',
      height: 24,
      bottom: 12,
      start: startPct,
      end: endPct,
      minValueSpan,
      borderColor: '#e8d9b0',
      fillerColor: 'rgba(212,167,44,0.16)',
      handleStyle: { color: '#d4a72c' },
      moveHandleStyle: { color: '#d4a72c' },
      brushSelect: false,
      dataBackground: { lineStyle: { color: '#d4a72c' }, areaStyle: { color: 'rgba(212,167,44,0.15)' } },
      selectedDataBackground: { lineStyle: { color: '#c79a2e' }, areaStyle: { color: 'rgba(212,167,44,0.25)' } },
      labelFormatter: (value) => {
        const index = Math.round(Number(value))
        const point = index >= 0 && index < data.length ? data[index] : null
        return point ? formatDataZoomLabel(point.time, props.period) : ''
      },
      textStyle: { color: '#9b8b63', fontSize: 10 },
    },
  ]
  const extremaSeriesList = [highSeries, lowSeries, invisibleTooltipSeries]
  const intradaySeries = [lineSeries, ...extremaSeriesList, latestHaloSeries, latestDotSeries]

  return {
    animation: false,
    grid: useIntradayProfile.value
      ? { left: 8, right: 26, top: 32, bottom: 54, containLabel: true }
      : { left: 8, right: 58, top: 16, bottom: 64, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: useIntradayProfile.value ? 'line' : 'cross',
        label: { backgroundColor: '#c79a2e' },
        lineStyle: { color: 'rgba(197, 138, 18, 0.32)', width: 1 },
      },
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8d9b0',
      borderWidth: 1,
      textStyle: { color: '#3a3320', fontSize: 12 },
      confine: true,
      formatter: tooltipFormatter,
    },
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: !useIntradayProfile.value,
      axisLine: { show: !useIntradayProfile.value, lineStyle: { color: '#e5ddc6' } },
      axisLabel: {
        color: useIntradayProfile.value ? '#8d9298' : '#9b8b63',
        fontSize: useIntradayProfile.value ? 13 : 11,
        interval: showTimeTick,
        hideOverlap: false,
        showMinLabel: true,
        showMaxLabel: true,
        margin: useIntradayProfile.value ? 14 : 10,
        formatter: formatTick,
      },
      axisTick: {
        show: !useIntradayProfile.value,
        alignWithLabel: true,
        interval: showTimeTick,
        length: 4,
        lineStyle: { color: '#d8ca9e' },
      },
    },
    yAxis: {
      min: yAxisScale.min,
      max: yAxisScale.max,
      interval: yAxisScale.interval,
      splitNumber: yAxisScale.splitNumber,
      scale: false,
      position: useIntradayProfile.value ? 'left' : 'right',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: useIntradayProfile.value ? '#8d9298' : '#9b8b63',
        fontSize: useIntradayProfile.value ? 13 : 11,
        margin: useIntradayProfile.value ? 12 : 8,
        formatter: (v) => formatYAxisValue(v, yAxisScale.interval),
      },
      splitLine: {
        lineStyle: {
          color: useIntradayProfile.value ? '#eceff3' : '#f0ebdd',
          type: 'dashed',
          width: 1,
        },
      },
    },
    dataZoom,
    series: useCandle.value ? [candleSeries, ...extremaSeriesList] : useIntradayProfile.value ? intradaySeries : [lineSeries, ...extremaSeriesList],
  }
}

const render = () => {
  if (!chartInstance) return
  chartInstance.setOption(buildOption(), true)
}

// 拖动/缩放滑块: 记录可见窗口索引, 并按可见区间重算纵轴
const onDataZoom = () => {
  if (!chartInstance) return
  const opt = chartInstance.getOption()
  const dz = (opt.dataZoom || [])[0]
  if (!dz) return
  const data = useIntradayProfile.value ? buildIntradayTimeline(bars.value).data : bars.value
  const n = data.length
  if (n < 1) return
  const sPct = Number(dz.start ?? 0)
  const ePct = Number(dz.end ?? 100)
  zoomStart = Math.round((sPct / 100) * (n - 1))
  zoomEnd = Math.round((ePct / 100) * (n - 1))
  const { showTimeTick, formatTick } = buildXAxisLabels(data, zoomStart, zoomEnd)

  // 拖动后同步更新可见窗口内的 X/Y 轴刻度, 不重置 dataZoom 本身。
  const y = buildYAxisScaleForRange(
    data,
    zoomStart,
    zoomEnd,
    useIntradayProfile.value ? null : props.stopLoss,
    useIntradayProfile.value ? INTRADAY_Y_TICK_COUNT : undefined,
  )
  chartInstance.setOption({
    xAxis: {
      axisLabel: {
        interval: showTimeTick,
        hideOverlap: false,
        showMinLabel: true,
        showMaxLabel: true,
        formatter: formatTick,
      },
      axisTick: { interval: showTimeTick },
    },
    yAxis: { min: y.min, max: y.max, interval: y.interval, splitNumber: y.splitNumber },
  })
}

const handleResize = () => chartInstance && chartInstance.resize()

onMounted(() => {
  nextTick(() => {
    if (!chartContainer.value) return
    chartInstance = echarts.init(chartContainer.value, null, { renderer: 'canvas' })
    render()
    chartInstance.on('datazoom', onDataZoom)
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

// 切换周期或数据源: 重置缩放回默认; 普通数据刷新继续保留当前缩放。
watch(() => buildViewportResetKey({ period: props.period, sourceKey: props.sourceKey }), () => {
  zoomStart = null
  zoomEnd = null
  nextTick(render)
})

// 数据/止损变化: 保持当前缩放窗口重绘
watch(() => [props.candles, props.stopLoss], () => {
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
  height: var(--price-chart-height, 360px);
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

@media (max-width: 760px) {
  .echart-box {
    height: var(--price-chart-height, 310px);
  }
}
</style>
