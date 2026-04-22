<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Search,
} from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmailTable from '@/components/emails/EmailTable.vue'
import EmailDetailSheet from '@/components/emails/EmailDetailSheet.vue'
import { useEmailsStore } from '@/stores/emails'
import { usePolling } from '@/composables/usePolling'
import { onWsEvent } from '@/composables/useWebSocket'
import { CATEGORY_CONFIG } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()
const store = useEmailsStore()
const detailOpen = ref(false)

usePolling(() => store.fetchEmails(), 60_000)

// Real-time updates via WebSocket
onWsEvent('poll_complete', () => store.fetchEmails(store.page))
onWsEvent('classification_complete', () => store.fetchEmails(store.page))

// Auto-open detail if navigated with ?detail=emailId (from Dashboard)
const detailId = route.query.detail as string | undefined
if (detailId) {
  openDetail(detailId)
  router.replace({ query: { ...route.query, detail: undefined } })
}

const categories = [
  { value: 'all', label: 'Toutes' },
  { value: 'pending', label: 'En attente' },
  ...Object.entries(CATEGORY_CONFIG).map(([value, cfg]) => ({ value, label: cfg.label })),
]

function setCategory(cat: string | number | bigint | Record<string, unknown> | null) {
  const val = String(cat ?? 'all')
  if (val === 'pending') {
    store.filters.category = undefined
    store.filters.processing_status = 'pending'
    store.filters.classification_status = undefined
  } else {
    store.filters.category = val === 'all' ? undefined : val
    store.filters.processing_status = undefined
    store.filters.classification_status = undefined
  }
  store.fetchEmails(1)
}

async function openDetail(emailId: string) {
  detailOpen.value = true
  await store.fetchEmailDetail(emailId)
}
</script>

<template>
  <PageHeader title="Emails" description="Tous les emails traités par InboxShield">
    <div class="relative">
      <Search class="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        v-model="store.filters.from_address"
        type="text"
        placeholder="Rechercher un expéditeur..."
        class="pl-9 sm:w-64"
        @keyup.enter="store.fetchEmails(1)"
      />
    </div>
  </PageHeader>

  <Tabs default-value="all" class="w-full flex-col justify-start gap-6">
    <div class="flex items-center justify-between gap-2">
      <Label for="category-selector" class="sr-only">Catégorie</Label>
      <Select default-value="all" @update:model-value="setCategory">
        <SelectTrigger id="category-selector" class="flex w-fit @4xl/main:hidden" size="sm">
          <SelectValue placeholder="Catégorie" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="cat in categories" :key="cat.value" :value="cat.value">
            {{ cat.label }}
          </SelectItem>
        </SelectContent>
      </Select>

      <TabsList class="hidden @4xl/main:flex">
        <TabsTrigger
          v-for="cat in categories"
          :key="cat.value"
          :value="cat.value"
          @click="setCategory(cat.value)"
        >
          {{ cat.label }}
        </TabsTrigger>
      </TabsList>
    </div>

    <TabsContent value="all" class="relative flex flex-col gap-4" :force-mount="true">
      <div class="overflow-hidden rounded-lg border">
        <EmailTable
          :emails="store.emails"
          :loading="store.loading"
          @select="openDetail"
        />
      </div>

      <!-- Pagination -->
      <div v-if="store.pages > 1" class="flex items-center justify-between px-4">
        <div class="text-muted-foreground hidden flex-1 text-sm lg:flex">
          {{ store.total }} email(s) au total
        </div>
        <div class="flex w-full items-center gap-8 lg:w-fit">
          <div class="flex w-fit items-center justify-center text-sm font-medium">
            Page {{ store.page }} sur {{ store.pages }}
          </div>
          <div class="ml-auto flex items-center gap-2 lg:ml-0">
            <Button
              variant="outline"
              class="hidden size-8 lg:flex"
              size="icon"
              :disabled="store.page <= 1"
              @click="store.fetchEmails(1)"
            >
              <span class="sr-only">Première page</span>
              <ChevronsLeft />
            </Button>
            <Button
              variant="outline"
              class="size-8"
              size="icon"
              :disabled="store.page <= 1"
              @click="store.fetchEmails(store.page - 1)"
            >
              <span class="sr-only">Page précédente</span>
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              class="size-8"
              size="icon"
              :disabled="store.page >= store.pages"
              @click="store.fetchEmails(store.page + 1)"
            >
              <span class="sr-only">Page suivante</span>
              <ChevronRight />
            </Button>
            <Button
              variant="outline"
              class="hidden size-8 lg:flex"
              size="icon"
              :disabled="store.page >= store.pages"
              @click="store.fetchEmails(store.pages)"
            >
              <span class="sr-only">Dernière page</span>
              <ChevronsRight />
            </Button>
          </div>
        </div>
      </div>
    </TabsContent>
  </Tabs>

  <EmailDetailSheet v-model:open="detailOpen" />
</template>
