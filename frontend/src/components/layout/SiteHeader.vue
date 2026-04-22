<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'

const route = useRoute()

const titleMap: Record<string, string> = {
  dashboard: 'Dashboard',
  emails: 'Emails',
  review: 'Review',
  rules: 'Règles',
  newsletters: 'Newsletters',
  senders: 'Expéditeurs',
  analytics: 'Analytics',
  threads: 'Conversations',
  settings: 'Paramètres',
}

const title = computed(() => {
  const name = typeof route.name === 'string' ? route.name : ''
  return titleMap[name] ?? 'InboxShield'
})
</script>

<template>
  <header
    class="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6 sticky top-0 z-10 bg-background/80 backdrop-blur"
  >
    <SidebarTrigger class="-ml-1" />
    <Separator orientation="vertical" class="mx-2 h-4" />
    <h1 class="text-sm font-medium">{{ title }}</h1>
  </header>
</template>
