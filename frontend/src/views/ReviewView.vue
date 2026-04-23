<script setup lang="ts">
import { CheckCircle2 } from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import ReviewItem from '@/components/review/ReviewItem.vue'
import { useReviewStore } from '@/stores/review'
import { usePolling } from '@/composables/usePolling'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

const store = useReviewStore()

usePolling(async () => { await store.fetchQueue(); await store.fetchStats() }, 30_000)

async function approveAll() {
  const ids = store.items.map((i) => i.email.id)
  await store.bulkApprove(ids)
}
</script>

<template>
  <PageHeader title="Review Queue" :description="`${store.total} email(s) en attente de validation`">
    <AlertDialog v-if="store.items.length > 0">
      <AlertDialogTrigger as-child>
        <Button>Tout approuver</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Tout approuver ?</AlertDialogTitle>
          <AlertDialogDescription>
            Vous allez approuver {{ store.items.length }} email(s) en une seule opération.
            Cette action est irréversible.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction @click="approveAll">Confirmer</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </PageHeader>

  <Card>
    <CardContent class="p-0">
      <!-- Loading skeleton -->
      <div v-if="store.loading" class="space-y-0">
        <div v-for="i in 4" :key="i" class="flex items-center gap-4 px-6 py-4">
          <Skeleton class="h-8 w-8 rounded-full" />
          <div class="flex-1 space-y-2">
            <div class="flex items-center gap-2">
              <Skeleton class="h-5 w-20 rounded-full" />
              <Skeleton class="h-3 w-12" />
            </div>
            <Skeleton class="h-4 w-40" />
            <Skeleton class="h-3 w-64" />
          </div>
          <div class="flex gap-2">
            <Skeleton class="h-8 w-8 rounded-md" />
            <Skeleton class="h-8 w-8 rounded-md" />
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="store.items.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle2 class="mb-3 h-10 w-10 text-emerald-500" />
        <p class="text-sm font-medium">Aucun email en attente</p>
        <p class="mt-1 text-xs text-muted-foreground">
          Tous les emails ont été traités.
        </p>
      </div>

      <!-- Review items -->
      <template v-else>
        <div v-for="(item, index) in store.items" :key="item.email.id">
          <ReviewItem
            :email="item.email"
            :classification="item.classification"
            @approve="store.approve"
            @correct="store.correct"
          />
          <Separator v-if="index < store.items.length - 1" />
        </div>
      </template>
    </CardContent>
  </Card>
</template>
