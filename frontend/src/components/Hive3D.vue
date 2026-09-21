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
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100)
  camera.position.set(0, 2.6, 11)

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // ---------- theme colors ----------
  let accent = new THREE.Color('#F0A500')
  const readTheme = () => {
    const v = getComputedStyle(document.documentElement).getPropertyValue('--hm-accent').trim()
    if (v) accent = new THREE.Color(v)
  }
  readTheme()
  const themeObs = new MutationObserver(readTheme)
  themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  // ---------- hive lattice (hex cluster) ----------
  const hive = new THREE.Group()
  const cells = []
  const R = 1.02                       // cell radius
  const N_RING = 3                     // cluster rings (19 cells)
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
      color: accent, transparent: true, opacity: isCenter ? 0.10 : 0.045,
    })
    const mesh = new THREE.Mesh(hexGeo, mat)
    mesh.position.set(x, 0, z)

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(hexGeo),
      new THREE.LineBasicMaterial({
        color: accent, transparent: true, opacity: isCenter ? 0.95 : 0.35,
      })
    )
    mesh.add(edges)
    mesh.userData = { baseY: 0, phase: Math.random() * Math.PI * 2, isCenter }
    hive.add(mesh)
    cells.push(mesh)
  }
  hive.rotation.y = 0.4
  scene.add(hive)

  // ---------- orbiting agent swarm ----------
  const N_AGENTS = 700
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
    color: accent, size: 0.055, transparent: true, opacity: 0.75,
    sizeAttenuation: true, depthWrite: false,
  })
  const swarm = new THREE.Points(pGeo, pMat)
  swarm.rotation.x = 0.5
  scene.add(swarm)

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

    hive.rotation.y = 0.4 + t * 0.12
    swarm.rotation.y = -t * 0.05

    // parallax camera
    camera.position.x += (pointer.x * 1.4 - camera.position.x) * 0.04
    camera.position.y += (2.6 - pointer.y * 1.0 - camera.position.y) * 0.04
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
