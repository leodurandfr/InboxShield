<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Server,
  Brain,
  Plus,
  Trash2,
  TestTube,
  Loader2,
  Check,
  Download,
  RefreshCw,
  X,
  CalendarIcon,
  SlidersHorizontal,
  Key,
  Eye,
  EyeOff,
  Rocket,
} from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import OllamaStatusCard from '@/components/settings/OllamaStatusCard.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useSettingsStore } from '@/stores/settings'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from '@/components/ui/table'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { CalendarDate, type DateValue } from '@internationalized/date'
import { format, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'

const store = useSettingsStore()

// Local form state
const llmTesting = ref(false)
const saving = ref(false)
const apiKeyInput = ref('')
const showApiKey = ref(false)

const isCloudProvider = computed(() => {
  const p = store.settings?.llm_provider
  return p === 'anthropic' || p === 'openai' || p === 'mistral'
})

// Onboarding banner : premier lancement avec Ollama local mais daemon absent/arrêté.
const showOnboardingBanner = computed(() => {
  if (store.settings?.llm_provider !== 'ollama') return false
  if (store.accounts.length > 0) return false
  const status = store.ollamaStatus?.service_status
  return status === 'not-installed' || status === 'stopped'
})

const onboardingBannerIsStopped = computed(
  () => store.ollamaStatus?.service_status === 'stopped',
)

// Default models per cloud provider
const defaultModels: Record<string, string> = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  mistral: 'mistral-large-latest',
}

// Refresh models list when provider changes
watch(() => store.settings?.llm_provider, (newVal, oldVal) => {
  if (newVal && oldVal && newVal !== oldVal && store.settings) {
    // Reset API key input when switching providers
    apiKeyInput.value = ''
    showApiKey.value = false
    // Clear stale models immediately so old list doesn't show
    store.llmModels = []
    // Set a sensible default model for the new provider
    const defaultModel = defaultModels[newVal as keyof typeof defaultModels]
    if (defaultModel) {
      store.settings.llm_model = defaultModel
    } else {
      store.settings.llm_model = ''
    }
    store.fetchLLMModels(newVal)
  }
})

// Date picker for initial fetch since
const fetchSinceDate = computed<DateValue | undefined>({
  get() {
    const iso = store.settings?.initial_fetch_since
    if (!iso) return undefined
    const d = parseISO(iso)
    return new CalendarDate(d.getFullYear(), d.getMonth() + 1, d.getDate())
  },
  set(val: DateValue | undefined) {
    if (!store.settings) return
    if (!val) {
      store.settings.initial_fetch_since = null
      return
    }
    // CalendarDate months are 1-indexed, format to ISO
    const jsDate = new Date(val.year, val.month - 1, val.day)
    store.settings.initial_fetch_since = format(jsDate, 'yyyy-MM-dd')
  },
})

const fetchSinceDateLabel = computed(() => {
  const iso = store.settings?.initial_fetch_since
  if (!iso) return null
  return format(parseISO(iso), 'd MMMM yyyy', { locale: fr })
})

// Account creation form
const showAddAccount = ref(false)
const newAccount = ref({ name: '', email: '', password: '', imap_host: '', imap_port: 993 })
const addingAccount = ref(false)
const testingConnection = ref(false)

// LLM model pull
const pullModelName = ref('')
const pulling = ref(false)
const pullStatus = ref<string | null>(null)
const pullProgress = ref(0)
const pullId = ref<string | null>(null)
let pollInterval: ReturnType<typeof setInterval> | null = null

// Recommended models for classification
const recommendedModels = [
  { name: 'qwen2.5:7b', desc: 'Rapide, bon pour la classification (4.7 GB)' },
  { name: 'qwen2.5:14b', desc: 'Plus précis, plus lent (9.0 GB)' },
  { name: 'llama3.1:8b', desc: 'Meta Llama, polyvalent (4.7 GB)' },
  { name: 'mistral:7b', desc: 'Mistral, bon en français (4.1 GB)' },
  { name: 'gemma2:9b', desc: 'Google Gemma, compact (5.4 GB)' },
]

onMounted(() => {
  store.fetchAll()
  store.fetchLLMModels()
  store.fetchOllamaStatus()
})

