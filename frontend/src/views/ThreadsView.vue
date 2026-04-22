<script setup lang="ts">
import {
  ArrowUpRight,
  ArrowDownLeft,
  Check,
  EyeOff,
  MessageSquare,
  Clock,
} from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import KPICard from '@/components/shared/KPICard.vue'
import PaginationControls from '@/components/shared/PaginationControls.vue'
import ThreadDetailSheet from '@/components/threads/ThreadDetailSheet.vue'
import { useThreadsStore } from '@/stores/threads'
import { usePolling } from '@/composables/usePolling'
import { onWsEvent } from '@/composables/useWebSocket'
import { formatRelativeDate } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const store = useThreadsStore()

usePolling(async () => { await store.fetchAll() }, 60_000)

// Real-time: refresh threads when new emails arrive
onWsEvent('poll_complete', () => store.fetchAll())

function setFilter(f: string) {
  store.filter = f
  store.fetchThreads(1)
}

function getInitials(participants: string[] | null): string {
  if (!participants || participants.length === 0) return '?'
  return participants[0]!.charAt(0).toUpperCase()
}

function formatDuration(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffHours < 1) return 'moins d\'1h'
  if (diffHours < 24) return `${diffHours}h`
  if (diffDays < 7) return `${diffDays}j`
  return `${Math.floor(diffDays / 7)}sem`
}
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <PageHeader title="Conversations" description="Suivi des threads et des réponses en attente." />

    <!-- Stats cards -->
    <div v-if="store.stats" class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <KPICard
        title="En attente de réponse"
        :value="store.stats.awaiting_reply"
        subtitle="Vous devez répondre"
        :icon="ArrowUpRight"
        icon-class="text-amber-500"
        value-class="text-amber-600"
      />
      <KPICard
        title="Réponse attendue"
        :value="store.stats.awaiting_response"
        subtitle="En attente d'un correspondant"
        :icon="ArrowDownLeft"
        icon-class="text-blue-500"
        value-class="text-blue-600"
      />
      <KPICard
        title="Total threads"
        :value="store.stats.total_threads"
        :icon="MessageSquare"
      />
      <KPICard
        title="Plus ancien"
        :value="store.stats.oldest_awaiting ? formatDuration(store.stats.oldest_awaiting) : '—'"
        :subtitle="store.stats.oldest_awaiting ? 'en attente' : undefined"
        :icon="Clock"
      />
    </div>
    <div v-else class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card v-for="i in 4" :key="i"><CardContent class="pt-6"><Skeleton class="h-10 w-24" /></CardContent></Card>
    </div>

    <!-- Tabs -->
    <Tabs :model-value="store.filter">
      <TabsList>
        <TabsTrigger value="all" @click="setFilter('all')">Tous en attente</TabsTrigger>
        <TabsTrigger value="awaiting_reply" @click="setFilter('awaiting_reply')">
          À répondre
          <Badge v-if="store.stats?.awaiting_reply" variant="secondary" class="ml-1.5">
            {{ store.stats.awaiting_reply }}
          </Badge>
        </TabsTrigger>
        <TabsTrigger value="awaiting_response" @click="setFilter('awaiting_response')">
          Réponse attendue
          <Badge v-if="store.stats?.awaiting_response" variant="secondary" class="ml-1.5">
            {{ store.stats.awaiting_response }}
          </Badge>
        </TabsTrigger>
      </TabsList>
    </Tabs>

    <!-- Thread list -->
    <Card>
      <CardContent class="p-0">
        <!-- Loading -->
        <div v-if="store.loading" class="space-y-0">
          <div v-for="i in 5" :key="i" class="flex items-center gap-4 px-6 py-4">
            <Skeleton class="h-9 w-9 rounded-full" />
            <div class="flex-1 space-y-2">
              <Skeleton class="h-4 w-48" />
              <Skeleton class="h-3 w-32" />
            </div>
            <div class="flex gap-2">
              <Skeleton class="h-8 w-8 rounded-md" />
              <Skeleton class="h-8 w-8 rounded-md" />
            </div>
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="store.threads.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
          <Check class="mb-3 h-10 w-10 text-emerald-500" />
          <p class="text-sm font-medium">Aucune conversation en attente</p>
          <p class="mt-1 text-xs text-muted-foreground">
            Toutes les conversations sont à jour.
          </p>
        </div>

        <!-- Items -->
        <template v-else>
          <div
            v-for="(thread, index) in store.threads"
            :key="thread.id"
          >
            <div
              class="flex items-center gap-4 px-6 py-4 cursor-pointer transition-colors hover:bg-muted/50"
              @click="store.fetchThreadDetail(thread.id)"
            >
              <Avatar class="h-9 w-9 shrink-0">
                <AvatarFallback class="text-xs">
                  {{ getInitials(thread.participants) }}
                </AvatarFallback>
              </Avatar>

              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <p class="truncate text-sm font-medium">
                    {{ thread.subject_normalized || '(sans sujet)' }}
                  </p>
                  <Badge variant="outline" class="shrink-0 text-xs">
                    {{ thread.email_count }} email{{ thread.email_count > 1 ? 's' : '' }}
                  </Badge>
                </div>
                <div class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <span v-if="thread.participants" class="truncate">
                    {{ thread.participants.slice(0, 3).join(', ') }}
                    <span v-if="thread.participants.length > 3">+{{ thread.participants.length - 3 }}</span>
                  </span>
                  <span class="shrink-0">&middot;</span>
                  <span v-if="thread.last_email_at" class="shrink-0">
                    {{ formatRelativeDate(thread.last_email_at) }}
                  </span>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <Badge
                  v-if="thread.awaiting_reply"
                  variant="secondary"
                  class="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
                >
                  <ArrowUpRight class="mr-1 h-3 w-3" />
                  À répondre
                </Badge>
                <Badge
                  v-if="thread.awaiting_response"
                  variant="secondary"
                  class="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                >
                  <ArrowDownLeft class="mr-1 h-3 w-3" />
                  En attente
                </Badge>
              </div>

              <div class="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  class="text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20"
                  title="Marquer comme résolu"
                  @click.stop="store.resolveThread(thread.id)"
                >
                  <Check class="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  class="text-muted-foreground hover:bg-muted"
                  title="Ignorer"
                  @click.stop="store.ignoreThread(thread.id)"
                >
                  <EyeOff class="h-4 w-4" />
                </Button>
              </div>
            </div>
            <Separator v-if="index < store.threads.length - 1" />
          </div>
        </template>

        <!-- Pagination -->
        <PaginationControls
          :page="store.page"
          :per-page="store.perPage"
          :total="store.total"
          item-label="threads"
          @update:page="store.fetchThreads"
        />
      </CardContent>
    </Card>

    <!-- Thread detail Sheet -->
    <ThreadDetailSheet />
  </div>
</template>
