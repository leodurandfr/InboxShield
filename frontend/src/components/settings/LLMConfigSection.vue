<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Brain,
  Download,
  RefreshCw,
  X,
  Key,
  Eye,
  EyeOff,
  Check,
  TestTube,
  Loader2,
  Trash2,
  Star,
} from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
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
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const store = useSettingsStore()

const llmTesting = ref(false)
const saving = ref(false)
const apiKeyInput = ref('')
const showApiKey = ref(false)

const isCloudProvider = computed(() => {
  const p = store.settings?.llm_provider
  return p === 'anthropic' || p === 'openai' || p === 'mistral'
})

const defaultModels: Record<string, string> = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  mistral: 'mistral-large-latest',
}

watch(() => store.settings?.llm_provider, (newVal, oldVal) => {
  if (newVal && oldVal && newVal !== oldVal && store.settings) {
    apiKeyInput.value = ''
    showApiKey.value = false
    store.llmModels = []
    const defaultModel = defaultModels[newVal as keyof typeof defaultModels]
    if (defaultModel) {
      store.settings.llm_model = defaultModel
    } else {
      store.settings.llm_model = ''
    }
    store.fetchLLMModels(newVal)
  }
})

// LLM model pull
const pulling = ref(false)
const pullingModel = ref<string | null>(null)
const pullStatus = ref<string | null>(null)
const pullProgress = ref(0)
const pullId = ref<string | null>(null)
let pollInterval: ReturnType<typeof setInterval> | null = null

const recommendedModels = [
  { name: 'qwen2.5:7b', desc: 'Rapide, bon pour la classification', size: '4.7 GB', recommended: true },
  { name: 'qwen2.5:14b', desc: 'Plus precis, plus lent', size: '9.0 GB', recommended: false },
  { name: 'llama3.1:8b', desc: 'Meta Llama, polyvalent', size: '4.7 GB', recommended: false },
  { name: 'mistral:7b', desc: 'Mistral, bon en francais', size: '4.1 GB', recommended: false },
  { name: 'gemma2:9b', desc: 'Google Gemma, compact', size: '5.4 GB', recommended: false },
]

// Helpers
const isInstalled = (name: string) => store.llmModels.some(m => m.name === name)
const getModelSize = (name: string) => store.llmModels.find(m => m.name === name)?.size
const isSelected = (name: string) => store.settings?.llm_model === name

const otherInstalledModels = computed(() =>
  store.llmModels.filter(m => !recommendedModels.some(r => r.name === m.name)),
)

// Delete model confirmation
const deleteDialogOpen = ref(false)
const modelToDelete = ref<string | null>(null)
const deleting = ref(false)

function confirmDelete(modelName: string) {
  modelToDelete.value = modelName
  deleteDialogOpen.value = true
}

async function executeDelete() {
  if (!modelToDelete.value) return
  const name = modelToDelete.value
  deleting.value = true
  try {
    await store.deleteLLMModel(name)
    toast.success(`${name} supprime`)
    // If we deleted the currently selected model, clear the selection
    if (store.settings && store.settings.llm_model === name) {
      store.settings.llm_model = ''
    }
  } catch {
    toast.error(`Erreur lors de la suppression de ${name}`)
  } finally {
    deleting.value = false
    deleteDialogOpen.value = false
    modelToDelete.value = null
  }
}

async function saveSettings() {
  if (!store.settings) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = { ...store.settings }
    if (apiKeyInput.value) {
      payload.llm_api_key = apiKeyInput.value
    }
    await store.updateSettings(payload)
    if (apiKeyInput.value) {
      apiKeyInput.value = ''
      showApiKey.value = false
    }
    toast.success('Parametres sauvegardes')
    await store.fetchLLMModels()
  } catch {
    toast.error('Erreur lors de la sauvegarde')
  } finally {
    saving.value = false
  }
}

async function testLLM() {
  llmTesting.value = true
  try {
    const result = await store.testLLM()
    if (result.success) {
      toast.success(`LLM connecte (${result.latency_ms}ms)`)
    } else {
      toast.error(result.error || 'Connexion LLM echouee')
    }
  } catch {
    toast.error('Connexion LLM echouee')
  } finally {
    llmTesting.value = false
  }
}

