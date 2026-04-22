import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type { PaginatedResponse, ReviewItem, ReviewStats } from '@/lib/types'
import { useAppStore } from './app'

export const useReviewStore = defineStore('review', () => {
  const items = ref<ReviewItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const stats = ref<ReviewStats | null>(null)
  const loading = ref(false)

  async function fetchQueue(p = 1) {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<ReviewItem>>('/review', {
        page: p,
        per_page: 20,
        sort: 'confidence',
      })
      items.value = res.items
      total.value = res.total
      page.value = res.page

      // Update badge count in app store
      const appStore = useAppStore()
      appStore.setReviewCount(res.total)
    } catch (e) {
      console.error('Failed to fetch review queue:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      stats.value = await api.get<ReviewStats>('/review/stats')
      const appStore = useAppStore()
      appStore.setReviewCount(stats.value.total_pending)
    } catch (e) {
      console.error('Failed to fetch review stats:', e)
    }
  }

  async function approve(emailId: string) {
    await api.post(`/review/${emailId}/approve`)
    items.value = items.value.filter((i) => i.email.id !== emailId)
    total.value = Math.max(0, total.value - 1)
    const appStore = useAppStore()
    appStore.setReviewCount(total.value)
  }

  async function correct(emailId: string, correctedCategory: string, note?: string) {
    await api.post(`/review/${emailId}/correct`, {
      corrected_category: correctedCategory,
      note,
    })
    items.value = items.value.filter((i) => i.email.id !== emailId)
    total.value = Math.max(0, total.value - 1)
    const appStore = useAppStore()
    appStore.setReviewCount(total.value)
  }

  async function bulkApprove(emailIds: string[]) {
    await api.post('/review/bulk-approve', { email_ids: emailIds })
    items.value = items.value.filter((i) => !emailIds.includes(i.email.id))
    total.value = Math.max(0, total.value - emailIds.length)
    const appStore = useAppStore()
    appStore.setReviewCount(total.value)
  }

  return { items, total, page, stats, loading, fetchQueue, fetchStats, approve, correct, bulkApprove }
})
