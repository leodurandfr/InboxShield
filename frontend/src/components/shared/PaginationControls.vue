<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const props = withDefaults(
  defineProps<{
    page: number
    perPage: number
    total: number
    itemLabel?: string
  }>(),
  { itemLabel: 'items' },
)

const emit = defineEmits<{
  (e: 'update:page', page: number): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.perPage)))
const rangeStart = computed(() => (props.total === 0 ? 0 : (props.page - 1) * props.perPage + 1))
const rangeEnd = computed(() => Math.min(props.page * props.perPage, props.total))

function prev() {
  if (props.page > 1) emit('update:page', props.page - 1)
}

function next() {
  if (props.page < totalPages.value) emit('update:page', props.page + 1)
}
</script>

<template>
  <div
    v-if="total > 0"
    class="flex items-center justify-between border-t px-6 py-3"
  >
    <p class="text-xs text-muted-foreground">
      {{ rangeStart }}&ndash;{{ rangeEnd }} sur {{ total }} {{ itemLabel }}
    </p>
    <div class="flex items-center gap-2">
      <Button variant="outline" size="sm" :disabled="page <= 1" @click="prev">
        <ChevronLeft class="size-4" />
        Précédent
      </Button>
      <span class="text-xs">{{ page }} / {{ totalPages }}</span>
      <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="next">
        Suivant
        <ChevronRight class="size-4" />
      </Button>
    </div>
  </div>
</template>
