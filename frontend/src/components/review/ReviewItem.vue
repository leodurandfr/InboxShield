<script setup lang="ts">
import { ref } from 'vue'
import type { ReviewItem as ReviewItemType } from '@/lib/types'
import { CATEGORY_CONFIG } from '@/lib/utils'
import { Check, X, ChevronsUpDown } from 'lucide-vue-next'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  email: Email
  classification: Classification
}>()

const emit = defineEmits<{
  approve: [emailId: string]
  correct: [emailId: string, category: string]
}>()

const correcting = ref(false)
const selectedCategory = ref('')

const allCategories = Object.entries(CATEGORY_CONFIG).map(([value, cfg]) => ({
  value,
  label: cfg.label,
}))

function getInitials(name: string | null, email: string): string {
  if (name) return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
  return email.charAt(0).toUpperCase()
}

function startCorrection() {
  correcting.value = true
  selectedCategory.value = ''
}

function submitCorrection() {
  if (!selectedCategory.value) return
  emit('correct', props.email.id, selectedCategory.value)
  correcting.value = false
}
</script>

<template>
  <Collapsible class="px-6 py-4">
    <div class="flex items-start gap-4">
      <!-- Avatar -->
      <Avatar class="mt-0.5 h-8 w-8 shrink-0">
        <AvatarFallback class="text-xs">
          {{ getInitials(email.from_name, email.from_address) }}
        </AvatarFallback>
      </Avatar>

      <!-- Info -->
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <Badge
            variant="secondary"
            :class="CATEGORY_CONFIG[classification.category]?.bgClass"
          >
            {{ CATEGORY_CONFIG[classification.category]?.label ?? classification.category }}
          </Badge>
          <span class="text-xs text-muted-foreground">
            {{ Math.round(classification.confidence * 100) }}% confiance
          </span>
        </div>

        <p class="mt-1 text-sm font-medium">
          {{ email.from_name || email.from_address }}
        </p>
        <p class="truncate text-sm text-muted-foreground">
          {{ email.subject || '(sans sujet)' }}
        </p>

        <!-- Expand trigger -->
        <CollapsibleTrigger as-child>
          <Button variant="ghost" size="sm" class="mt-1 h-auto gap-1 px-0 py-0 text-xs text-primary">
            <ChevronsUpDown class="h-3 w-3" />
            Détails
          </Button>
        </CollapsibleTrigger>
      </div>

      <!-- Actions -->
      <div class="flex shrink-0 gap-2">
        <Button
          variant="outline"
          size="icon-sm"
          class="text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20"
          title="Approuver"
          @click="emit('approve', email.id)"
        >
          <Check class="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          class="text-amber-600 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-900/20"
          title="Corriger"
          @click="startCorrection"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>
    </div>

    <!-- Expanded details -->
    <CollapsibleContent>
      <div class="mt-3 ml-12 space-y-3 rounded-md bg-muted p-3">
        <div>
          <p class="text-xs font-medium text-muted-foreground">Explication :</p>
          <p class="mt-1 text-sm">{{ classification.explanation || '—' }}</p>
        </div>
        <div v-if="email.body_excerpt">
          <p class="text-xs font-medium text-muted-foreground">Extrait :</p>
          <ScrollArea class="mt-1 max-h-32">
            <p class="whitespace-pre-wrap text-xs text-muted-foreground">
              {{ email.body_excerpt }}
            </p>
          </ScrollArea>
        </div>
      </div>
    </CollapsibleContent>

    <!-- Correction form -->
    <div v-if="correcting" class="mt-3 ml-12 flex items-center gap-2">
      <Select v-model="selectedCategory">
        <SelectTrigger class="w-48">
          <SelectValue placeholder="Choisir une catégorie" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="cat in allCategories" :key="cat.value" :value="cat.value">
            {{ cat.label }}
          </SelectItem>
        </SelectContent>
      </Select>
      <Button
        size="sm"
        :disabled="!selectedCategory"
        @click="submitCorrection"
      >
        Corriger
      </Button>
      <Button
        variant="ghost"
        size="sm"
        @click="correcting = false"
      >
        Annuler
      </Button>
    </div>
  </Collapsible>
</template>
