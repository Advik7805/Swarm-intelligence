import { ref, watchEffect } from 'vue'

const THEME_KEY = 'hivemind-theme'
const theme = ref(localStorage.getItem(THEME_KEY) || 'dark')

function apply(t) {
  document.documentElement.setAttribute('data-theme', t)
}

watchEffect(() => {
  apply(theme.value)
  localStorage.setItem(THEME_KEY, theme.value)
})

export function useTheme() {
  const toggle = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }
  return { theme, toggle }
}
