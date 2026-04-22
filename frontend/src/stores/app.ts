import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
  const reviewCount = ref(0)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('sidebar_collapsed', String(sidebarCollapsed.value))
  }

  function setSidebarCollapsed(value: boolean) {
    sidebarCollapsed.value = value
    localStorage.setItem('sidebar_collapsed', String(value))
  }

  function setReviewCount(count: number) {
    reviewCount.value = count
  }

  return { sidebarCollapsed, reviewCount, toggleSidebar, setSidebarCollapsed, setReviewCount }
})
