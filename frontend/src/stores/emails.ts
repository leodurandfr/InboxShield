import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { api } from '@/lib/api'
import type { Email, EmailDetail, PaginatedResponse } from '@/lib/types'

export const useEmailsStore = defineStore('emails', () => {
  const emails = ref<Email[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(20)
  const pages = ref(0)
  const loading = ref(false)

  // Detail drawer
  const selectedEmail = ref<EmailDetail | null>(null)
  const detailLoading = ref(false)

  const filters = reactive({
    account_id: undefined as string | undefined,
    category: undefined as string | undefined,
    processing_status: undefined as string | undefined,
    classification_status: undefined as string | undefined,
    is_read: undefined as boolean | undefined,
    from_address: undefined as string | undefined,
    subject: undefined as string | undefined,
    sort: '-date' as string,
  })

  async function fetchEmails(p = 1) {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<Email>>('/emails', {
        ...filters,
        page: p,
        per_page: perPage.value,
      })
      emails.value = res.items
      total.value = res.total
      page.value = res.page
      pages.value = res.pages
    } catch (e) {
      console.error('Failed to fetch emails:', e)
    } finally {
      loading.value = false
    }
  }

  async function moveEmail(emailId: string, folder: string) {
    await api.post(`/emails/${emailId}/move`, { folder })
    await fetchEmails(page.value)
  }

  async function reclassifyEmail(emailId: string) {
    await api.post(`/emails/${emailId}/reclassify`)
    await fetchEmails(page.value)
  }

  function resetFilters() {
    filters.account_id = undefined
    filters.category = undefined
    filters.processing_status = undefined
    filters.classification_status = undefined
    filters.is_read = undefined
    filters.from_address = undefined
    filters.subject = undefined
    filters.sort = '-date'
  }

  return {
    emails, total, page, perPage, pages, loading, filters,
    fetchEmails, moveEmail, reclassifyEmail, resetFilters,
  }
})
