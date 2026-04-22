import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import type {
  AnalyticsOverview,
  CategoryBreakdown,
  ConfusionEntry,
  DailyVolume,
  HourlyHeatmapEntry,
  PerformanceMetrics,
  TopSender,
} from '@/lib/types'

export const useAnalyticsStore = defineStore('analytics', () => {
  const overview = ref<AnalyticsOverview | null>(null)
  const categories = ref<CategoryBreakdown[]>([])
  const dailyVolume = ref<DailyVolume[]>([])
  const topSenders = ref<TopSender[]>([])
  const performance = ref<PerformanceMetrics | null>(null)
  const confusionMatrix = ref<ConfusionEntry[]>([])
  const heatmap = ref<HourlyHeatmapEntry[]>([])
  const loading = ref(false)
  const exporting = ref(false)
  const period = ref('30d')

  const totalCorrections = computed(() =>
    confusionMatrix.value.reduce((acc, e) => acc + e.count, 0),
  )

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

  async function fetchPerformance() {
    try {
      performance.value = await api.get<PerformanceMetrics>('/analytics/performance', {
        period: period.value,
      })
    } catch (e) {
      console.error('Failed to fetch performance metrics:', e)
    }
  }

  async function fetchConfusionMatrix() {
    try {
      const res = await api.get<{ entries: ConfusionEntry[] }>('/analytics/confusion-matrix', {
        period: period.value,
      })
      confusionMatrix.value = res.entries ?? []
    } catch (e) {
      console.error('Failed to fetch confusion matrix:', e)
    }
  }

  async function fetchHeatmap() {
    try {
      const res = await api.get<{ entries: HourlyHeatmapEntry[] }>('/analytics/hourly-heatmap', {
        period: period.value,
      })
      heatmap.value = res.entries ?? []
    } catch (e) {
      console.error('Failed to fetch heatmap:', e)
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
        fetchPerformance(),
        fetchConfusionMatrix(),
        fetchHeatmap(),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview, categories, dailyVolume, topSenders,
    performance, confusionMatrix, heatmap, totalCorrections,
    loading, exporting, period,
    fetchOverview, fetchCategories, fetchDailyVolume, fetchTopSenders,
    fetchPerformance, fetchConfusionMatrix, fetchHeatmap, exportCsv,
    fetchAll,
  }
})
