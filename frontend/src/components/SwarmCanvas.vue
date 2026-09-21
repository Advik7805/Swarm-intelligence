<template>
  <canvas ref="canvasRef" class="swarm-canvas" aria-hidden="true"></canvas>
</template>

<script setup>
/**
 * SwarmCanvas — HiveMind signature hero animation.
 *
 * A boid-style swarm: hundreds of amber agents drift in murmuration
 * patterns, periodically converging toward a moving "consensus point"
 * — a visual metaphor for swarm intelligence converging on a prediction.
 * Theme-aware (reads CSS variables), resolution-aware, and pauses when
 * the tab is hidden.
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref(null)
let rafId = null
let cleanup = null

onMounted(() => {
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  let W = 0, H = 0, dpr = 1

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2)
    W = canvas.clientWidth
    H = canvas.clientHeight
    canvas.width = W * dpr
    canvas.height = H * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  window.addEventListener('resize', resize)

  const css = (name, fallback) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

  const N = Math.min(140, Math.max(70, Math.floor(W / 12)))
  const agents = Array.from({ length: N }, () => ({
    x: Math.random() * W,
    y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.8,
    vy: (Math.random() - 0.5) * 0.8,
    r: 1 + Math.random() * 2.2,
    phase: Math.random() * Math.PI * 2,
  }))

  const target = { x: W * 0.7, y: H * 0.4, t: 0 }
  let visible = !document.hidden
  const onVis = () => { visible = !document.hidden }
  document.addEventListener('visibilitychange', onVis)

  const ACCENT = () => css('--hm-accent', '#F0A500')
  const GRID = () => css('--hm-grid', 'rgba(230,237,243,0.07)')

  function frame() {
    rafId = requestAnimationFrame(frame)
    if (!visible) return

    target.t += 0.004
    target.x = W * (0.5 + 0.32 * Math.cos(target.t * 1.7))
    target.y = H * (0.45 + 0.3 * Math.sin(target.t * 2.3))

    ctx.clearRect(0, 0, W, H)

    // subtle hive grid
    ctx.strokeStyle = GRID()
    ctx.lineWidth = 1
    const step = 56
    ctx.beginPath()
    for (let x = step; x < W; x += step) { ctx.moveTo(x, 0); ctx.lineTo(x, H) }
    for (let y = step; y < H; y += step) { ctx.moveTo(0, y); ctx.lineTo(W, y) }
    ctx.stroke()

    // consensus point
    const pulse = 3 + Math.sin(target.t * 12) * 1.2
    ctx.beginPath()
    ctx.arc(target.x, target.y, 4 + pulse, 0, Math.PI * 2)
    ctx.fillStyle = ACCENT()
    ctx.globalAlpha = 0.9
    ctx.fill()
    ctx.globalAlpha = 0.15
    ctx.beginPath()
    ctx.arc(target.x, target.y, 18 + pulse * 2, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalAlpha = 1

    // boid update: cohesion + mild separation + consensus pull
    const pull = 0.0022 + 0.0022 * (1 + Math.sin(target.t * 0.9))
    for (const a of agents) {
      a.vx += (target.x - a.x) * pull
      a.vy += (target.y - a.y) * pull

      for (const b of agents) {
        const dx = b.x - a.x, dy = b.y - a.y
        const d2 = dx * dx + dy * dy
        if (d2 < 100 && d2 > 0.01) {       // separation
          a.vx -= dx * 0.0022
          a.vy -= dy * 0.0022
        } else if (d2 < 6400 && d2 > 100) { // alignment/cohesion
          a.vx += dx * 0.00008
          a.vy += dy * 0.00008
        }
      }

      // speed clamp
      const sp = Math.hypot(a.vx, a.vy) || 0.001
      const max = 1.6, min = 0.25
      if (sp > max) { a.vx = a.vx / sp * max; a.vy = a.vy / sp * max }
      else if (sp < min) { a.vx = a.vx / sp * min; a.vy = a.vy / sp * min }

      a.x += a.vx
      a.y += a.vy

      // wrap
      if (a.x < -8) a.x = W + 8; else if (a.x > W + 8) a.x = -8
      if (a.y < -8) a.y = H + 8; else if (a.y > H + 8) a.y = -8

      a.phase += 0.04 + sp * 0.02
      const alpha = 0.35 + 0.35 * Math.sin(a.phase)

      ctx.beginPath()
      ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2)
      ctx.fillStyle = ACCENT()
      ctx.globalAlpha = alpha
      ctx.fill()
    }
    ctx.globalAlpha = 1
  }
  frame()

  cleanup = () => {
    cancelAnimationFrame(rafId)
    window.removeEventListener('resize', resize)
    document.removeEventListener('visibilitychange', onVis)
  }
})

onBeforeUnmount(() => cleanup && cleanup())
</script>

<style scoped>
.swarm-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  opacity: 0.85;
}
</style>
