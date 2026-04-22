<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="mb-6">
    <h1 class="text-2xl font-bold tracking-tight">{{ title }}</h1>
    <p v-if="description" class="mt-1 text-sm" :style="{ color: 'var(--color-muted-foreground)' }">
      {{ description }}
    </p>
    <div class="mt-4">
      <slot />
    </div>
  </div>
</template>
