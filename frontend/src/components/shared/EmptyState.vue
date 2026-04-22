<script setup lang="ts">
import type { FunctionalComponent } from 'vue'

defineProps<{
  icon?: FunctionalComponent
  title: string
  description?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-center">
    <component :is="icon" v-if="icon" class="mb-3 size-10 text-muted-foreground" />
    <p class="text-sm font-medium">{{ title }}</p>
    <p v-if="description" class="mt-1 max-w-sm text-xs text-muted-foreground">
      {{ description }}
    </p>
    <div class="mt-4">
      <slot />
    </div>
  </div>
</template>
