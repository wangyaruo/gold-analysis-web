<script setup>
import {computed} from 'vue'

const props = defineProps({
  value: {type: Number, default: 50},   // 0-100 情绪指数
  mood: {type: String, default: '中性'},
})

const W = 230
const H = 142
const cx = 115
const cy = 122
const R = 90
const sw = 15

const v = computed(() => Math.max(0, Math.min(100, Number(props.value) || 0)))

function pt(angleDeg, r) {
  const a = (angleDeg * Math.PI) / 180
  return {x: cx + r * Math.cos(a), y: cy - r * Math.sin(a)}
}

// 角度从 180°(左)经顶部到 0°(右)
function arcPath(r, fromDeg, toDeg) {
  const s = pt(fromDeg, r)
  const e = pt(toDeg, r)
  const large = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`
}

const valueAngle = computed(() => 180 * (1 - v.value / 100))
const trackPath = computed(() => arcPath(R, 180, 0))
const activePath = computed(() => arcPath(R, 180, valueAngle.value))

const ticks = computed(() =>
  [0, 25, 50, 75, 100].map((n) => {
    const p = pt(180 * (1 - n / 100), R + 16)
    return {n, x: p.x, y: p.y}
  }),
)

const needle = computed(() => pt(valueAngle.value, R - 6))

const moodColor = computed(() => {
  const x = v.value
  if (x >= 80) return '#1f9d6b'
  if (x >= 60) return '#3aa76d'
  if (x > 40) return '#e0a020'
  if (x > 20) return '#e0801e'
  return '#d6453d'
})
</script>

<template>
  <div class="gauge-container">
    <svg :viewBox="`0 0 ${W} ${H}`" class="gauge-svg" aria-label="市场情绪指数">
      <defs>
        <linearGradient id="gauge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#d6453d"/>
          <stop offset="30%" stop-color="#e0801e"/>
          <stop offset="55%" stop-color="#e6b32a"/>
          <stop offset="100%" stop-color="#1f9d6b"/>
        </linearGradient>
      </defs>

      <path :d="trackPath" class="gauge-track" :stroke-width="sw" fill="none" stroke-linecap="round"/>
      <path :d="activePath" stroke="url(#gauge-grad)" :stroke-width="sw" fill="none" stroke-linecap="round"/>

      <text
        v-for="t in ticks"
        :key="t.n"
        :x="t.x"
        :y="t.y + 4"
        text-anchor="middle"
        class="gauge-tick"
      >{{ t.n }}</text>

      <line :x1="cx" :y1="cy" :x2="needle.x" :y2="needle.y" class="gauge-needle"/>
      <circle :cx="cx" :cy="cy" r="6" class="gauge-hub"/>

      <text :x="cx" :y="cy - 28" text-anchor="middle" class="gauge-value">{{ Math.round(v) }}</text>
      <text :x="cx" :y="cy - 7" text-anchor="middle" class="gauge-mood" :fill="moodColor">{{ mood }}</text>
    </svg>
  </div>
</template>
