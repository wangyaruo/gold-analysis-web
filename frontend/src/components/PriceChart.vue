<script setup>
import { computed } from 'vue'

const props = defineProps({
  history: {
    type: Array,
    default: () => [],
  },
  stopLoss: {
    type: Number,
    default: null,
  },
  unit: {
    type: String,
    default: 'CNY/g',
  },
})

const width = 760
const height = 320
const paddingTop = 20
const paddingBottom = 38
const paddingLeft = 52
const paddingRight = 24
const latestLabelWidth = 88
const latestLabelHeight = 26

const prices = computed(() => props.history.map((point) => Number(point.display_price ?? point.price)).filter(Number.isFinite))

const bounds = computed(() => {
  const values = prices.value.length ? [...prices.value] : [0]
  if (props.stopLoss) values.push(props.stopLoss)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return {
    min: min - span * 0.1,
    max: max + span * 0.1,
  }
})

const yTicks = computed(() => {
  const {min, max} = bounds.value
  const count = 5
  const step = (max - min) / count
  return Array.from({length: count + 1}, (_, i) => min + step * i)
})

const xLabels = computed(() => {
  const total = props.history.length
  if (!total) return []
  const desired = Math.min(6, total)
  const result = []
  for (let i = 0; i < desired; i += 1) {
    const index = Math.round((i / (desired - 1 || 1)) * (total - 1))
    const point = props.history[index]
    const raw = point?.timestamp || point?.time || point?.date
    let label = ''
    if (raw) {
      const d = new Date(raw)
      if (!Number.isNaN(d.getTime())) {
        label = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      }
    }
    result.push({index, label: label || `${index + 1}` })
  }
  return result
})

function x(index) {
  if (prices.value.length <= 1) return paddingLeft
  return paddingLeft + (index / (prices.value.length - 1)) * (width - paddingLeft - paddingRight)
}

function y(price) {
  const range = bounds.value.max - bounds.value.min || 1
  return height - paddingBottom - ((price - bounds.value.min) / range) * (height - paddingTop - paddingBottom)
}

const linePath = computed(() => {
  if (!prices.value.length) return ''
  return prices.value
    .map((price, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(price).toFixed(2)}`)
    .join(' ')
})

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

const latestPoint = computed(() => {
  if (!prices.value.length) return null
  const index = prices.value.length - 1
  const value = prices.value[index]
  const pointX = x(index)
  const pointY = y(value)
  const labelX = clamp(pointX - latestLabelWidth / 2, paddingLeft, width - paddingRight - latestLabelWidth)
  const labelY = pointY - latestLabelHeight - 12 < paddingTop ? pointY + 12 : pointY - latestLabelHeight - 12

  return {
    value,
    pointX,
    pointY,
    labelX,
    labelY,
    guideY: labelY > pointY ? labelY : labelY + latestLabelHeight,
  }
})

const candleBars = computed(() => {
  const grouped = []
  for (let index = 0; index < prices.value.length; index += 4) {
    const slice = prices.value.slice(index, index + 4)
    if (!slice.length) continue
    const open = slice[0]
    const close = slice[slice.length - 1]
    const high = Math.max(...slice)
    const low = Math.min(...slice)
    grouped.push({
      x: x(index + slice.length / 2),
      openY: y(open),
      closeY: y(close),
      highY: y(high),
      lowY: y(low),
      positive: close >= open,
    })
  }
  return grouped
})
</script>

<template>
  <div class="chart-shell" aria-label="黄金价格走势">
    <svg :viewBox="`0 0 ${width} ${height}`" role="img">
      <defs>
        <linearGradient id="price-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#d4a72c" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#d4a72c" stop-opacity="0.02" />
        </linearGradient>
      </defs>

      <g class="y-axis">
        <g v-for="(tick, index) in yTicks" :key="`y-${index}`">
          <line
            :x1="paddingLeft"
            :x2="width - paddingRight"
            :y1="y(tick)"
            :y2="y(tick)"
            class="grid-line"
          />
          <text :x="paddingLeft - 8" :y="y(tick) + 4" text-anchor="end" class="axis-label">
            {{ tick.toFixed(0) }}
          </text>
        </g>
      </g>

      <g class="x-axis">
        <text
          v-for="label in xLabels"
          :key="`x-${label.index}`"
          :x="x(label.index)"
          :y="height - paddingBottom + 20"
          text-anchor="middle"
          class="axis-label"
        >
          {{ label.label }}
        </text>
      </g>

      <g class="candles">
        <g v-for="(bar, index) in candleBars" :key="index">
          <line :x1="bar.x" :x2="bar.x" :y1="bar.highY" :y2="bar.lowY" :class="bar.positive ? 'up' : 'down'" />
          <rect
            :x="bar.x - 4"
            :y="Math.min(bar.openY, bar.closeY)"
            width="8"
            :height="Math.max(Math.abs(bar.closeY - bar.openY), 2)"
            :class="bar.positive ? 'up-fill' : 'down-fill'"
          />
        </g>
      </g>

      <path v-if="linePath" :d="`${linePath} L ${x(prices.length - 1)} ${height - paddingBottom} L ${paddingLeft} ${height - paddingBottom} Z`" fill="url(#price-fill)" />
      <path v-if="linePath" :d="linePath" class="price-line" />

      <g v-if="latestPoint" class="latest-price-marker">
        <line
          :x1="latestPoint.pointX"
          :x2="latestPoint.pointX"
          :y1="latestPoint.pointY"
          :y2="latestPoint.guideY"
          class="latest-price-guide"
        />
        <circle :cx="latestPoint.pointX" :cy="latestPoint.pointY" r="5" class="latest-price-dot" />
        <rect
          :x="latestPoint.labelX"
          :y="latestPoint.labelY"
          :width="latestLabelWidth"
          :height="latestLabelHeight"
          rx="7"
          class="latest-price-badge"
        />
        <text
          :x="latestPoint.labelX + latestLabelWidth / 2"
          :y="latestPoint.labelY + 17"
          class="latest-price-label"
          data-testid="latest-chart-price"
          text-anchor="middle"
        >
          {{ latestPoint.value.toFixed(2) }}
        </text>
      </g>

      <line
        v-if="stopLoss"
        :x1="paddingLeft"
        :x2="width - paddingRight"
        :y1="y(stopLoss)"
        :y2="y(stopLoss)"
        class="stop-line"
      />
      <g v-if="stopLoss">
        <rect
          :x="width - paddingRight - 132"
          :y="y(stopLoss) - 22"
          width="126"
          height="18"
          rx="5"
          class="stop-badge"
        />
        <text :x="width - paddingRight - 69" :y="y(stopLoss) - 9" text-anchor="middle" class="stop-label">
          止损位 {{ stopLoss.toFixed(2) }}
        </text>
      </g>
    </svg>
  </div>
</template>
