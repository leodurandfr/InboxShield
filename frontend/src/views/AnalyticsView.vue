<script setup lang="ts">
import { onMounted, computed } from 'vue'
import {
  BarChart3,
  Mail,
  ShieldAlert,
  Bot,
  Newspaper,
  CalendarDays,
  TrendingUp,
  Download,
  Activity,
  ArrowRightLeft,
  Clock3,
  Loader2,
} from 'lucide-vue-next'
import { useAnalyticsStore } from '@/stores/analytics'
import { CATEGORY_CONFIG } from '@/lib/utils'

import PageHeader from '@/components/layout/PageHeader.vue'
import KPICard from '@/components/shared/KPICard.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const store = useAnalyticsStore()

function setPeriod(p: string) {
  store.period = p
  store.fetchAll()
}

function categoryLabel(cat: string) {
  return CATEGORY_CONFIG[cat]?.label ?? cat
}

function categoryClass(cat: string) {
  return CATEGORY_CONFIG[cat]?.bgClass ?? ''
}

// Heatmap helpers
const DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => `${i}h`)

const heatmapMax = computed(() => {
  if (!store.heatmap.length) return 1
  return Math.max(...store.heatmap.map(e => e.count), 1)
})

function heatmapValue(day: number, hour: number): number {
  const entry = store.heatmap.find(e => e.day_of_week === day && e.hour === hour)
  return entry?.count ?? 0
}

function heatmapColor(count: number): string {
  if (count === 0) return 'bg-muted'
  const intensity = count / heatmapMax.value
  if (intensity < 0.25) return 'bg-primary/20'
  if (intensity < 0.5) return 'bg-primary/40'
  if (intensity < 0.75) return 'bg-primary/60'
  return 'bg-primary/90'
}

