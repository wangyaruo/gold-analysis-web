<script setup>
import {computed} from 'vue'

const props = defineProps({
  history: {
    type: Array,
    default: () => [],
  },
  positive: {
    type: Boolean,
    default: true,
  },
})

const width = 280
const height = 70

const prices = computed(() =>
  props.history
    .map((point) => Number(point.display_price ?? point.price))
    .filter(Number.isFinite)
    .slice(-24),
)

const bounds = computed(() => {
  const values = prices.value.length ? prices.value : [0, 1]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return {min: min - span * 0.1, max: max + span * 0.1}
})

function x(index) {
  if (prices.value.length <= 1) return 0
  return (index / (prices.value.length - 1)) * width
}

function y(price) {
  const range = bounds.value.max - bounds.value.min || 1
  return height - ((price - bounds.value.min) / range) * height
}

const linePath = computed(() => {
  if (!prices.value.length) return ''
  return prices.value
    .map((price, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(price).toFixed(2)}`)
    .join(' ')
})

const areaPath = computed(() => {
  if (!prices.value.length) return ''
  return `${linePath.value} L ${width} ${height} L 0 ${height} Z`
})

const strokeColor = computed(() => (props.positive ? '#10b981' : '#ef4444'))
const gradientId = computed(() => (props.positive ? 'mini-pnl-up' : 'mini-pnl-down'))
</script>

<template>
  <div class="mini-pnl-chart">
    <svg :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="mini-pnl-up" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#10b981" stop-opacity="0.28"/>
          <stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="mini-pnl-down" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#ef4444" stop-opacity="0.28"/>
          <stop offset="100%" stop-color="#ef4444" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path v-if="areaPath" :d="areaPath" :fill="`url(#${gradientId})`"/>
      <path
        v-if="linePath"
        :d="linePath"
        fill="none"
        :stroke="strokeColor"
        stroke-width="2"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
    </svg>
  </div>
</template>
