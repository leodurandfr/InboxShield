import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import type { Rule } from '@/lib/types'

export const useRulesStore = defineStore('rules', () => {
  const rules = ref<Rule[]>([])
  const loading = ref(false)

  async function fetchRules() {
    loading.value = true
    try {
      rules.value = await api.get<Rule[]>('/rules')
    } catch (e) {
      console.error('Failed to fetch rules:', e)
    } finally {
      loading.value = false
    }
  }

  async function createRule(data: Partial<Rule>) {
    const rule = await api.post<Rule>('/rules', data)
    rules.value.unshift(rule)
    return rule
  }

  async function updateRule(id: string, data: Partial<Rule>) {
    const rule = await api.put<Rule>(`/rules/${id}`, data)
    const idx = rules.value.findIndex((r) => r.id === id)
    if (idx >= 0) rules.value[idx] = rule
    return rule
  }

  async function deleteRule(id: string) {
    await api.delete(`/rules/${id}`)
    rules.value = rules.value.filter((r) => r.id !== id)
  }

  async function toggleRule(id: string, active: boolean) {
    // Optimistic update: immediately reflect the change in the UI
    const idx = rules.value.findIndex((r) => r.id === id)
    const previous = idx >= 0 ? rules.value[idx] : null
    if (previous) rules.value[idx] = { ...previous, is_active: active }
    try {
      const rule = await api.put<Rule>(`/rules/${id}`, { is_active: active })
      if (idx >= 0) rules.value[idx] = rule
      return rule
    } catch (e) {
      // Revert on failure
      if (previous) rules.value[idx] = previous
      throw e
    }
  }

  return { rules, loading, fetchRules, createRule, updateRule, deleteRule, toggleRule }
})