onMounted(() => {
  store.fetchAll()
})
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <div class="flex items-center justify-between">
      <PageHeader title="Analytics" description="Vue d'ensemble de l'activité de votre boîte mail." />
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          :disabled="store.exporting"
          @click="store.exportCsv()"
        >
          <Loader2 v-if="store.exporting" class="mr-1.5 h-4 w-4 animate-spin" />
          <Download v-else class="mr-1.5 h-4 w-4" />
          Export CSV
        </Button>
        <Tabs :model-value="store.period">
          <TabsList>
            <TabsTrigger value="7d" @click="setPeriod('7d')">7j</TabsTrigger>
            <TabsTrigger value="30d" @click="setPeriod('30d')">30j</TabsTrigger>
            <TabsTrigger value="90d" @click="setPeriod('90d')">90j</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>

    <!-- KPI Cards -->
    <div v-if="store.overview" class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <KPICard
        title="Emails reçus"
        :value="store.overview.emails_received"
        :subtitle="`${store.overview.emails_today} aujourd'hui`"
        :icon="Mail"
      />
      <KPICard
        title="Phishing bloqué"
        :value="store.overview.phishing_blocked"
        :subtitle="`${store.overview.spam_filtered} spam filtrés`"
        :icon="ShieldAlert"
        icon-class="text-red-500"
        value-class="text-red-600"
      />
      <KPICard
        title="Classification auto"
        :value="`${store.overview.auto_classification_rate}%`"
        :subtitle="`${store.overview.review_pending} en attente`"
        :icon="Bot"
      />
      <KPICard
        title="Newsletters"
        :value="store.overview.newsletters_tracked"
        subtitle="suivies"
        :icon="Newspaper"
      />
    </div>
    <div v-else class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card v-for="i in 4" :key="i"><CardContent class="pt-6"><Skeleton class="h-10 w-24" /></CardContent></Card>
    </div>

    <!-- Performance metrics -->
    <div v-if="store.performance" class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <KPICard
        title="Temps moyen"
        :value="store.performance.avg_processing_time_ms ? `${Math.round(store.performance.avg_processing_time_ms)}ms` : '—'"
        subtitle="par classification"
        :icon="Clock3"
      />
      <KPICard
        title="Taux review"
        :value="`${Math.round(store.performance.review_rate)}%`"
        :subtitle="`${Math.round(store.performance.correction_rate)}% corrigés`"
        :icon="Activity"
      />
      <Card>
        <CardHeader class="flex flex-row items-center justify-between pb-2">
          <CardTitle class="text-sm font-medium text-muted-foreground">Méthodes</CardTitle>
          <ArrowRightLeft class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="space-y-1 text-xs">
            <div class="flex justify-between">
              <span class="text-muted-foreground">Direct</span>
              <span class="font-mono">{{ Math.round(store.performance.direct_classification_rate * 100) }}%</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Règles</span>
              <span class="font-mono">{{ Math.round(store.performance.rule_classification_rate * 100) }}%</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">LLM</span>
              <span class="font-mono">{{ Math.round(store.performance.llm_classification_rate * 100) }}%</span>
            </div>
          </div>
        </CardContent>
      </Card>
      <KPICard
        title="Tokens utilisés"
        :value="store.performance.total_tokens_used.toLocaleString()"
        subtitle="sur la période"
        :icon="Bot"
      />
    </div>

    <div class="grid gap-6 lg:grid-cols-2">
      <!-- Categories breakdown -->
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <BarChart3 class="h-4 w-4" />
            Répartition par catégorie
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="store.categories.length > 0" class="space-y-3">
            <div
              v-for="cat in store.categories"
              :key="cat.category"
              class="flex items-center gap-3"
            >
              <Badge variant="secondary" :class="categoryClass(cat.category)" class="w-28 justify-center">
                {{ categoryLabel(cat.category) }}
              </Badge>
              <div class="flex-1">
                <Progress :model-value="cat.percentage" class="h-2" />
              </div>
              <span class="w-16 text-right text-sm font-mono text-muted-foreground">
                {{ cat.count }} <span class="text-xs">({{ cat.percentage }}%)</span>
              </span>
            </div>
          </div>
          <div v-else class="flex items-center justify-center py-8 text-sm text-muted-foreground">
            Pas de données pour cette période.
          </div>
        </CardContent>
      </Card>

      <!-- Top senders -->
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <TrendingUp class="h-4 w-4" />
            Top expéditeurs
          </CardTitle>
        </CardHeader>
        <CardContent class="p-0">
          <Table v-if="store.topSenders.length > 0">
            <TableHeader>
              <TableRow>
                <TableHead>Expéditeur</TableHead>
                <TableHead class="text-right">Emails</TableHead>
                <TableHead class="hidden sm:table-cell">Catégorie</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="sender in store.topSenders" :key="sender.email_address">
                <TableCell>
                  <div class="flex flex-col">
                    <span class="text-sm font-medium">{{ sender.display_name || sender.email_address }}</span>
                    <span v-if="sender.display_name" class="text-xs text-muted-foreground">{{ sender.email_address }}</span>
                  </div>
                </TableCell>
                <TableCell class="text-right font-mono text-sm">{{ sender.total_emails }}</TableCell>
                <TableCell class="hidden sm:table-cell">
                  <Badge v-if="sender.primary_category" variant="secondary" :class="categoryClass(sender.primary_category)">
                    {{ categoryLabel(sender.primary_category) }}
                  </Badge>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <div v-else class="flex items-center justify-center py-8 text-sm text-muted-foreground">
            Pas de données.
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Confusion matrix -->
    <Card v-if="store.confusionMatrix.length > 0">
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-base">
          <ArrowRightLeft class="h-4 w-4" />
          Matrice de confusion
        </CardTitle>
        <CardDescription>
          {{ store.totalCorrections }} corrections sur la période — catégorie originale → catégorie corrigée
        </CardDescription>
      </CardHeader>
      <CardContent class="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Classifié comme</TableHead>
              <TableHead>Corrigé en</TableHead>
              <TableHead class="text-right">Occurrences</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="entry in store.confusionMatrix" :key="`${entry.original_category}-${entry.corrected_category}`">
              <TableCell>
                <Badge variant="secondary" :class="categoryClass(entry.original_category)">
                  {{ categoryLabel(entry.original_category) }}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant="secondary" :class="categoryClass(entry.corrected_category)">
                  {{ categoryLabel(entry.corrected_category) }}
                </Badge>
              </TableCell>
              <TableCell class="text-right font-mono">{{ entry.count }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Daily volume chart -->
    <Card v-if="store.dailyVolume.length > 0">
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-base">
          <CalendarDays class="h-4 w-4" />
          Volume quotidien
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="flex items-end gap-1" style="height: 120px">
          <TooltipProvider>
            <Tooltip v-for="day in store.dailyVolume" :key="day.date">
              <TooltipTrigger as-child>
                <div class="group relative flex-1">
                  <div
                    class="w-full rounded-t bg-primary/80 transition-colors hover:bg-primary"
                    :style="{
                      height: `${Math.max(4, (day.total / Math.max(...store.dailyVolume.map(d => d.total))) * 100)}%`,
                    }"
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p class="text-xs">{{ day.date }}: {{ day.total }} emails</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <div class="mt-2 flex justify-between text-xs text-muted-foreground">
          <span>{{ store.dailyVolume[0]?.date }}</span>
          <span>{{ store.dailyVolume[store.dailyVolume.length - 1]?.date }}</span>
        </div>
      </CardContent>
    </Card>

    <!-- Heatmap -->
    <Card v-if="store.heatmap.length > 0">
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-base">
          <CalendarDays class="h-4 w-4" />
          Activité par heure
        </CardTitle>
        <CardDescription>
          Volume d'emails par jour de la semaine et heure de la journée
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <div class="min-w-[600px]">
            <!-- Hour labels -->
            <div class="flex">
              <div class="w-10 shrink-0" />
              <div class="flex flex-1">
                <div
                  v-for="h in HOUR_LABELS.filter((_, i) => i % 2 === 0)"
                  :key="h"
                  class="flex-1 text-center text-[10px] text-muted-foreground"
                >
                  {{ h }}
                </div>
              </div>
            </div>

            <!-- Grid rows -->
            <div
              v-for="(dayLabel, dayIdx) in DAY_LABELS"
              :key="dayIdx"
              class="flex items-center gap-0.5"
            >
              <div class="w-10 shrink-0 text-right text-[10px] text-muted-foreground pr-1.5">
                {{ dayLabel }}
              </div>
              <TooltipProvider>
                <Tooltip v-for="hourIdx in 24" :key="hourIdx">
                  <TooltipTrigger as-child>
                    <div
                      class="flex-1 aspect-square rounded-sm"
                      :class="heatmapColor(heatmapValue(dayIdx, hourIdx - 1))"
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p class="text-xs">{{ dayLabel }} {{ hourIdx - 1 }}h: {{ heatmapValue(dayIdx, hourIdx - 1) }} emails</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <!-- Legend -->
            <div class="mt-3 flex items-center justify-end gap-1 text-[10px] text-muted-foreground">
              <span>Moins</span>
              <div class="h-3 w-3 rounded-sm bg-muted" />
              <div class="h-3 w-3 rounded-sm bg-primary/20" />
              <div class="h-3 w-3 rounded-sm bg-primary/40" />
              <div class="h-3 w-3 rounded-sm bg-primary/60" />
              <div class="h-3 w-3 rounded-sm bg-primary/90" />
              <span>Plus</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
