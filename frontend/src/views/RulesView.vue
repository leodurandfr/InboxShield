<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ListFilter, Plus } from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import RuleCreateForm from '@/components/rules/RuleCreateForm.vue'
import RuleListItem from '@/components/rules/RuleListItem.vue'
import { useRulesStore } from '@/stores/rules'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'

const store = useRulesStore()
const showCreateForm = ref(false)

onMounted(() => {
  store.fetchRules()
})

async function toggleActive(id: string, current: boolean) {
  await store.toggleRule(id, !current)
}

async function deleteRule(id: string) {
  await store.deleteRule(id)
}
</script>

<template>
  <PageHeader title="Règles" description="Créez des règles pour trier automatiquement vos emails">
    <Button @click="showCreateForm = !showCreateForm">
      <Plus class="h-4 w-4" />
      Nouvelle règle
    </Button>
  </PageHeader>

  <!-- Create form -->
  <RuleCreateForm v-model:open="showCreateForm" />

  <!-- Rules list -->
  <Card>
    <CardContent class="p-0">
      <!-- Loading skeleton -->
      <div v-if="store.loading" class="space-y-0">
        <div v-for="i in 3" :key="i" class="flex items-center gap-4 px-6 py-4">
          <Skeleton class="h-5 w-9 rounded-full" />
          <div class="flex-1 space-y-2">
            <Skeleton class="h-4 w-40" />
            <div class="flex gap-2">
              <Skeleton class="h-5 w-16 rounded-full" />
              <Skeleton class="h-5 w-20 rounded-full" />
              <Skeleton class="h-3 w-12" />
            </div>
          </div>
          <Skeleton class="h-8 w-8 rounded-md" />
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="store.rules.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
        <ListFilter class="mb-3 h-10 w-10 text-muted-foreground/50" />
        <p class="text-sm font-medium">Aucune règle créée</p>
        <p class="mt-1 text-xs text-muted-foreground">Cliquez sur « Nouvelle règle » pour commencer.</p>
      </div>

      <!-- Rules -->
      <template v-else>
        <div v-for="(rule, index) in store.rules" :key="rule.id">
          <RuleListItem
            :rule="rule"
            @toggle="toggleActive"
            @delete="deleteRule"
          />
          <Separator v-if="index < store.rules.length - 1" />
        </div>
      </template>
    </CardContent>
  </Card>
</template>
