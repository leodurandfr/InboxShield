import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type { PaginatedResponse, Thread, ThreadDetail, ThreadStats } from '@/lib/types'

export const useThreadsStore = defineStore('threads', () => {
  const threads = ref<Thread[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(20)
  const loading = ref(false)

  const stats = ref<ThreadStats | null>(null)
  const selectedThread = ref<ThreadDetail | null>(null)
  const detailLoading = ref(false)
  const filter = ref<string>('all')

  async function fetchThreads(p = 1) {
    loading.value = true
    try {
      const status = filter.value === 'all' ? undefined : filter.value
      const res = await api.get<PaginatedResponse<Thread>>('/threads', {
        page: p,
        per_page: perPage.value,
        status,
      })
      threads.value = res.items
      total.value = res.total
      page.value = res.page
      perPage.value = res.per_page
    } catch (e) {
      console.error('Failed to fetch threads:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      stats.value = await api.get<ThreadStats>('/threads/stats')
    } catch (e) {
      console.error('Failed to fetch thread stats:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([fetchThreads(page.value), fetchStats()])
  }

  async function fetchThreadDetail(id: string) {
    detailLoading.value = true
    try {
      selectedThread.value = await api.get<ThreadDetail>(`/threads/${id}`)
    } catch (e) {
      console.error('Failed to fetch thread detail:', e)
      selectedThread.value = null
    } finally {
      detailLoading.value = false
    }
  }

  function closeDetail() {
    selectedThread.value = null
  }

  async function resolveThread(id: string) {
    await api.post(`/threads/${id}/resolve`)
    threads.value = threads.value.filter((t) => t.id !== id)
    total.value = Math.max(0, total.value - 1)
    if (selectedThread.value?.id === id) selectedThread.value = null
    await fetchStats()
  }

  async function ignoreThread(id: string) {
    await api.post(`/threads/${id}/ignore`)
    threads.value = threads.value.filter((t) => t.id !== id)
    total.value = Math.max(0, total.value - 1)
    if (selectedThread.value?.id === id) selectedThread.value = null
    await fetchStats()
  }

  return {
    threads,
    total,
    page,
    perPage,
    loading,
    stats,
    selectedThread,
    detailLoading,
    filter,
    fetchThreads,
    fetchStats,
    fetchAll,
    fetchThreadDetail,
    closeDetail,
    resolveThread,
    ignoreThread,
  }
})
