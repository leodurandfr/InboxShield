<script setup lang="ts">
import type { Email } from '@/lib/types'
import { CATEGORY_CONFIG, formatRelativeDate } from '@/lib/utils'
import { Mail, Loader2 } from 'lucide-vue-next'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import EmptyState from '@/components/shared/EmptyState.vue'

defineProps<{
  emails: Email[]
  loading: boolean
  skeletonRows?: number
  emptyTitle?: string
  emptyDescription?: string
}>()

const emit = defineEmits<{
  select: [emailId: string]
}>()

function getInitials(name: string | null, email: string): string {
  if (name) {
    return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
  }
  return email.charAt(0).toUpperCase()
}
</script>

<template>
  <!-- Loading skeleton -->
  <Table v-if="loading">
    <TableHeader class="bg-muted">
      <TableRow>
        <TableHead class="w-10" />
        <TableHead class="w-24">Catégorie</TableHead>
        <TableHead>Expéditeur</TableHead>
        <TableHead class="w-16 text-right">Score</TableHead>
        <TableHead class="w-20 text-right">Date</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow v-for="i in (skeletonRows ?? 8)" :key="i">
        <TableCell class="pl-4 pr-0">
          <Skeleton class="h-8 w-8 rounded-full" />
        </TableCell>
        <TableCell>
          <Skeleton class="h-5 w-16 rounded-full" />
        </TableCell>
        <TableCell>
          <div class="space-y-1.5">
            <Skeleton class="h-4 w-32" />
            <Skeleton class="h-3 w-48" />
          </div>
        </TableCell>
        <TableCell>
          <Skeleton class="ml-auto h-5 w-10 rounded-full" />
        </TableCell>
        <TableCell>
          <Skeleton class="ml-auto h-3 w-12" />
        </TableCell>
      </TableRow>
    </TableBody>
  </Table>

  <!-- Empty state -->
  <EmptyState
    v-else-if="emails.length === 0"
    :icon="Mail"
    :title="emptyTitle ?? 'Aucun email trouvé'"
    :description="emptyDescription ?? 'Modifiez vos filtres ou attendez de nouveaux emails.'"
  />

  <!-- Email table -->
  <Table v-else>
    <TableHeader class="bg-muted">
      <TableRow>
        <TableHead class="w-10" />
        <TableHead class="w-24">Catégorie</TableHead>
        <TableHead>Expéditeur</TableHead>
        <TableHead class="w-16 text-right">Score</TableHead>
        <TableHead class="w-20 text-right">Date</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow
        v-for="email in emails"
        :key="email.id"
        class="cursor-pointer"
        @click="emit('select', email.id)"
      >
        <TableCell class="w-10 pl-4 pr-0">
          <Avatar class="h-8 w-8">
            <AvatarFallback class="text-xs">
              {{ getInitials(email.from_name, email.from_address) }}
            </AvatarFallback>
          </Avatar>
        </TableCell>

        <TableCell class="w-24">
          <Badge
            v-if="email.classification"
            variant="outline"
            class="px-1.5"
            :class="CATEGORY_CONFIG[email.classification.category]?.bgClass"
          >
            {{ CATEGORY_CONFIG[email.classification.category]?.label ?? email.classification.category }}
          </Badge>
          <Badge v-else variant="outline" class="text-muted-foreground px-1.5">
            {{ email.processing_status }}
          </Badge>
        </TableCell>

        <TableCell>
          <p class="truncate text-sm" :class="{ 'font-semibold': !email.is_read }">
            {{ email.from_name || email.from_address }}
          </p>
          <p class="truncate text-xs text-muted-foreground">
            {{ email.subject || '(sans sujet)' }}
          </p>
        </TableCell>

        <TableCell class="w-16 text-right">
          <Badge
            v-if="email.classification"
            variant="secondary"
            class="tabular-nums text-[11px] px-1.5"
          >
            {{ Math.round(email.classification.confidence * 100) }}%
          </Badge>
        </TableCell>

        <TableCell class="w-20 pr-4 text-right text-xs text-muted-foreground">
          {{ formatRelativeDate(email.date) }}
        </TableCell>
      </TableRow>
    </TableBody>
  </Table>
</template>
