<template>
  <button
    class="theme-toggle"
    :title="theme === 'dark' ? $t('theme.toLight') : $t('theme.toDark')"
    @click="toggle"
  >
    <span class="icon">{{ theme === 'dark' ? '☀' : '☾' }}</span>
  </button>
</template>

<script setup>
import { useTheme } from '../composables/useTheme'
const { theme, toggle } = useTheme()
</script>

<style scoped>
.theme-toggle {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--hm-border);
  background: var(--hm-surface);
  color: var(--hm-accent);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.theme-toggle:hover {
  border-color: var(--hm-accent-dim);
  box-shadow: 0 0 12px var(--hm-glow);
  transform: translateY(-1px);
}
.icon { line-height: 1; }
</style>
