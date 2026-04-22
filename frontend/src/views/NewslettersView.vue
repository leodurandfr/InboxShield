<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { toast } from 'vue-sonner'
import {
  Newspaper,
  MailX,
  Clock,
  Loader2,
} from 'lucide-vue-next'
import { useNewslettersStore } from '@/stores/newsletters'
import { formatRelativeDate } from '@/lib/utils'

import PageHeader from '@/components/layout/PageHeader.vue'
import KPICard from '@/components/shared/KPICard.vue'
import PaginationControls from '@/components/shared/PaginationControls.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'

const store = useNewslettersStore()

const selectedIds = ref<Set<string>>(new Set())
const unsubscribing = ref<Set<string>>(new Set())
const statusFilter = ref<string | undefined>(undefined)

const statusTabs = [
  { value: undefined, label: 'Toutes' },
  { value: 'subscribed', label: 'Abonnées' },
  { value: 'unsubscribed', label: 'Désabonnées' },
]

function setStatusFilter(val: string | undefined) {
  statusFilter.value = val
  store.filters.status = val
  selectedIds.value.clear()
  store.fetchNewsletters(1)
}

const allSelected = computed(() =>
  store.newsletters.length > 0 && store.newsletters.every(n => selectedIds.value.has(n.id)),
)

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value.clear()
  } else {
    store.newsletters.forEach(n => selectedIds.value.add(n.id))
  }
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

async function handleUnsubscribe(id: string) {
  unsubscribing.value.add(id)
  try {
    await store.unsubscribe(id)
    toast.success('Désinscription effectuée')
    selectedIds.value.delete(id)
  } catch {
    toast.error('Échec de la désinscription')
  } finally {
    unsubscribing.value.delete(id)
  }
}

async function handleBulkUnsubscribe() {
  const ids = Array.from(selectedIds.value)
  if (ids.length === 0) return
  try {
    const res = await store.bulkUnsubscribe(ids)
    toast.success(`Désinscription : ${res.success} réussies, ${res.failed} échouées`)
    selectedIds.value.clear()
  } catch {
    toast.error('Erreur lors de la désinscription groupée')
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'subscribed': return { label: 'Abonnée', class: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400' }
    case 'unsubscribed': return { label: 'Désabonnée', class: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' }
    case 'unsubscribing': return { label: 'En cours...', class: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' }
    case 'failed': return { label: 'Échouée', class: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' }
    default: return { label: status, class: '' }
  }
}

onMounted(() => {
  store.fetchNewsletters()
  store.fetchStats()
})
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <PageHeader title="Newsletters" description="Gérez vos abonnements et désabonnez-vous en un clic." />

    <!-- Stats cards -->
    <div v-if="store.stats" class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <KPICard title="Total" :value="store.stats.total_newsletters" />
      <KPICard title="Abonnées" :value="store.stats.total_subscribed" value-class="text-emerald-600" />
      <KPICard title="Taux lecture moy." :value="`${store.stats.avg_read_rate}%`" />
      <KPICard title="Jamais lues" :value="store.stats.never_read_count" value-class="text-amber-600" />
    </div>
    <div v-else-if="store.statsLoading" class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card v-for="i in 4" :key="i"><CardContent class="pt-6"><Skeleton class="h-10 w-20" /></CardContent></Card>
    </div>

    <!-- Filters + Bulk actions -->
    <div class="flex items-center justify-between gap-4">
      <Tabs :model-value="statusFilter ?? 'all'">
        <TabsList>
          <TabsTrigger
            v-for="tab in statusTabs"
            :key="tab.value ?? 'all'"
            :value="tab.value ?? 'all'"
            @click="setStatusFilter(tab.value)"
          >
            {{ tab.label }}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <Button
        v-if="selectedIds.size > 0"
        variant="destructive"
        size="sm"
        @click="handleBulkUnsubscribe"
      >
        <MailX class="mr-2 h-4 w-4" />
        Désabonner ({{ selectedIds.size }})
      </Button>
    </div>

    <!-- Table -->
    <Card>
      <CardContent class="p-0">
        <!-- Loading -->
        <div v-if="store.loading" class="space-y-3 p-6">
          <Skeleton v-for="i in 5" :key="i" class="h-12 w-full" />
        </div>

        <!-- Empty state -->
        <div v-else-if="store.newsletters.length === 0" class="flex flex-col items-center gap-3 py-16 text-center">
          <Newspaper class="h-12 w-12 text-muted-foreground/40" />
          <p class="text-lg font-medium">Aucune newsletter détectée</p>
          <p class="max-w-sm text-sm text-muted-foreground">
            Les newsletters seront automatiquement détectées lors du traitement des emails.
          </p>
        </div>

        <!-- Data table -->
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead class="w-10">
                <Checkbox :model-value="allSelected" @update:model-value="toggleSelectAll" />
              </TableHead>
              <TableHead>Newsletter</TableHead>
              <TableHead class="hidden sm:table-cell">Reçus</TableHead>
              <TableHead class="hidden md:table-cell">Taux lecture</TableHead>
              <TableHead class="hidden lg:table-cell">Fréquence</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead class="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="nl in store.newsletters" :key="nl.id">
              <TableCell>
                <Checkbox :checked="selectedIds.has(nl.id)" @update:checked="toggleSelect(nl.id)" />
              </TableCell>
              <TableCell>
                <div class="flex flex-col">
                  <span class="font-medium">{{ nl.name || nl.sender_address }}</span>
                  <span v-if="nl.name" class="text-xs text-muted-foreground">{{ nl.sender_address }}</span>
                  <span v-if="nl.last_received_at" class="mt-0.5 text-xs text-muted-foreground">
                    {{ formatRelativeDate(nl.last_received_at) }}
                  </span>
                </div>
              </TableCell>
              <TableCell class="hidden sm:table-cell">
                {{ nl.total_received }}
              </TableCell>
              <TableCell class="hidden md:table-cell">
                <div class="flex items-center gap-2">
                  <Progress :model-value="nl.read_rate" class="h-2 w-16" />
                  <span class="text-xs text-muted-foreground">{{ nl.read_rate }}%</span>
                </div>
              </TableCell>
              <TableCell class="hidden lg:table-cell">
                <span v-if="nl.frequency_days" class="text-sm text-muted-foreground">
                  <Clock class="mr-1 inline h-3 w-3" />
                  {{ nl.frequency_days < 2 ? 'Quotidien' : nl.frequency_days < 8 ? 'Hebdo' : nl.frequency_days < 35 ? 'Mensuel' : `~${Math.round(nl.frequency_days)}j` }}
                </span>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <Badge variant="secondary" :class="statusBadge(nl.subscription_status).class">
                  {{ statusBadge(nl.subscription_status).label }}
                </Badge>
              </TableCell>
              <TableCell>
                <Button
                  v-if="nl.subscription_status === 'subscribed' && nl.unsubscribe_method"
                  variant="ghost"
                  size="sm"
                  :disabled="unsubscribing.has(nl.id)"
                  @click="handleUnsubscribe(nl.id)"
                >
                  <Loader2 v-if="unsubscribing.has(nl.id)" class="h-4 w-4 animate-spin" />
                  <MailX v-else class="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Pagination -->
    <PaginationControls
      :page="store.page"
      :per-page="store.perPage"
      :total="store.total"
      item-label="newsletters"
      @update:page="store.fetchNewsletters"
    />
  </div>
</template>
