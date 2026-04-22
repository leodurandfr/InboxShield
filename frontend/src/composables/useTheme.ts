import { computed, ref, watchEffect } from 'vue'

const STORAGE_KEY = 'inboxshield_theme'
type Theme = 'light' | 'dark'

function detectInitial(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const theme = ref<Theme>(detectInitial())

watchEffect(() => {
  const root = document.documentElement
  if (theme.value === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
  localStorage.setItem(STORAGE_KEY, theme.value)
})

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  function setTheme(next: Theme) {
    theme.value = next
  }

  return { theme, isDark, toggleTheme, setTheme }
}
