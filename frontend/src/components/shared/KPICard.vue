<script setup lang="ts">
import type { FunctionalComponent } from 'vue'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

defineProps<{
  title: string
  value: string | number
  subtitle?: string
  icon?: FunctionalComponent
  iconClass?: string
  valueClass?: string
}>()
</script>

<template>
  <Card>
    <CardContent class="flex items-start justify-between gap-3 pt-6">
      <div class="min-w-0 flex-1">
        <p class="text-xs font-medium text-muted-foreground">{{ title }}</p>
        <p :class="cn('mt-1 text-2xl font-bold tracking-tight', valueClass)">{{ value }}</p>
        <p v-if="subtitle" class="mt-1 text-xs text-muted-foreground">{{ subtitle }}</p>
      </div>
      <component :is="icon" v-if="icon" :class="cn('size-5 shrink-0 text-muted-foreground', iconClass)" />
    </CardContent>
  </Card>
</template>
