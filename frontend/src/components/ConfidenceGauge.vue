<template>
  <div class="confidence-gauge">
    <svg :viewBox="`0 0 200 130`" class="gauge-svg">
      <!-- track -->
      <path :d="arcPath(180, 360)" fill="none" stroke="var(--hm-border)" stroke-width="14" stroke-linecap="round" />
      <!-- value arc -->
      <path v-if="clamped > 0.005" :d="arcPath(180, 180 + 180 * clamped)" fill="none"
        :stroke="bandColor" stroke-width="14" stroke-linecap="round"
        style="filter: drop-shadow(0 0 6px var(--hm-glow));" />
      <!-- needle dot -->
      <g :transform="`translate(${needlePos.x},${needlePos.y})`">
        <circle r="6" :fill="bandColor" stroke="var(--hm-bg)" stroke-width="2" />
      </g>
      <text x="100" y="86" text-anchor="middle" class="score-num">{{ Math.round(score) }}</text>
      <text x="100" y="106" text-anchor="middle" class="score-band">{{ bandLabel }}</text>
    </svg>
    <div class="factors">
      <div v-for="f in factorList" :key="f.key" class="factor">
        <div class="factor-head">
          <span class="factor-label">{{ f.label }}</span>
          <span class="factor-val">{{ Math.round(f.value * 100) }}%</span>
        </div>
        <div class="factor-bar">
          <div class="factor-fill" :style="{ width: (f.value * 100) + '%', background: bandColor }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  score: { type: Number, default: 0 },
  band: { type: String, default: 'low' },
  factors: { type: Object, default: () => ({}) },
})

const { t } = useI18n()

const clamped = computed(() => Math.max(0, Math.min(100, props.score)) / 100)
const bandColor = computed(() => ({
  high: 'var(--hm-pos)',
  medium: 'var(--hm-accent)',
  low: 'var(--hm-neg)',
}[props.band] || 'var(--hm-neutral)'))
const bandLabel = computed(() => t(`analytics.band.${props.band}`))

const FACTOR_LABELS = {
  stabilisation: 'analytics.factors.stabilisation',
  consensus: 'analytics.factors.consensus',
  cascade: 'analytics.factors.cascade',
  sufficiency: 'analytics.factors.sufficiency',
}
const factorList = computed(() =>
  Object.entries(FACTOR_LABELS).map(([key, label]) => ({
    key,
    label: t(label),
    value: Math.max(0, Math.min(1, Number(props.factors[key] ?? 0))),
  })))

function polar(cx, cy, r, deg) {
  const rad = (deg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}
function arcPath(startDeg, endDeg) {
  // semicircle gauge from 180° (left) to 0° (right)
  const cx = 100, cy = 100, r = 80
  const s = polar(cx, cy, r, 180 + (startDeg + 90) * 1.8 / 1.8) // placeholder
  void s
  const a0 = 180 + (startDeg + 90) * (180 / 180)
  const a1 = 180 + (endDeg + 90) * (180 / 180)
  const p0 = polar(cx, cy, r, a0)
  const p1 = polar(cx, cy, r, a1)
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0
  return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`
}
const needlePos = computed(() => {
  const a = 180 + 180 * clamped.value
  const rad = (a * Math.PI) / 180
  return { x: 100 + 80 * Math.cos(rad), y: 100 + 80 * Math.sin(rad) }
})
</script>

<style scoped>
.confidence-gauge { text-align: center; }
.gauge-svg { width: 210px; height: 140px; }
.score-num {
  font-size: 34px; font-weight: 800;
  fill: var(--hm-text); font-family: var(--font-sans);
}
.score-band {
  font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase;
  fill: var(--hm-text-muted); font-family: var(--font-mono);
}
.factors { margin-top: 10px; display: grid; gap: 10px; text-align: left; }
.factor-head {
  display: flex; justify-content: space-between;
  font-size: 0.72rem; color: var(--hm-text-muted);
  margin-bottom: 4px; letter-spacing: 0.3px;
}
.factor-val { color: var(--hm-text); font-family: var(--font-mono); }
.factor-bar {
  height: 6px; border-radius: 3px;
  background: var(--hm-bg-soft); border: 1px solid var(--hm-border-soft);
  overflow: hidden;
}
.factor-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
</style>
