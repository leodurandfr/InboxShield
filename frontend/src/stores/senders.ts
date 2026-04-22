import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { api } from '@/lib/api'
import type { PaginatedResponse, Sender, SenderDetail } from '@/lib/types'

interface SenderFilters {
  search?: string
  is_newsletter?: boolean
  is_blocked?: boolean
}

export const useSendersStore = defineStore('senders', () => {
  const senders = ref<Sender[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(20)
  const loading = ref(false)

  const selectedSender = ref<SenderDetail | null>(null)
  const detailLoading = ref(false)

  const filters = reactive<SenderFilters>({})

  async function fetchSenders(p = 1) {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<Sender>>('/senders', {
        page: p,
        per_page: perPage.value,
        search: filters.search,
        is_newsletter: filters.is_newsletter,
        is_blocked: filters.is_blocked,
      })
      senders.value = res.items
      total.value = res.total
      page.value = res.page
      perPage.value = res.per_page
    } catch (e) {
      console.error('Failed to fetch senders:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchSenderDetail(id: string) {
    detailLoading.value = true
    try {
      selectedSender.value = await api.get<SenderDetail>(`/senders/${id}`)
    } catch (e) {
      console.error('Failed to fetch sender detail:', e)
      selectedSender.value = null
    } finally {
      detailLoading.value = false
    }
  }

  function closeDetail() {
    selectedSender.value = null
  }

  async function blockSender(id: string) {
    await api.post(`/senders/${id}/block`)
    const idx = senders.value.findIndex((s) => s.id === id)
    if (idx >= 0) senders.value[idx]!.is_blocked = true
    if (selectedSender.value?.id === id) selectedSender.value.is_blocked = true
  }

  async function unblockSender(id: string) {
    await api.post(`/senders/${id}/unblock`)
    const idx = senders.value.findIndex((s) => s.id === id)
    if (idx >= 0) senders.value[idx]!.is_blocked = false
    if (selectedSender.value?.id === id) selectedSender.value.is_blocked = false
  }

  return {
    senders,
    total,
    page,
    perPage,
    loading,
    selectedSender,
    detailLoading,
    filters,
    fetchSenders,
    fetchSenderDetail,
    closeDetail,
    blockSender,
    unblockSender,
  }
})
