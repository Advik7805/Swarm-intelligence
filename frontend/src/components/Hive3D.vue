<template>
  <canvas ref="canvasRef" class="hive3d" aria-hidden="true"></canvas>
</template>

<script setup>
/**
 * Hive3D — HiveMind's signature 3D hero scene (three.js).
 *
 * A floating honeycomb lattice of amber hexagonal prisms (the "hive") with
 * a swarm of particles orbiting it (the "agents"). Whole cluster slowly
 * rotates, cells bob gently, and the camera follows the pointer with soft
 * parallax. Theme-aware, DPR-capped, pauses when hidden, honors
 * prefers-reduced-motion, and fully disposes on unmount.
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'

const canvasRef = ref(null)
let rafId = null
let cleanup = null

onMounted(() => {
  const canvas = canvasRef.value
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100)
  camera.position.set(0, 3.4, 17)

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // ---------- theme colors ----------
  let accent = new THREE.Color('#F0A500')
  const fog = new THREE.Fog(new THREE.Color('#0D1117'), 15, 34)
  scene.fog = fog
  const readTheme = () => {
    const cs = getComputedStyle(document.documentElement)
    const v = cs.getPropertyValue('--hm-accent').trim()
    if (v) accent = new THREE.Color(v)
    const bg = cs.getPropertyValue('--hm-bg').trim()
    if (bg) fog.color = new THREE.Color(bg)
  }
  readTheme()
  const themeObs = new MutationObserver(readTheme)
  themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  // ---------- hive lattice (hex cluster) ----------
  const hive = new THREE.Group()
  const cells = []
  const R = 1.02                       // cell radius
  const N_RING = 2                     // cluster rings (19 cells)
  const hexGeo = new THREE.CylinderGeometry(R * 0.94, R * 0.94, 0.55, 6)
  const posSet = new Set()
  const ax = (q, r) => ({ x: R * 1.74 * (q + r / 2), z: R * 1.5 * r })
  for (let q = -N_RING; q <= N_RING; q++) {
    for (let r = Math.max(-N_RING, -q - N_RING); r <= Math.min(N_RING, -q + N_RING); r++) {
      posSet.add(`${ax(q, r).x},${ax(q, r).z}`)
    }
  }
  for (const key of posSet) {
    const [x, z] = key.split(',').map(Number)
    const isCenter = Math.abs(x) < 0.01 && Math.abs(z) < 0.01
    const mat = new THREE.MeshBasicMaterial({
      color: accent, transparent: true, opacity: isCenter ? 0.07 : 0.028,
    })
    const mesh = new THREE.Mesh(hexGeo, mat)
    mesh.position.set(x, 0, z)

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(hexGeo),
      new THREE.LineBasicMaterial({
        color: accent, transparent: true, opacity: isCenter ? 0.85 : 0.22,
      })
    )
    mesh.add(edges)
    mesh.userData = { baseY: 0, phase: Math.random() * Math.PI * 2, isCenter }
    hive.add(mesh)
    cells.push(mesh)
  }
  hive.position.x = 2.4
  hive.rotation.y = 0.4
  scene.add(hive)

  // ---------- orbiting agent swarm ----------
  const N_AGENTS = 480
  const pGeo = new THREE.BufferGeometry()
  const positions = new Float32Array(N_AGENTS * 3)
  const seeds = new Float32Array(N_AGENTS * 3)   // radius, speed, phase
  for (let i = 0; i < N_AGENTS; i++) {
    seeds[i * 3] = 4.2 + Math.random() * 3.6          // orbital radius
    seeds[i * 3 + 1] = 0.15 + Math.random() * 0.5     // angular speed
    seeds[i * 3 + 2] = Math.random() * Math.PI * 2    // phase
  }
  pGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const pMat = new THREE.PointsMaterial({
    color: accent, size: 0.048, transparent: true, opacity: 0.5,
    sizeAttenuation: true, depthWrite: false,
  })
  const swarm = new THREE.Points(pGeo, pMat)
  swarm.rotation.x = 0.5
  scene.add(swarm)

  // ---------- energy pulses (sparks traveling between cells) ----------
  const N_PULSES = 12
  const pulseGeo = new THREE.BufferGeometry()
  pulseGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N_PULSES * 3), 3))
  const pulseMat = new THREE.PointsMaterial({
    color: new THREE.Color('#ffd97a'), size: 0.16, transparent: true, opacity: 0.95,
    sizeAttenuation: true, depthWrite: false, blending: THREE.AdditiveBlending,
  })
  const pulses = new THREE.Points(pulseGeo, pulseMat)
  scene.add(pulses)
  const pulseState = []
  const cellXZ = cells.map((c) => ({ x: c.position.x + hive.position.x, z: c.position.z }))
  const randCell = () => cellXZ[(Math.random() * cellXZ.length) | 0]
  for (let i = 0; i < N_PULSES; i++) {
    pulseState.push({ from: randCell(), to: randCell(), t: Math.random(), speed: 0.25 + Math.random() * 0.5 })
  }

  // ---------- size / resize ----------
  const resize = () => {
    const w = canvas.clientWidth || 1
    const h = canvas.clientHeight || 1
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }
  resize()
  const ro = new ResizeObserver(resize)
  ro.observe(canvas)

  // ---------- pointer parallax ----------
  const pointer = { x: 0, y: 0 }
  const onPointer = (e) => {
    const rect = canvas.getBoundingClientRect()
    pointer.x = ((e.clientX - rect.left) / rect.width - 0.5) * 2
    pointer.y = ((e.clientY - rect.top) / rect.height - 0.5) * 2
  }
  window.addEventListener('pointermove', onPointer, { passive: true })

  // ---------- animation ----------
  let visible = !document.hidden
  const onVis = () => { visible = !document.hidden }
  document.addEventListener('visibilitychange', onVis)

  let t = 0
  const drawFrame = () => {
    // cells bob
    for (const c of cells) {
      const { phase, isCenter } = c.userData
      c.position.y = Math.sin(t * 0.9 + phase) * (isCenter ? 0.34 : 0.18)
    }
    // agents orbit
    const arr = pGeo.attributes.position.array
    for (let i = 0; i < N_AGENTS; i++) {
      const rad = seeds[i * 3], spd = seeds[i * 3 + 1], ph = seeds[i * 3 + 2]
      const a = ph + t * spd
      arr[i * 3] = Math.cos(a) * rad
      arr[i * 3 + 1] = Math.sin(a * 1.7 + ph) * 0.9
      arr[i * 3 + 2] = Math.sin(a) * rad
    }
    pGeo.attributes.position.needsUpdate = true

    // pulses travel between cells, then pick a new pair
    const parr = pulseGeo.attributes.position.array
    for (let i = 0; i < N_PULSES; i++) {
      const s = pulseState[i]
      s.t += 0.016 * s.speed
      if (s.t >= 1) {
        s.t = 0
        s.from = s.to
        s.to = randCell()
      }
      const e = s.t * s.t * (3 - 2 * s.t) // smoothstep ease
      parr[i * 3] = s.from.x + (s.to.x - s.from.x) * e
      parr[i * 3 + 1] = 0.3 + Math.sin(e * Math.PI) * 0.5
      parr[i * 3 + 2] = s.from.z + (s.to.z - s.from.z) * e
    }
    pulseGeo.attributes.position.needsUpdate = true
    pulseMat.opacity = 0.55 + Math.sin(t * 2.4) * 0.35

    hive.rotation.y = 0.4 + t * 0.08
    swarm.rotation.y = -t * 0.05

    // breathing center-cell glow
    if (cells[0]?.userData.isCenter) {
      const center = cells[0]
      center.material.opacity = 0.07 + Math.sin(t * 1.8) * 0.035
      center.children[0].material.opacity = 0.85 + Math.sin(t * 1.8) * 0.12
    }

    // autonomous drift + parallax camera
    const driftX = Math.sin(t * 0.11) * 2.2
    const driftY = Math.sin(t * 0.07 + 1.2) * 0.6
    camera.position.x += (driftX + pointer.x * 1.4 - camera.position.x) * 0.04
    camera.position.y += (2.6 + driftY - pointer.y * 1.0 - camera.position.y) * 0.04
    camera.lookAt(0, 0, 0)

    renderer.render(scene, camera)
  }

  if (reducedMotion) {
    drawFrame()                                    // single static frame
  } else {
    const loop = () => {
      rafId = requestAnimationFrame(loop)
      if (!visible) return
      t += 0.016
      drawFrame()
    }
    loop()
  }

  cleanup = () => {
    cancelAnimationFrame(rafId)
    ro.disconnect()
    window.removeEventListener('pointermove', onPointer)
    document.removeEventListener('visibilitychange', onVis)
    themeObs.disconnect()
    hexGeo.dispose()
    pGeo.dispose()
    pMat.dispose()
    for (const c of cells) {
      c.material.dispose()
      c.children[0]?.geometry.dispose()
      c.children[0]?.material.dispose()
    }
    renderer.dispose()
  }
})

onBeforeUnmount(() => cleanup && cleanup())
</script>

<style scoped>
.hive3d {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
