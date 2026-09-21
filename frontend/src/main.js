import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './assets/theme.css'

const app = createApp(App)

/**
 * v-reveal — scroll-triggered entrance animation.
 * Adds the `revealed` class when the element enters the viewport.
 * Optional binding value = stagger delay in ms: v-reveal="120"
 */
const revealObserver = 'IntersectionObserver' in window
  ? new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add('revealed')
          revealObserver.unobserve(e.target)
        }
      }
    }, { threshold: 0.12 })
  : null

app.directive('reveal', {
  mounted(el, binding) {
    el.classList.add('reveal')
    if (binding.value) el.style.transitionDelay = `${binding.value}ms`
    if (revealObserver) {
      revealObserver.observe(el)
    } else {
      el.classList.add('revealed')     // graceful fallback
    }
  },
  unmounted(el) {
    revealObserver?.unobserve(el)
  },
})

app.use(router)
app.use(i18n)

app.mount('#app')
