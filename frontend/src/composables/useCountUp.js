import { ref, watch, onBeforeUnmount } from 'vue'

/**
 * Tweened number counter — animates toward the getter's value with an
 * ease-out curve whenever it changes. Honors prefers-reduced-motion.
 *
 * Usage: const shown = useCountUp(() => props.value)
 */
export function useCountUp(getter, duration = 900) {
  const shown = ref(typeof getter === 'function' ? (getter() || 0) : 0)
  let raf = null

  const stop = watch(getter, (to) => {
    to = Number(to) || 0
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) { shown.value = to; return }
    const from = shown.value
    const start = performance.now()
    if (raf) cancelAnimationFrame(raf)
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      shown.value = Math.round(from + (to - from) * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
  }, { immediate: true })

  onBeforeUnmount(() => raf && cancelAnimationFrame(raf))
  return { shown, stop }
}
