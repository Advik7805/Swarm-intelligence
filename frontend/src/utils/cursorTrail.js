/**
 * Cursor trail effect.
 * Spawns small fading particles at the pointer that drift and shrink away.
 * Rendered on a fixed full-screen canvas behind interactive UI.
 * Theme-aware (reads --hm-* CSS variables), skips touch devices,
 * and fully disabled when the user prefers reduced motion.
 */

let canvas = null
let ctx = null
let particles = []
let rafId = 0
let running = false
let lastX = -1
let lastY = -1
let palette = ['#f5b942', '#e8833a', '#d9e5ff']

const MAX_PARTICLES = 90

function readPalette() {
  const styles = getComputedStyle(document.documentElement)
  const accent = styles.getPropertyValue('--hm-accent').trim()
  const accent2 = styles.getPropertyValue('--hm-accent-2').trim()
  const spark = styles.getPropertyValue('--hm-spark')?.trim()
  palette = [accent, accent2, spark, '#ffffff'].filter(Boolean)
  if (!palette.length) palette = ['#f5b942', '#ffffff']
}

function spawn(x, y) {
  if (particles.length >= MAX_PARTICLES) particles.shift()
  const angle = Math.random() * Math.PI * 2
  const speed = 0.3 + Math.random() * 1.2
  particles.push({
    x: x + (Math.random() - 0.5) * 6,
    y: y + (Math.random() - 0.5) * 6,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed - 0.4,
    life: 1,
    decay: 0.016 + Math.random() * 0.02,
    size: 1.2 + Math.random() * 2.6,
    color: palette[(Math.random() * palette.length) | 0],
  })
}

function tick() {
  if (!ctx || !canvas) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.save()
  ctx.scale(dpr, dpr)
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.x += p.vx
    p.y += p.vy
    p.vy += 0.015 // slight gravity pull
    p.life -= p.decay
    if (p.life <= 0) {
      particles.splice(i, 1)
      continue
    }
    ctx.globalAlpha = p.life * 0.85
    ctx.fillStyle = p.color
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
  rafId = requestAnimationFrame(tick)
}

function onPointerMove(e) {
  const x = e.clientX
  const y = e.clientY
  if (lastX >= 0) {
    // interpolate so fast moves leave a continuous trail
    const dx = x - lastX
    const dy = y - lastY
    const dist = Math.hypot(dx, dy)
    const steps = Math.min(Math.floor(dist / 9) + 1, 5)
    for (let i = 0; i < steps; i++) {
      spawn(lastX + (dx * i) / steps, lastY + (dy * i) / steps)
    }
  } else {
    spawn(x, y)
  }
  lastX = x
  lastY = y
}

function resize() {
  if (!canvas) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
}

export function startCursorTrail() {
  if (running) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (window.matchMedia('(hover: none)').matches) return // touch devices: skip
  running = true
  canvas = document.createElement('canvas')
  canvas.id = 'cursor-trail-canvas'
  Object.assign(canvas.style, {
    position: 'fixed',
    inset: '0',
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
    zIndex: '12000',
  })
  document.body.appendChild(canvas)
  ctx = canvas.getContext('2d')
  readPalette()
  resize()
  window.addEventListener('resize', resize)
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(rafId)
    } else {
      rafId = requestAnimationFrame(tick)
    }
  })
  // refresh palette when the theme toggles
  const observer = new MutationObserver(readPalette)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  rafId = requestAnimationFrame(tick)
}

export function stopCursorTrail() {
  running = false
  cancelAnimationFrame(rafId)
  if (canvas) {
    canvas.remove()
    canvas = null
    ctx = null
  }
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', onPointerMove)
  particles = []
  lastX = -1
  lastY = -1
}
