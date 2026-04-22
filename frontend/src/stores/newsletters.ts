import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { api } from '@/lib/api'
import type { Newsletter, NewsletterStats, PaginatedResponse } from '@/lib/types'

interface BulkUnsubscribeResult {
  success: number
  failed: number
}

export const useNewslettersStore = defineStore('newsletters', () => {
  const newsletters = ref<Newsletter[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(20)
  const loading = ref(false)

  const stats = ref<NewsletterStats | null>(null)
  const statsLoading = ref(false)

  const filters = reactive<{ status?: string }>({ status: undefined })

  async function fetchNewsletters(p = 1) {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<Newsletter>>('/newsletters', {
        page: p,
        per_page: perPage.value,
        status: filters.status,
      })
      newsletters.value = res.items
      total.value = res.total
      page.value = res.page
      perPage.value = res.per_page
    } catch (e) {
      console.error('Failed to fetch newsletters:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    statsLoading.value = true
    try {
      stats.value = await api.get<NewsletterStats>('/newsletters/stats')
    } catch (e) {
      console.error('Failed to fetch newsletter stats:', e)
    } finally {
      statsLoading.value = false
    }
  }

  async function unsubscribe(id: string) {
    await api.post(`/newsletters/${id}/unsubscribe`)
    await fetchNewsletters(page.value)
  }

  async function bulkUnsubscribe(ids: string[]): Promise<BulkUnsubscribeResult> {
    const res = await api.post<BulkUnsubscribeResult>('/newsletters/bulk-unsubscribe', {
      newsletter_ids: ids,
    })
    await fetchNewsletters(page.value)
    return res
  }

  return {
    newsletters,
    total,
    page,
    perPage,
    loading,
    stats,
    statsLoading,
    filters,
    fetchNewsletters,
    fetchStats,
    unsubscribe,
    bulkUnsubscribe,
  }
})
