<script setup lang="ts">
import type { Rule } from '@/lib/types'
import { CATEGORY_CONFIG } from '@/lib/utils'
import { Mail, Pencil, Trash2 } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
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

defineProps<{
  rule: Rule
}>()

const emit = defineEmits<{
  toggle: [id: string, current: boolean]
  edit: [rule: Rule]
  viewEmails: [rule: Rule]
  delete: [id: string]
}>()
</script>

<template>
  <div class="flex items-center gap-4 px-6 py-3">
    <!-- Toggle active -->
    <Switch
      :model-value="rule.is_active"
      @update:model-value="emit('toggle', rule.id, rule.is_active)"
    />

    <!-- Info -->
    <div class="min-w-0 flex-1">
      <p class="text-sm font-medium" :class="{ 'opacity-50': !rule.is_active }">{{ rule.name }}</p>
      <p v-if="rule.type === 'natural' && rule.natural_text" class="mt-0.5 truncate text-xs text-muted-foreground/70 italic" :class="{ 'opacity-50': !rule.is_active }">
        {{ rule.natural_text }}
      </p>
      <div class="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary" :class="rule.type === 'natural' ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400' : ''">
          {{ rule.type === 'natural' ? 'IA' : 'structurée' }}
        </Badge>
        <Badge
          v-if="rule.category"
          variant="secondary"
          :class="CATEGORY_CONFIG[rule.category]?.bgClass"
        >
          {{ CATEGORY_CONFIG[rule.category]?.label }}
        </Badge>
        <button
          class="cursor-pointer underline-offset-2 hover:underline"
          @click="emit('viewEmails', rule)"
        >
          {{ rule.match_count }} matchs
        </button>
        <span>Priorité {{ rule.priority }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex shrink-0 items-center gap-1">
      <!-- Edit -->
      <Button variant="ghost" size="icon-sm" @click="emit('edit', rule)">
        <Pencil class="h-4 w-4" />
      </Button>

      <!-- View matched emails -->
      <Button
        variant="ghost"
        size="icon-sm"
        :disabled="rule.match_count === 0"
        @click="emit('viewEmails', rule)"
      >
        <Mail class="h-4 w-4" />
      </Button>

      <!-- Delete -->
      <AlertDialog>
      <AlertDialogTrigger as-child>
        <Button variant="ghost" size="icon-sm" class="shrink-0 text-destructive hover:text-destructive">
          <Trash2 class="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer cette règle ?</AlertDialogTitle>
          <AlertDialogDescription>
            La règle « {{ rule.name }} » sera définitivement supprimée.
            Cette action est irréversible.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            @click="emit('delete', rule.id)"
          >
            Supprimer
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
  </div>
</template>
