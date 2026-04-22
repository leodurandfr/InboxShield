<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { toast } from 'vue-sonner'
import {
  Users,
  Search,
  Ban,
  CheckCircle2,
  Newspaper,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-vue-next'
import { useSendersStore } from '@/stores/senders'
import { formatRelativeDate, CATEGORY_CONFIG } from '@/lib/utils'

import PageHeader from '@/components/layout/PageHeader.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'

const store = useSendersStore()

const searchQuery = ref('')
const activeTab = ref('all')

const tabs = [
  { value: 'all', label: 'Tous' },
  { value: 'newsletter', label: 'Newsletters' },
  { value: 'blocked', label: 'Bloqués' },
]

function setTab(val: string) {
  activeTab.value = val
  store.filters.is_newsletter = val === 'newsletter' ? true : undefined
  store.filters.is_blocked = val === 'blocked' ? true : undefined
  store.fetchSenders(1)
}

function handleSearch() {
  store.filters.search = searchQuery.value || undefined
  store.fetchSenders(1)
}

function clearSearch() {
  searchQuery.value = ''
  store.filters.search = undefined
  store.fetchSenders(1)
}

async function handleBlock(id: string) {
  try {
    await store.blockSender(id)
    toast.success('Expéditeur bloqué')
  } catch {
    toast.error('Erreur lors du blocage')
  }
}

async function handleUnblock(id: string) {
  try {
    await store.unblockSender(id)
    toast.success('Expéditeur débloqué')
  } catch {
    toast.error('Erreur lors du déblocage')
  }
}

function openDetail(id: string) {
  store.fetchSenderDetail(id)
}

const totalPages = computed(() => Math.ceil(store.total / store.perPage))

function categoryLabel(cat: string | null) {
  if (!cat) return 'Inconnu'
  return CATEGORY_CONFIG[cat]?.label ?? cat
}

function categoryClass(cat: string | null) {
  if (!cat) return ''
  return CATEGORY_CONFIG[cat]?.bgClass ?? ''
}

onMounted(() => {
  store.fetchSenders()
})
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <PageHeader title="Expéditeurs" description="Consultez les profils d'expéditeurs et gérez les blocages." />

    <!-- Filters -->
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <Tabs :model-value="activeTab">
        <TabsList>
          <TabsTrigger
            v-for="tab in tabs"
            :key="tab.value"
            :value="tab.value"
            @click="setTab(tab.value)"
          >
            {{ tab.label }}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <div class="relative w-full sm:w-72">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          v-model="searchQuery"
          placeholder="Rechercher un expéditeur..."
          class="pl-9 pr-9"
          @keydown.enter="handleSearch"
        />
        <button
          v-if="searchQuery"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          @click="clearSearch"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- Table -->
    <Card>
      <CardContent class="p-0">
        <!-- Loading -->
        <div v-if="store.loading" class="space-y-3 p-6">
          <Skeleton v-for="i in 5" :key="i" class="h-12 w-full" />
        </div>

        <!-- Empty state -->
        <div v-else-if="store.senders.length === 0" class="flex flex-col items-center gap-3 py-16 text-center">
          <Users class="h-12 w-12 text-muted-foreground/40" />
          <p class="text-lg font-medium">Aucun expéditeur</p>
          <p class="max-w-sm text-sm text-muted-foreground">
            Les profils d'expéditeurs sont créés automatiquement lors du traitement des emails.
          </p>
        </div>

        <!-- Data table -->
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>Expéditeur</TableHead>
              <TableHead class="hidden sm:table-cell">Catégorie</TableHead>
              <TableHead class="hidden md:table-cell">Emails</TableHead>
              <TableHead class="hidden lg:table-cell">Dernier email</TableHead>
              <TableHead>Tags</TableHead>
              <TableHead class="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="sender in store.senders"
              :key="sender.id"
              class="cursor-pointer"
              @click="openDetail(sender.id)"
            >
              <TableCell>
                <div class="flex flex-col">
                  <span class="font-medium">{{ sender.display_name || sender.email_address }}</span>
                  <span v-if="sender.display_name" class="text-xs text-muted-foreground">{{ sender.email_address }}</span>
                  <span v-if="sender.domain" class="text-xs text-muted-foreground">{{ sender.domain }}</span>
                </div>
              </TableCell>
              <TableCell class="hidden sm:table-cell">
                <Badge v-if="sender.primary_category" variant="secondary" :class="categoryClass(sender.primary_category)">
                  {{ categoryLabel(sender.primary_category) }}
                </Badge>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="hidden md:table-cell font-mono text-sm">
                {{ sender.total_emails }}
              </TableCell>
              <TableCell class="hidden lg:table-cell text-sm text-muted-foreground">
                {{ sender.last_email_at ? formatRelativeDate(sender.last_email_at) : '—' }}
              </TableCell>
              <TableCell>
                <div class="flex gap-1">
                  <Badge v-if="sender.is_newsletter" variant="outline" class="text-xs">
                    <Newspaper class="mr-1 h-3 w-3" />
                    Newsletter
                  </Badge>
                  <Badge v-if="sender.is_blocked" variant="destructive" class="text-xs">
                    <Ban class="mr-1 h-3 w-3" />
                    Bloqué
                  </Badge>
                </div>
              </TableCell>
              <TableCell @click.stop>
                <Button
                  v-if="sender.is_blocked"
                  variant="ghost"
                  size="sm"
                  @click="handleUnblock(sender.id)"
                >
                  <CheckCircle2 class="h-4 w-4 text-emerald-600" />
                </Button>
                <Button
                  v-else
                  variant="ghost"
                  size="sm"
                  @click="handleBlock(sender.id)"
                >
                  <Ban class="h-4 w-4 text-red-500" />
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between">
      <p class="text-sm text-muted-foreground">{{ store.total }} expéditeur{{ store.total > 1 ? 's' : '' }}</p>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="store.page <= 1" @click="store.fetchSenders(store.page - 1)">
          <ChevronLeft class="h-4 w-4" />
        </Button>
        <span class="text-sm">{{ store.page }} / {{ totalPages }}</span>
        <Button variant="outline" size="sm" :disabled="store.page >= totalPages" @click="store.fetchSenders(store.page + 1)">
          <ChevronRight class="h-4 w-4" />
        </Button>
      </div>
    </div>

    <!-- Sender detail sheet -->
    <Sheet :open="!!store.selectedSender" @update:open="(v: boolean) => { if (!v) store.closeDetail() }">
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{{ store.selectedSender?.display_name || store.selectedSender?.email_address }}</SheetTitle>
          <SheetDescription v-if="store.selectedSender?.display_name">
            {{ store.selectedSender.email_address }}
          </SheetDescription>
        </SheetHeader>

        <div v-if="store.selectedSender" class="mt-6 space-y-6">
          <!-- Info -->
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p class="text-muted-foreground">Domaine</p>
              <p class="font-medium">{{ store.selectedSender.domain || '—' }}</p>
            </div>
            <div>
              <p class="text-muted-foreground">Emails total</p>
              <p class="font-medium">{{ store.selectedSender.total_emails }}</p>
            </div>
            <div>
              <p class="text-muted-foreground">Catégorie principale</p>
              <Badge v-if="store.selectedSender.primary_category" variant="secondary" :class="categoryClass(store.selectedSender.primary_category)">
                {{ categoryLabel(store.selectedSender.primary_category) }}
              </Badge>
              <p v-else>—</p>
            </div>
            <div>
              <p class="text-muted-foreground">Dernier email</p>
              <p class="font-medium">{{ store.selectedSender.last_email_at ? formatRelativeDate(store.selectedSender.last_email_at) : '—' }}</p>
            </div>
          </div>

          <!-- Category breakdown -->
          <div v-if="store.selectedSender.category_stats && store.selectedSender.category_stats.length > 0">
            <h4 class="mb-3 text-sm font-medium">Répartition par catégorie</h4>
            <div class="space-y-2">
              <div
                v-for="cs in store.selectedSender.category_stats"
                :key="cs.category"
                class="flex items-center justify-between text-sm"
              >
                <Badge variant="secondary" :class="categoryClass(cs.category)">
                  {{ categoryLabel(cs.category) }}
                </Badge>
                <span class="font-mono">
                  {{ cs.count }}
                  <span v-if="cs.corrected_count > 0" class="text-xs text-muted-foreground">
                    ({{ cs.corrected_count }} corrigés)
                  </span>
                </span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 border-t pt-4">
            <Button
              v-if="store.selectedSender.is_blocked"
              variant="outline"
              @click="handleUnblock(store.selectedSender.id)"
            >
              <CheckCircle2 class="mr-2 h-4 w-4" />
              Débloquer
            </Button>
            <Button
              v-else
              variant="destructive"
              @click="handleBlock(store.selectedSender.id)"
            >
              <Ban class="mr-2 h-4 w-4" />
              Bloquer
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
