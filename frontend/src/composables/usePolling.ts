import { ref, onMounted, onUnmounted } from 'vue'

export function usePolling(callback: () => Promise<void>, intervalMs = 60_000) {
  const isActive = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  function start() {
    if (timer) return
    isActive.value = true
    timer = setInterval(callback, intervalMs)
  }

  function stop() {
    if (!timer) return
    clearInterval(timer)
    timer = null
    isActive.value = false
  }

  async function refresh() {
    await callback()
  }

  function onVisibilityChange() {
    if (document.hidden) {
      stop()
    } else {
      callback()
      start()
    }
  }

  onMounted(() => {
    start()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return { isActive, start, stop, refresh }
}
