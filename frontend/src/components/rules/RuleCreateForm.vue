<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { toast } from 'vue-sonner'
import { Sparkles, X } from 'lucide-vue-next'
import { useRulesStore } from '@/stores/rules'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', value: boolean): void }>()

const store = useRulesStore()

type Mode = 'structured' | 'natural'

const mode = ref<Mode>('structured')
const submitting = ref(false)

const form = reactive({
  name: '',
  category: '',
  field: 'from_address',
  operator: 'contains',
  value: '',
  natural_text: '',
})

const visible = computed({
  get: () => props.open,
  set: (v: boolean) => emit('update:open', v),
})

function reset() {
  form.name = ''
  form.category = ''
  form.field = 'from_address'
  form.operator = 'contains'
  form.value = ''
  form.natural_text = ''
  mode.value = 'structured'
}

async function submit() {
  if (!form.name.trim()) {
    toast.error('Nom requis')
    return
  }
  submitting.value = true
  try {
    if (mode.value === 'structured') {
      await store.createRule({
        name: form.name,
        type: 'structured',
        category: form.category || null,
        conditions: {
          field: form.field,
          operator: form.operator,
          value: form.value,
        },
        actions: form.category ? [{ type: 'set_category', category: form.category }] : [],
        is_active: true,
      })
    } else {
      await store.createRule({
        name: form.name,
        type: 'natural',
        natural_text: form.natural_text,
        category: form.category || null,
        is_active: true,
      })
    }
    toast.success('Règle créée')
    reset()
    emit('update:open', false)
  } catch (e) {
    toast.error('Échec de la création')
    console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Card v-if="visible" class="border-dashed">
    <CardHeader class="flex flex-row items-center justify-between">
      <CardTitle class="text-base">Nouvelle règle</CardTitle>
      <Button variant="ghost" size="icon-sm" @click="emit('update:open', false)">
        <X class="size-4" />
      </Button>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="flex gap-2">
        <Button
          :variant="mode === 'structured' ? 'default' : 'outline'"
          size="sm"
          @click="mode = 'structured'"
        >
          Structurée
        </Button>
        <Button
          :variant="mode === 'natural' ? 'default' : 'outline'"
          size="sm"
          @click="mode = 'natural'"
        >
          <Sparkles class="size-3.5" />
          Langage naturel
        </Button>
      </div>

      <div class="space-y-2">
        <Label>Nom</Label>
        <Input v-model="form.name" placeholder="Ex: Archiver les newsletters de X" />
      </div>

      <template v-if="mode === 'structured'">
        <div class="grid gap-2 sm:grid-cols-3">
          <div class="space-y-2">
            <Label>Champ</Label>
            <Select v-model="form.field">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="from_address">Expéditeur</SelectItem>
                <SelectItem value="subject">Sujet</SelectItem>
                <SelectItem value="body">Corps</SelectItem>
                <SelectItem value="domain">Domaine</SelectItem>
                <SelectItem value="folder">Dossier</SelectItem>
                <SelectItem value="has_attachments">Pièces jointes</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-2">
            <Label>Opérateur</Label>
            <Select v-model="form.operator">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="contains">contient</SelectItem>
                <SelectItem value="not_contains">ne contient pas</SelectItem>
                <SelectItem value="equals">égale</SelectItem>
                <SelectItem value="starts_with">commence par</SelectItem>
                <SelectItem value="ends_with">finit par</SelectItem>
                <SelectItem value="matches">regex</SelectItem>
                <SelectItem value="in">parmi</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-2">
            <Label>Valeur</Label>
            <Input v-model="form.value" placeholder="..." />
          </div>
        </div>
      </template>

      <template v-else>
        <div class="space-y-2">
          <Label>Description</Label>
          <Textarea
            v-model="form.natural_text"
            rows="3"
            placeholder="Ex: Archiver les emails de notifications GitHub de plus de 7 jours"
          />
        </div>
      </template>

      <div class="space-y-2">
        <Label>Catégorie à appliquer (optionnel)</Label>
        <Select v-model="form.category">
          <SelectTrigger><SelectValue placeholder="Aucune" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="important">Important</SelectItem>
            <SelectItem value="work">Travail</SelectItem>
            <SelectItem value="personal">Personnel</SelectItem>
            <SelectItem value="newsletter">Newsletter</SelectItem>
            <SelectItem value="promotion">Promotion</SelectItem>
            <SelectItem value="notification">Notification</SelectItem>
            <SelectItem value="spam">Spam</SelectItem>
            <SelectItem value="phishing">Phishing</SelectItem>
            <SelectItem value="transactional">Transactionnel</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="emit('update:open', false)">Annuler</Button>
        <Button :disabled="submitting" @click="submit">Créer</Button>
      </div>
    </CardContent>
  </Card>
</template>