async function saveSettings() {
  if (!store.settings) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = { ...store.settings }
    // Include API key only if user entered a new one
    if (apiKeyInput.value) {
      payload.llm_api_key = apiKeyInput.value
    }
    await store.updateSettings(payload)
    if (apiKeyInput.value) {
      apiKeyInput.value = ''
      showApiKey.value = false
    }
    toast.success('Paramètres sauvegardés')
    // Refresh models after saving (API key may have changed)
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
      toast.success(`LLM connecté (${result.latency_ms}ms)`)
    } else {
      toast.error(result.error || 'Connexion LLM échouée')
    }
  } catch {
    toast.error('Connexion LLM échouée')
  } finally {
    llmTesting.value = false
  }
}

async function testConnection() {
  testingConnection.value = true
  try {
    const result = await api.post<{ success: boolean; error?: string }>('/accounts/test-connection', {
      email: newAccount.value.email,
      password: newAccount.value.password,
      imap_host: newAccount.value.imap_host || undefined,
      imap_port: newAccount.value.imap_port || undefined,
    })
    if (result.success) {
      toast.success('Connexion IMAP réussie')
    } else {
      toast.error(result.error || 'Connexion IMAP échouée')
    }
  } catch {
    toast.error('Connexion IMAP échouée')
  } finally {
    testingConnection.value = false
  }
}

async function addAccount() {
  addingAccount.value = true
  try {
    await api.post('/accounts', {
      name: newAccount.value.name,
      email: newAccount.value.email,
      password: newAccount.value.password,
      imap_host: newAccount.value.imap_host || undefined,
      imap_port: newAccount.value.imap_port || undefined,
    })
    showAddAccount.value = false
    newAccount.value = { name: '', email: '', password: '', imap_host: '', imap_port: 993 }
    toast.success('Compte ajouté avec succès')
    await store.fetchAccounts()
  } catch {
    toast.error('Erreur lors de l\'ajout du compte')
  } finally {
    addingAccount.value = false
  }
}

async function deleteAccount(id: string) {
  await api.delete(`/accounts/${id}`)
  toast.success('Compte supprimé')
  await store.fetchAccounts()
}

async function pullModel(modelName: string) {
  pulling.value = true
  pullProgress.value = 0
  pullStatus.value = `Démarrage du téléchargement de ${modelName}...`
  try {
    const res = await api.post<{ pull_id: string }>('/settings/llm/pull', { model: modelName })
    pullId.value = res.pull_id
    startPollingPull()
  } catch {
    pullStatus.value = null
    pulling.value = false
    toast.error(`Impossible de télécharger ${modelName}`)
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
          : `Téléchargement de ${res.model}... ${res.progress}%`

      if (res.status === 'done' || res.status === 'cancelled' || res.status.startsWith('error')) {
        stopPollingPull()
        pulling.value = false
        pullId.value = null
        if (res.status === 'done') {
          toast.success(`${res.model} téléchargé avec succès`)
          await store.fetchLLMModels()
        } else if (res.status.startsWith('error')) {
          toast.error(`Erreur: ${res.status}`)
        }
      }
    } catch {
      stopPollingPull()
      pulling.value = false
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
    toast.info('Téléchargement annulé')
  } catch {
    toast.error('Erreur lors de l\'annulation')
  } finally {
    stopPollingPull()
    pulling.value = false
    pullId.value = null
    pullProgress.value = 0
    pullStatus.value = null
  }
}

onUnmounted(() => {
  stopPollingPull()
})
</script>