async function pullModel(modelName: string) {
  pulling.value = true
  pullingModel.value = modelName
  pullProgress.value = 0
  pullStatus.value = `Demarrage du telechargement de ${modelName}...`
  try {
    const res = await api.post<{ pull_id: string }>('/settings/llm/pull', { model: modelName })
    pullId.value = res.pull_id
    startPollingPull()
  } catch {
    pullStatus.value = null
    pulling.value = false
    pullingModel.value = null
    toast.error(`Impossible de telecharger ${modelName}`)
  }
}

function startPollingPull() {
  stopPollingPull()
  pollInterval = setInterval(async () => {
    if (!pullId.value) return
    try {
      const res = await api.get<{ status: string; progress: number; model: string }>(`/settings/llm/pull/${pullId.value}`)
      pullProgress.value = res.progress
      pullStatus.value = res.status === 'done'
        ? null
        : res.status.startsWith('error')
          ? null
          : `Telechargement de ${res.model}... ${res.progress}%`

      if (res.status === 'done' || res.status === 'cancelled' || res.status.startsWith('error')) {
        stopPollingPull()
        pulling.value = false
        pullingModel.value = null
        pullId.value = null
        if (res.status === 'done') {
          toast.success(`${res.model} telecharge avec succes`)
          await store.fetchLLMModels()
        } else if (res.status.startsWith('error')) {
          toast.error(`Erreur: ${res.status}`)
        }
      }
    } catch {
      stopPollingPull()
      pulling.value = false
      pullingModel.value = null
      pullId.value = null
    }
  }, 2000)
}

function stopPollingPull() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function cancelPull() {
  if (!pullId.value) return
  try {
    await api.delete(`/settings/llm/pull/${pullId.value}`)
    toast.info('Telechargement annule')
  } catch {
    toast.error('Erreur lors de l\'annulation')
  } finally {
    stopPollingPull()
    pulling.value = false
    pullingModel.value = null
    pullId.value = null
    pullProgress.value = 0
    pullStatus.value = null
  }
}

function selectModel(modelName: string) {
  if (store.settings) {
    store.settings.llm_model = modelName
  }
}

onUnmounted(() => {
  stopPollingPull()
})
</script>

