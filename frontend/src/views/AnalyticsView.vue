<script setup lang="ts">
import { onMounted } from 'vue'
import {
  BarChart3,
  Mail,
  ShieldAlert,
  Bot,
  Newspaper,
  CalendarDays,
  TrendingUp,
} from 'lucide-vue-next'
import { useAnalyticsStore } from '@/stores/analytics'
import { CATEGORY_CONFIG } from '@/lib/utils'

import PageHeader from '@/components/layout/PageHeader.vue'
import KPICard from '@/components/shared/KPICard.vue'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

onMounted(() => {
  store.fetchAll()
})
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <div class="flex items-center justify-between">
      <PageHeader title="Analytics" description="Vue d'ensemble de l'activité de votre boîte mail." />
      <Tabs :model-value="store.period">
        <TabsList>
          <TabsTrigger value="7d" @click="setPeriod('7d')">7j</TabsTrigger>
          <TabsTrigger value="30d" @click="setPeriod('30d')">30j</TabsTrigger>
          <TabsTrigger value="90d" @click="setPeriod('90d')">90j</TabsTrigger>
        </TabsList>
      </Tabs>
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
  </div>
</template>