<template>
  <PageHeader title="Paramètres" description="Configuration des comptes IMAP et du LLM" />

  <div class="space-y-6">
    <!-- Onboarding banner : premier lancement, provider Ollama choisi mais daemon absent/arrêté -->
    <Alert v-if="showOnboardingBanner" class="border-primary/40 bg-primary/5">
      <Rocket class="h-4 w-4 text-primary" />
      <AlertTitle>
        {{ onboardingBannerIsStopped ? 'Démarre Ollama pour commencer' : 'Installe Ollama pour commencer' }}
      </AlertTitle>
      <AlertDescription>
        <p class="mb-2">
          {{
            onboardingBannerIsStopped
              ? 'Le daemon Ollama est installé mais arrêté. Relance-le avec la commande ci-dessous, puis ajoute un compte IMAP.'
              : 'InboxShield est configuré pour utiliser Ollama en local. Exécute le script d\'installation depuis la racine du projet, puis ajoute un compte IMAP.'
          }}
        </p>
        <pre class="rounded bg-muted px-3 py-2 text-xs font-mono">{{
          onboardingBannerIsStopped
            ? 'brew services start ollama    # macOS\nsystemctl start ollama         # Linux'
            : './scripts/install-ollama.sh'
        }}</pre>
        <p class="mt-2 text-xs text-muted-foreground">
          Pas envie d'installer un LLM local ? Choisis un provider cloud (Claude, OpenAI, Mistral) ci-dessous et renseigne une clé API.
        </p>
      </AlertDescription>
    </Alert>

    <!-- IMAP Accounts -->
    <Card>
      <CardHeader class="flex flex-row items-center justify-between space-y-0">
        <div class="flex items-center gap-3">
          <div class="rounded-md bg-primary/10 p-2">
            <Server class="h-5 w-5 text-primary" />
          </div>
          <div>
            <CardTitle>Comptes IMAP</CardTitle>
            <CardDescription>Gérez vos comptes email connectés</CardDescription>
          </div>
        </div>
        <Button size="sm" @click="showAddAccount = !showAddAccount">
          <Plus class="h-4 w-4" />
          Ajouter
        </Button>
      </CardHeader>
      <CardContent>
        <!-- Add account form -->
        <Card v-if="showAddAccount" class="mb-4 bg-muted/30">
          <CardContent class="pt-6">
            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-2">
                <Label for="acct-name">Nom du compte</Label>
                <Input id="acct-name" v-model="newAccount.name" placeholder="Mon email" />
              </div>
              <div class="space-y-2">
                <Label for="acct-email">Email</Label>
                <Input id="acct-email" v-model="newAccount.email" type="email" placeholder="you@example.com" />
              </div>
              <div class="space-y-2">
                <Label for="acct-password">Mot de passe / App password</Label>
                <Input id="acct-password" v-model="newAccount.password" type="password" />
              </div>
              <div class="space-y-2">
                <Label for="acct-host">Serveur IMAP (auto-détecté si vide)</Label>
                <Input id="acct-host" v-model="newAccount.imap_host" placeholder="imap.example.com" />
              </div>
            </div>
            <div class="mt-4 flex items-center gap-2">
              <Button variant="outline" size="sm" :disabled="testingConnection" @click="testConnection">
                <Loader2 v-if="testingConnection" class="h-4 w-4 animate-spin" />
                <TestTube v-else class="h-4 w-4" />
                Tester
              </Button>
              <Button size="sm" :disabled="addingAccount" @click="addAccount">
                <Loader2 v-if="addingAccount" class="h-4 w-4 animate-spin" />
                {{ addingAccount ? 'Ajout...' : 'Ajouter le compte' }}
              </Button>
              <Button variant="ghost" size="sm" @click="showAddAccount = false">
                Annuler
              </Button>
            </div>
          </CardContent>
        </Card>

        <!-- Account list -->
        <div v-if="store.accounts.length === 0 && !showAddAccount" class="flex flex-col items-center justify-center py-8 text-center">
          <Server class="mb-3 h-10 w-10 text-muted-foreground/50" />
          <p class="text-sm font-medium">Aucun compte configuré</p>
          <p class="mt-1 text-xs text-muted-foreground">Cliquez sur « Ajouter » pour connecter un compte email.</p>
        </div>
        <Table v-else-if="store.accounts.length > 0">
          <TableBody>
            <TableRow v-for="account in store.accounts" :key="account.id">
              <TableCell class="w-4 pl-4 pr-0">
                <div class="h-2 w-2 rounded-full" :class="account.last_poll_error ? 'bg-destructive' : 'bg-emerald-500'" />
              </TableCell>
              <TableCell>
                <p class="text-sm font-medium">{{ account.name }}</p>
                <p class="text-xs text-muted-foreground">{{ account.email }}</p>
              </TableCell>
              <TableCell class="text-right">
                <Badge variant="outline" class="text-xs">{{ account.provider || 'custom' }}</Badge>
              </TableCell>
              <TableCell class="w-10 pr-4">
                <AlertDialog>
                  <AlertDialogTrigger as-child>
                    <Button variant="ghost" size="icon-sm" class="text-destructive hover:text-destructive">
                      <Trash2 class="h-4 w-4" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Supprimer ce compte ?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Le compte « {{ account.name }} » et toutes ses données associées seront définitivement supprimés.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Annuler</AlertDialogCancel>
                      <AlertDialogAction
                        class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        @click="deleteAccount(account.id)"
                      >
                        Supprimer
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Classification settings -->
    <Card v-if="store.settings">
      <CardHeader>
        <div class="flex items-center gap-3">
          <div class="rounded-md bg-primary/10 p-2">
            <SlidersHorizontal class="h-5 w-5 text-primary" />
          </div>
          <div>
            <CardTitle>Classification</CardTitle>
            <CardDescription>Paramètres d'analyse et de tri des emails</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div class="space-y-2">
          <Label>Analyser les emails à partir du</Label>
          <p class="text-xs text-muted-foreground">
            Lors du premier scan d'un compte, InboxShield récupèrera tous les emails depuis cette date. Par défaut : 1er du mois en cours.
          </p>
          <Popover>
            <PopoverTrigger as-child>
              <Button
                variant="outline"
                :class="[
                  'w-[280px] justify-start text-left font-normal',
                  !store.settings.initial_fetch_since && 'text-muted-foreground',
                ]"
              >
                <CalendarIcon class="mr-2 h-4 w-4" />
                {{ fetchSinceDateLabel ?? '1er du mois en cours (par défaut)' }}
              </Button>
            </PopoverTrigger>
            <PopoverContent class="w-auto p-0">
              <Calendar v-model="fetchSinceDate" locale="fr" layout="month-and-year" />
              <div v-if="store.settings.initial_fetch_since" class="border-t px-3 py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  class="w-full text-xs"
                  @click="store.settings.initial_fetch_since = null"
                >
                  Réinitialiser (1er du mois)
                </Button>
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </CardContent>
    </Card>

    <!-- Ollama supervision (visible uniquement si provider = ollama) -->
    <OllamaStatusCard v-if="store.settings?.llm_provider === 'ollama'" />

    <!-- LLM Configuration -->
    <template v-if="store.settings">
      <Card>
        <CardHeader>
          <div class="flex items-center gap-3">
            <div class="rounded-md bg-primary/10 p-2">
              <Brain class="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle>Configuration LLM</CardTitle>
              <CardDescription>Paramétrez le modèle d'intelligence artificielle</CardDescription>
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
              <Label for="llm-model">Modèle</Label>
              <div class="flex gap-2">
                <!-- Ollama: always show dropdown of local models -->
                <template v-if="!isCloudProvider">
                  <Select v-if="store.llmModels.length > 0" v-model="store.settings.llm_model" class="flex-1">
                    <SelectTrigger id="llm-model">
                      <SelectValue placeholder="Choisir un modèle local" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem v-for="m in store.llmModels.filter(m => m.name)" :key="m.name" :value="m.name">
                        {{ m.name }}<template v-if="m.size"> ({{ m.size }})</template>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Input v-else v-model="store.settings.llm_model" class="flex-1" placeholder="qwen2.5:7b" />
                </template>
                <!-- Cloud providers: show provider model list if available, otherwise text input -->
                <template v-else>
                  <Select v-if="store.llmModels.length > 0" v-model="store.settings.llm_model" class="flex-1">
                    <SelectTrigger id="llm-model">
                      <SelectValue placeholder="Choisir un modèle" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem v-for="m in store.llmModels.filter(m => m.name)" :key="m.name" :value="m.name">
                        {{ m.name }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Input v-else v-model="store.settings.llm_model" class="flex-1" :placeholder="defaultModels[store.settings.llm_provider as keyof typeof defaultModels] ?? 'nom-du-modèle'" />
                </template>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button variant="outline" size="icon" @click="store.fetchLLMModels()">
                        <RefreshCw class="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Rafraîchir les modèles</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </div>

            <!-- API Key (cloud providers only) -->
            <div v-if="isCloudProvider" class="space-y-2 sm:col-span-2">
              <Label for="llm-api-key">
                Clé API
                <Badge v-if="store.settings.has_api_key" variant="outline" class="ml-2 text-xs text-emerald-600 dark:text-emerald-400">
                  <Check class="mr-1 h-3 w-3" />
                  configurée
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
                    :placeholder="store.settings.has_api_key ? '••••••••••••••••••••  (laisser vide pour garder la clé actuelle)' : 'sk-...'"
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
                La clé est chiffrée avant stockage et n'est jamais exposée en clair.
              </p>
            </div>

            <!-- Base URL (OpenAI compatible) -->
            <div v-if="store.settings.llm_provider === 'openai'" class="space-y-2 sm:col-span-2">
              <Label for="llm-base-url">URL personnalisée (optionnel)</Label>
              <Input
                id="llm-base-url"
                :model-value="store.settings.llm_base_url ?? ''"
                placeholder="https://api.openai.com/v1 (par défaut)"
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
                Mode automatique (exécuter les actions sans validation manuelle)
              </Label>
            </div>
          </div>

          <!-- Download models (Ollama only) -->
          <Card v-if="store.settings.llm_provider === 'ollama'" class="mt-6 bg-muted/30">
            <CardContent class="pt-6">
              <h3 class="mb-3 flex items-center gap-2 text-sm font-medium">
                <Download class="h-4 w-4" />
                Télécharger un modèle
              </h3>
              <div class="flex flex-wrap gap-2">
                <TooltipProvider>
                  <Tooltip v-for="rec in recommendedModels" :key="rec.name">
                    <TooltipTrigger as-child>
                      <Button
                        :variant="store.llmModels.some(m => m.name === rec.name) ? 'outline' : 'secondary'"
                        size="sm"
                        :disabled="pulling"
                        @click="pullModel(rec.name)"
                      >
                        <Check v-if="store.llmModels.some(m => m.name === rec.name)" class="h-3 w-3 text-emerald-500" />
                        {{ rec.name }}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{{ rec.desc }}</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <div class="mt-3 flex gap-2">
                <Input v-model="pullModelName" class="flex-1" placeholder="Nom du modèle (ex: phi3:mini)" />
                <Button size="sm" :disabled="pulling || !pullModelName" @click="pullModel(pullModelName)">
                  <Loader2 v-if="pulling" class="h-4 w-4 animate-spin" />
                  <Download v-else class="h-4 w-4" />
                  Télécharger
                </Button>
              </div>
              <div v-if="pulling" class="mt-3 space-y-1">
                <div class="flex items-center gap-2">
                  <Progress :model-value="pullProgress" class="h-2 flex-1" />
                  <span class="shrink-0 text-xs font-mono text-muted-foreground">{{ pullProgress }}%</span>
                  <Button variant="destructive" size="icon-sm" @click="cancelPull" title="Annuler">
                    <X class="h-4 w-4" />
                  </Button>
                </div>
                <p v-if="pullStatus" class="text-xs text-muted-foreground">{{ pullStatus }}</p>
              </div>
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
    </template>

    <!-- Loading skeleton for settings -->
    <Card v-else>
      <CardHeader>
        <div class="flex items-center gap-3">
          <Skeleton class="h-9 w-9 rounded-md" />
          <div class="space-y-2">
            <Skeleton class="h-5 w-40" />
            <Skeleton class="h-4 w-64" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2">
            <Skeleton class="h-4 w-16" />
            <Skeleton class="h-9 w-full" />
          </div>
          <div class="space-y-2">
            <Skeleton class="h-4 w-16" />
            <Skeleton class="h-9 w-full" />
          </div>
          <div class="space-y-2">
            <Skeleton class="h-4 w-24" />
            <Skeleton class="h-9 w-full" />
          </div>
          <div class="space-y-2">
            <Skeleton class="h-4 w-24" />
            <Skeleton class="h-9 w-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
