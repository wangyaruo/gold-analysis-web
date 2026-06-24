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
})

const width = 760
const height = 300
const padding = 28

const prices = computed(() => props.history.map((point) => Number(point.price)).filter(Number.isFinite))

const bounds = computed(() => {
  const values = prices.value.length ? prices.value : [0]
  if (props.stopLoss) values.push(props.stopLoss)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return {
    min: min - span * 0.08,
    max: max + span * 0.08,
  }
})

function x(index) {
  if (prices.value.length <= 1) return padding
  return padding + (index / (prices.value.length - 1)) * (width - padding * 2)
}

function y(price) {
  const range = bounds.value.max - bounds.value.min || 1
  return height - padding - ((price - bounds.value.min) / range) * (height - padding * 2)
}

const linePath = computed(() => {
  if (!prices.value.length) return ''
  return prices.value
    .map((price, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(price).toFixed(2)}`)
    .join(' ')
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
          <stop offset="0%" stop-color="#d4a72c" stop-opacity="0.32" />
          <stop offset="100%" stop-color="#d4a72c" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <line
        v-for="tick in 4"
        :key="tick"
        :x1="padding"
        :x2="width - padding"
        :y1="padding + tick * ((height - padding * 2) / 5)"
        :y2="padding + tick * ((height - padding * 2) / 5)"
        class="grid-line"
      />
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
      <path v-if="linePath" :d="`${linePath} L ${x(prices.length - 1)} ${height - padding} L ${padding} ${height - padding} Z`" fill="url(#price-fill)" />
      <path v-if="linePath" :d="linePath" class="price-line" />
      <line
        v-if="stopLoss"
        :x1="padding"
        :x2="width - padding"
        :y1="y(stopLoss)"
        :y2="y(stopLoss)"
        class="stop-line"
      />
      <text v-if="stopLoss" :x="width - padding - 86" :y="y(stopLoss) - 8" class="stop-label">
        Stop {{ stopLoss.toFixed(2) }}
      </text>
    </svg>
  </div>
</template>
