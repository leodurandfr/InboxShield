import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type { Account, LLMModel, OllamaStatus, Settings } from '@/lib/types'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings | null>(null)
  const accounts = ref<Account[]>([])
  const llmModels = ref<LLMModel[]>([])
  const ollamaStatus = ref<OllamaStatus | null>(null)
  const loading = ref(false)

  async function fetchSettings() {
    try {
      settings.value = await api.get<Settings>('/settings')
    } catch (e) {
      console.error('Failed to fetch settings:', e)
    }
  }

  async function updateSettings(data: Partial<Settings>) {
    settings.value = await api.put<Settings>('/settings', data)
  }

  async function fetchAccounts() {
    try {
      accounts.value = await api.get<Account[]>('/accounts')
    } catch (e) {
      console.error('Failed to fetch accounts:', e)
    }
  }

  async function fetchLLMModels(provider?: string) {
    try {
      const query = provider ? `?provider=${encodeURIComponent(provider)}` : ''
      const res = await api.get<{ provider: string; models: LLMModel[] }>(`/settings/llm/models${query}`)
      llmModels.value = res.models
    } catch (e) {
      console.error('Failed to fetch LLM models:', e)
      llmModels.value = []
    }
  }

  async function testLLM() {
    return api.post<{ success: boolean; provider: string; model: string; latency_ms: number | null; error: string | null }>('/settings/llm/test')
  }

  async function deleteLLMModel(name: string) {
    await api.delete(`/settings/llm/models/${encodeURIComponent(name)}`)
    llmModels.value = llmModels.value.filter((m) => m.name !== name)
  }

  async function fetchOllamaStatus() {
    try {
      ollamaStatus.value = await api.get<OllamaStatus>('/system/ollama/status')
    } catch (e) {
      console.error('Failed to fetch Ollama status:', e)
      ollamaStatus.value = null
    }
  }

  async function unloadOllamaModel(name: string) {
    await api.post(`/system/ollama/unload/${encodeURIComponent(name)}`)
    await fetchOllamaStatus()
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchSettings(), fetchAccounts()])
    } finally {
      loading.value = false
    }
  }

  return {
    settings, accounts, llmModels, ollamaStatus, loading,
    fetchSettings, updateSettings, fetchAccounts, fetchLLMModels, testLLM, deleteLLMModel,
    fetchOllamaStatus, unloadOllamaModel, fetchAll,
  }
})
