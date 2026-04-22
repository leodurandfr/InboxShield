<script setup lang="ts">
import { Check, EyeOff } from 'lucide-vue-next'
import { useThreadsStore } from '@/stores/threads'
import { formatRelativeDate, CATEGORY_CONFIG } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

const store = useThreadsStore()

function categoryLabel(cat: string | null | undefined) {
  if (!cat) return ''
  return CATEGORY_CONFIG[cat as keyof typeof CATEGORY_CONFIG]?.label ?? cat
}

function categoryClass(cat: string | null | undefined) {
  if (!cat) return ''
  return CATEGORY_CONFIG[cat as keyof typeof CATEGORY_CONFIG]?.bgClass ?? ''
}
</script>

<template>
  <Sheet
    :open="!!store.selectedThread"
    @update:open="(v: boolean) => { if (!v) store.closeDetail() }"
  >
    <SheetContent class="w-full sm:max-w-xl">
      <SheetHeader>
        <SheetTitle>
          {{ store.selectedThread?.subject_normalized || '(sans sujet)' }}
        </SheetTitle>
        <SheetDescription v-if="store.selectedThread">
          {{ store.selectedThread.email_count }} email{{ store.selectedThread.email_count > 1 ? 's' : '' }}
          &middot;
          {{ store.selectedThread.participants?.join(', ') || '—' }}
        </SheetDescription>
      </SheetHeader>

      <div v-if="store.detailLoading" class="mt-6 space-y-3">
        <Skeleton v-for="i in 4" :key="i" class="h-16 w-full" />
      </div>

      <div v-else-if="store.selectedThread" class="mt-6 space-y-4">
        <div class="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            class="text-emerald-700 dark:text-emerald-400"
            @click="store.resolveThread(store.selectedThread.id)"
          >
            <Check class="mr-1 size-4" />
            Résoudre
          </Button>
          <Button
            size="sm"
            variant="outline"
            @click="store.ignoreThread(store.selectedThread.id)"
          >
            <EyeOff class="mr-1 size-4" />
            Ignorer
          </Button>
        </div>

        <Separator />

        <div class="space-y-3">
          <div
            v-for="email in store.selectedThread.emails"
            :key="email.id"
            class="rounded-md border p-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium">
                  {{ email.from_name || email.from_address }}
                </p>
                <p class="truncate text-xs text-muted-foreground">
                  {{ email.subject || '(sans sujet)' }}
                </p>
              </div>
              <Badge
                v-if="email.category"
                variant="secondary"
                :class="categoryClass(email.category)"
              >
                {{ categoryLabel(email.category) }}
              </Badge>
            </div>
            <p class="mt-2 text-xs text-muted-foreground">
              {{ formatRelativeDate(email.date) }}
            </p>
          </div>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