<template>
  <Card v-if="store.settings">
    <CardHeader>
      <div class="flex items-center gap-3">
        <div class="rounded-md bg-primary/10 p-2">
          <Brain class="h-5 w-5 text-primary" />
        </div>
        <div>
          <CardTitle>Configuration LLM</CardTitle>
          <CardDescription>Parametrez le modele d'intelligence artificielle</CardDescription>
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="space-y-2">
          <Label for="llm-provider">Provider</Label>
          <Select v-model="store.settings.llm_provider">
            <SelectTrigger id="llm-provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ollama">Ollama (local)</SelectItem>
              <SelectItem value="anthropic">Anthropic (Claude)</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="mistral">Mistral</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="space-y-2">
          <Label for="llm-model">Modele</Label>
          <div class="flex gap-2">
            <!-- Ollama: always show dropdown of local models -->
            <template v-if="!isCloudProvider">
              <Select v-if="store.llmModels.length > 0" v-model="store.settings.llm_model" class="flex-1">
                <SelectTrigger id="llm-model">
                  <SelectValue placeholder="Choisir un modele local" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="m in store.llmModels.filter(m => m.name)" :key="m.name" :value="m.name">
                    {{ m.name }}<template v-if="m.size"> ({{ m.size }})</template>
                  </SelectItem>
                </SelectContent>
              </Select>
              <Input v-else v-model="store.settings.llm_model" class="flex-1" placeholder="qwen2.5:7b" />
            </template>
            <!-- Cloud providers -->
            <template v-else>
              <Select v-if="store.llmModels.length > 0" v-model="store.settings.llm_model" class="flex-1">
                <SelectTrigger id="llm-model">
                  <SelectValue placeholder="Choisir un modele" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="m in store.llmModels.filter(m => m.name)" :key="m.name" :value="m.name">
                    {{ m.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <Input v-else v-model="store.settings.llm_model" class="flex-1" :placeholder="defaultModels[store.settings.llm_provider as keyof typeof defaultModels] ?? 'nom-du-modele'" />
            </template>
            <Button variant="outline" size="icon" @click="store.fetchLLMModels()" title="Rafraichir les modeles">
              <RefreshCw class="h-4 w-4" />
            </Button>
          </div>
        </div>

        <!-- API Key (cloud providers only) -->
        <div v-if="isCloudProvider" class="space-y-2 sm:col-span-2">
          <Label for="llm-api-key">
            Cle API
            <Badge v-if="store.settings.has_api_key" variant="outline" class="ml-2 text-xs text-emerald-600 dark:text-emerald-400">
              <Check class="mr-1 h-3 w-3" />
              configuree
            </Badge>
          </Label>
          <div class="flex gap-2">
            <div class="relative flex-1">
              <Key class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="llm-api-key"
                v-model="apiKeyInput"
                :type="showApiKey ? 'text' : 'password'"
                class="pl-9 pr-9 font-mono text-sm"
                :placeholder="store.settings.has_api_key ? '••••••••••••••••••••  (laisser vide pour garder la cle actuelle)' : 'sk-...'"
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                @click="showApiKey = !showApiKey"
              >
                <EyeOff v-if="showApiKey" class="h-4 w-4" />
                <Eye v-else class="h-4 w-4" />
              </button>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            La cle est chiffree avant stockage et n'est jamais exposee en clair.
          </p>
        </div>

        <!-- Base URL (OpenAI compatible) -->
        <div v-if="store.settings.llm_provider === 'openai'" class="space-y-2 sm:col-span-2">
          <Label for="llm-base-url">URL personnalisee (optionnel)</Label>
          <Input
            id="llm-base-url"
            :model-value="store.settings.llm_base_url ?? ''"
            placeholder="https://api.openai.com/v1 (par defaut)"
            @update:model-value="(v: string | number) => { if (store.settings) store.settings.llm_base_url = String(v) || null }"
          />
          <p class="text-xs text-muted-foreground">
            Pour les API compatibles OpenAI (Azure, Groq, Together, etc.)
          </p>
        </div>

        <div class="space-y-2">
          <Label for="polling-interval">Intervalle de polling (minutes)</Label>
          <Input id="polling-interval" v-model.number="store.settings.polling_interval_minutes" type="number" />
        </div>
        <div class="space-y-2">
          <Label for="confidence-threshold">Seuil de confiance</Label>
          <Input id="confidence-threshold" v-model.number="store.settings.confidence_threshold" type="number" step="0.05" min="0" max="1" />
        </div>
        <div class="flex items-center gap-3 sm:col-span-2">
          <Switch
            id="auto-mode"
            :checked="store.settings.auto_mode"
            @update:checked="(val: boolean) => { if (store.settings) store.settings.auto_mode = val }"
          />
          <Label for="auto-mode" class="cursor-pointer">
            Mode automatique (executer les actions sans validation manuelle)
          </Label>
        </div>
      </div>

      <!-- Ollama Model Management -->
      <Card v-if="store.settings.llm_provider === 'ollama'" class="mt-6 bg-muted/30">
        <CardContent class="pt-6">
          <h3 class="mb-4 flex items-center gap-2 text-sm font-medium">
            <Download class="h-4 w-4" />
            Modeles Ollama
          </h3>

          <!-- Pull progress bar (shown during download) -->
          <div v-if="pulling" class="mb-4 space-y-1 rounded-lg border bg-background p-3">
            <div class="flex items-center gap-2">
              <Loader2 class="h-4 w-4 shrink-0 animate-spin text-primary" />
              <Progress :model-value="pullProgress" class="h-2 flex-1" />
              <span class="shrink-0 text-xs font-mono text-muted-foreground">{{ pullProgress }}%</span>
              <Button variant="destructive" size="icon" class="h-6 w-6" @click="cancelPull" title="Annuler">
                <X class="h-3 w-3" />
              </Button>
            </div>
            <p v-if="pullStatus" class="text-xs text-muted-foreground">{{ pullStatus }}</p>
          </div>

          <!-- Recommended models list -->
          <div class="space-y-2">
            <div
              v-for="rec in recommendedModels"
              :key="rec.name"
              class="flex items-center justify-between rounded-lg border p-3 transition-colors"
              :class="{
                'border-primary/50 bg-primary/5': isSelected(rec.name),
                'hover:bg-muted/50': !isSelected(rec.name),
              }"
            >
              <div class="flex items-center gap-3 min-w-0">
                <button
                  v-if="isInstalled(rec.name)"
                  class="flex items-center"
                  :title="isSelected(rec.name) ? 'Modele selectionne' : 'Selectionner ce modele'"
                  @click="selectModel(rec.name)"
                >
                  <div
                    class="flex h-5 w-5 items-center justify-center rounded-full border-2 transition-colors"
                    :class="isSelected(rec.name) ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/30'"
                  >
                    <Check v-if="isSelected(rec.name)" class="h-3 w-3" />
                  </div>
                </button>
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-medium">{{ rec.name }}</p>
                    <Badge v-if="rec.recommended" variant="secondary" class="text-[10px] px-1.5 py-0">
                      <Star class="mr-0.5 h-2.5 w-2.5" />
                      recommande
                    </Badge>
                  </div>
                  <p class="text-xs text-muted-foreground">
                    {{ rec.desc }}
                    <span class="text-muted-foreground/70"> · {{ getModelSize(rec.name) ?? rec.size }}</span>
                  </p>
                </div>
              </div>
              <div class="flex items-center gap-2 shrink-0 ml-3">
                <Badge v-if="isInstalled(rec.name)" variant="outline" class="text-xs text-emerald-600 dark:text-emerald-400">
                  <Check class="mr-1 h-3 w-3" />
                  Installe
                </Badge>
                <Button
                  v-if="!isInstalled(rec.name)"
                  size="sm"
                  variant="secondary"
                  :disabled="pulling"
                  @click="pullModel(rec.name)"
                >
                  <Loader2 v-if="pulling && pullingModel === rec.name" class="h-3 w-3 animate-spin" />
                  <Download v-else class="h-3 w-3" />
                  Telecharger
                </Button>
                <Button
                  v-if="isInstalled(rec.name)"
                  variant="ghost"
                  size="icon"
                  class="h-7 w-7 text-muted-foreground hover:text-destructive"
                  :disabled="deleting"
                  title="Supprimer"
                  @click="confirmDelete(rec.name)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>

          <!-- Other installed models (not in recommended list) -->
          <template v-if="otherInstalledModels.length > 0">
            <Separator class="my-4" />
            <h4 class="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Autres modeles installes
            </h4>
            <div class="space-y-2">
              <div
                v-for="m in otherInstalledModels"
                :key="m.name"
                class="flex items-center justify-between rounded-lg border p-3 transition-colors"
                :class="{
                  'border-primary/50 bg-primary/5': isSelected(m.name),
                  'hover:bg-muted/50': !isSelected(m.name),
                }"
              >
                <div class="flex items-center gap-3 min-w-0">
                  <button
                    class="flex items-center"
                    :title="isSelected(m.name) ? 'Modele selectionne' : 'Selectionner ce modele'"
                    @click="selectModel(m.name)"
                  >
                    <div
                      class="flex h-5 w-5 items-center justify-center rounded-full border-2 transition-colors"
                      :class="isSelected(m.name) ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/30'"
                    >
                      <Check v-if="isSelected(m.name)" class="h-3 w-3" />
                    </div>
                  </button>
                  <div class="min-w-0">
                    <p class="text-sm font-medium">{{ m.name }}</p>
                    <p v-if="m.size" class="text-xs text-muted-foreground">{{ m.size }}</p>
                  </div>
                </div>
                <div class="flex items-center gap-2 shrink-0 ml-3">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7 text-muted-foreground hover:text-destructive"
                    :disabled="deleting"
                    title="Supprimer"
                    @click="confirmDelete(m.name)"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          </template>
        </CardContent>
      </Card>

      <Separator class="my-6" />

      <div class="flex items-center gap-2">
        <Button @click="saveSettings" :disabled="saving">
          <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
          {{ saving ? 'Sauvegarde...' : 'Sauvegarder' }}
        </Button>
        <Button variant="outline" @click="testLLM" :disabled="llmTesting">
          <Loader2 v-if="llmTesting" class="h-4 w-4 animate-spin" />
          <TestTube v-else class="h-4 w-4" />
          Tester le LLM
        </Button>
      </div>
    </CardContent>
  </Card>

  <!-- Delete confirmation dialog -->
  <AlertDialog :open="deleteDialogOpen" @update:open="(v) => { deleteDialogOpen = v }">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Supprimer le modele ?</AlertDialogTitle>
        <AlertDialogDescription>
          Le modele <span class="font-mono font-medium">{{ modelToDelete }}</span> sera supprime
          de votre machine. Vous pourrez le re-telecharger plus tard si necessaire.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel :disabled="deleting">Annuler</AlertDialogCancel>
        <AlertDialogAction
          class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          :disabled="deleting"
          @click.prevent="executeDelete"
        >
          <Loader2 v-if="deleting" class="h-4 w-4 animate-spin" />
          Supprimer
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
