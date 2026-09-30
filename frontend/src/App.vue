<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { startCursorTrail } from './utils/cursorTrail'

onMounted(() => {
  // global cursor trail (respects reduced-motion + touch devices)
  startCursorTrail()
})
</script>

<style>
/* Global style reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: var(--font-mono), 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--hm-text);
  background-color: var(--hm-bg);
  min-height: 100vh;
}

/* Global button style */
button {
  font-family: inherit;
}
</style>
