import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type { Email, PaginatedResponse, SystemStats } from '@/lib/types'

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref<SystemStats | null>(null)
  const recentEmails = ref<Email[]>([])
  const pendingEmails = ref<Email[]>([])
  const pendingTotal = ref(0)
  const classificationProgress = ref<{ processed: number; total: number } | null>(null)
  const loading = ref(false)
  const polling = ref(false)
  const error = ref<string | null>(null)

  // Classification state (driven by WS events + API status)
  const classifying = ref(false)
  const pendingResumeCount = ref(0)

  async function fetchStats() {
    try {
      stats.value = await api.get<SystemStats>('/system/stats')
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
  }

  async function fetchRecentEmails(limit = 20) {
    try {
      const res = await api.get<PaginatedResponse<Email>>('/emails', {
        sort: '-classified_at',
        processing_status: 'classified',
        per_page: limit,
      })
      recentEmails.value = res.items
    } catch (e) {
      console.error('Failed to fetch recent emails:', e)
    }
  }

  async function fetchPendingEmails() {
    try {
      const res = await api.get<PaginatedResponse<Email>>('/emails', {
        processing_status: 'pending',
        sort: '-date',
        per_page: 10,
      })
      pendingTotal.value = res.total
      // Strip stale classifications so the table shows "pending" badges
      pendingEmails.value = res.items.map(e => ({ ...e, classification: null }))
    } catch (e) {
      console.error('Failed to fetch pending emails:', e)
    }
  }

  /** Mark an email as 'classifying' — move it to top of list, or insert it if not visible */
  function markEmailClassifying(emailId: string, meta?: { from_name?: string; from_address?: string; subject?: string; date?: string }) {
    const idx = pendingEmails.value.findIndex(e => e.id === emailId)
    if (idx !== -1) {
      const existing = pendingEmails.value[idx]!
      existing.processing_status = 'classifying'
      if (idx > 0) {
        const [email] = pendingEmails.value.splice(idx, 1)
        if (email) pendingEmails.value.unshift(email)
      }
    } else if (meta) {
      // Not in visible list — add placeholder at top so user sees it
      pendingEmails.value.unshift({
        id: emailId,
        account_id: '',
        from_address: meta.from_address ?? '',
        from_name: meta.from_name ?? null,
        subject: meta.subject ?? null,
        date: meta.date ?? '',
        folder: null,
        is_read: false,
        is_flagged: false,
        has_attachments: false,
        processing_status: 'classifying',
        classification: null,
      })
      // Keep list to a reasonable size (max 15 visible)
      if (pendingEmails.value.length > 15) {
        pendingEmails.value.pop()
      }
    }
  }

  /** Remove a classified email from pending list (local, no API call) */
  function markEmailClassified(emailId: string) {
    const idx = pendingEmails.value.findIndex(e => e.id === emailId)
    if (idx !== -1) {
      pendingEmails.value.splice(idx, 1)
    }
    if (pendingTotal.value > 0) {
      pendingTotal.value--
    }
  }

  /** Update classification progress from WS event */
  function updateClassificationProgress(processed: number, total: number) {
    classifying.value = true
    pendingResumeCount.value = 0
    classificationProgress.value = { processed, total }
    if (processed >= total) {
      // Classification complete — clear progress after a short delay
      setTimeout(() => {
        classificationProgress.value = null
      }, 2000)
    }
  }

  /** Clear classification progress */
  function clearClassificationProgress() {
    classificationProgress.value = null
  }

  /** Called when classification finishes normally */
  function setClassificationComplete() {
    classifying.value = false
    pendingResumeCount.value = 0
    clearClassificationProgress()
  }

  /** Called when classification is cancelled */
  function setClassificationCancelled(remaining: number) {
    classifying.value = false
    pendingResumeCount.value = remaining
    clearClassificationProgress()
  }

  /** Fetch classification status from API (for page reload recovery) */
  async function fetchClassificationStatus() {
    try {
      const res = await api.get<{ active: boolean; pending_count: number }>('/system/classification-status')
      classifying.value = res.active
      if (!res.active && res.pending_count > 0) {
        pendingResumeCount.value = res.pending_count
      } else {
        pendingResumeCount.value = 0
      }
    } catch (e) {
      console.error('Failed to fetch classification status:', e)
    }
  }

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      await Promise.all([fetchStats(), fetchRecentEmails(), fetchPendingEmails()])
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Erreur de chargement'
    } finally {
      loading.value = false
    }
  }

  async function pollAll() {
    polling.value = true
    error.value = null
    try {
      const res = await api.post<{
        total_new_emails: number
        llm_available?: boolean
        llm_warning?: string
      }>('/system/poll-all')
      // Mark classifying immediately — WS events will confirm later
      if (res && (res.total_new_emails ?? 0) > 0) {
        classifying.value = true
        pendingResumeCount.value = 0
      }
      // Refresh dashboard data after poll
      await fetchAll()
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lors de l\'analyse'
      console.error('Failed to poll:', e)
    } finally {
      polling.value = false
    }
  }

  const reanalyzing = ref(false)

  async function reanalyzeAll() {
    reanalyzing.value = true
    error.value = null
    try {
      const res = await api.post<{
        total_fetched: number
        llm_available?: boolean
        llm_warning?: string
      }>('/system/reanalyze-all')
      await fetchAll()
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lors de la réanalyse'
      console.error('Failed to reanalyze:', e)
    } finally {
      reanalyzing.value = false
    }
  }

  const cancelling = ref(false)

  async function cancelAnalysis() {
    cancelling.value = true
    try {
      const res = await api.post<{ cancelled: number; remaining: number }>('/system/cancel-analysis')
      await fetchAll()
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lors de l\'annulation'
      console.error('Failed to cancel analysis:', e)
    } finally {
      cancelling.value = false
      polling.value = false
      reanalyzing.value = false
    }
  }

  const resuming = ref(false)

  async function resumeClassification() {
    resuming.value = true
    error.value = null
    try {
      const res = await api.post<{ total_queued: number }>('/system/resume-classification')
      pendingResumeCount.value = 0
      await fetchAll()
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lors de la reprise'
      console.error('Failed to resume classification:', e)
    } finally {
      resuming.value = false
    }
  }

  async function createTestEmail(payload: {
    from_address: string
    from_name?: string
    subject?: string
    body?: string
  }) {
    try {
      const res = await api.post<{
        status: string
        email_id: string
        classification: {
          category: string
          confidence: number
          status: string
          classified_by: string
        } | null
      }>('/system/test-email', payload)
      await fetchAll()
      return res
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur lors de la création'
      console.error('Failed to create test email:', e)
    }
  }

  return {
    stats, recentEmails, pendingEmails, pendingTotal, classificationProgress,
    loading, polling, reanalyzing, cancelling, resuming, error,
    classifying, pendingResumeCount,
    fetchStats, fetchRecentEmails, fetchPendingEmails, fetchAll,
    pollAll, reanalyzeAll, cancelAnalysis, resumeClassification, createTestEmail,
    fetchClassificationStatus,
    markEmailClassifying, markEmailClassified,
    updateClassificationProgress, clearClassificationProgress,
    setClassificationComplete, setClassificationCancelled,
  }
})
