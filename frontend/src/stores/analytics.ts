import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type {
  AnalyticsOverview,
  CategoryBreakdown,
  DailyVolume,
  TopSender,
} from '@/lib/types'

export const useAnalyticsStore = defineStore('analytics', () => {
  const overview = ref<AnalyticsOverview | null>(null)
  const categories = ref<CategoryBreakdown[]>([])
  const dailyVolume = ref<DailyVolume[]>([])
  const topSenders = ref<TopSender[]>([])
  const loading = ref(false)
  const exporting = ref(false)
  const period = ref('30d')

  async function fetchOverview() {
    loading.value = true
    try {
      overview.value = await api.get<AnalyticsOverview>('/analytics/overview', {
        period: period.value,
      })
    } catch (e) {
      console.error('Failed to fetch analytics overview:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchCategories() {
    try {
      const res = await api.get<{ period: string; total: number; categories: CategoryBreakdown[] }>('/analytics/categories', {
        period: period.value,
      })
      categories.value = res.categories
    } catch (e) {
      console.error('Failed to fetch categories:', e)
    }
  }

  async function fetchDailyVolume() {
    try {
      const res = await api.get<{ period: string; days: DailyVolume[] }>('/analytics/volume', {
        period: period.value,
      })
      dailyVolume.value = res.days
    } catch (e) {
      console.error('Failed to fetch daily volume:', e)
    }
  }

  async function fetchTopSenders(limit = 10) {
    try {
      const res = await api.get<{ limit: number; senders: TopSender[] }>('/analytics/top-senders', {
        limit,
      })
      topSenders.value = res.senders
    } catch (e) {
      console.error('Failed to fetch top senders:', e)
    }
  }

  async function exportCsv() {
    exporting.value = true
    try {
      const url = `/api/v1/analytics/export?period=${period.value}`
      window.open(url, '_blank')
    } catch (e) {
      console.error('Failed to export CSV:', e)
    } finally {
      exporting.value = false
    }
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([
        fetchOverview(),
        fetchCategories(),
        fetchDailyVolume(),
        fetchTopSenders(),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview, categories, dailyVolume, topSenders,
    loading, exporting, period,
    fetchOverview, fetchCategories, fetchDailyVolume, fetchTopSenders, exportCsv,
    fetchAll,
  }
})
