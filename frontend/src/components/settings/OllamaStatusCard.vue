<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { toast } from 'vue-sonner'
import {
  Activity,
  AlertTriangle,
  Cpu,
  HardDrive,
  Loader2,
  PowerOff,
  RefreshCw,
  Terminal,
  XCircle,
} from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

const store = useSettingsStore()

const refreshing = ref(false)
const unloading = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const status = computed(() => store.ollamaStatus)

const serviceStatus = computed(() => status.value?.service_status ?? null)

const installMethodLabel = computed(() => {
  const m = status.value?.install_method
  if (!m || m === 'unknown') return 'Inconnu'
  if (m === 'homebrew') return 'Homebrew'
  if (m === 'systemd') return 'systemd'
  if (m === 'app') return 'App desktop'
  if (m === 'docker') return 'Docker (container)'
  return m
})

const totalDiskGb = computed(() => {
  const bytes = status.value?.total_disk_bytes ?? 0
  return (bytes / 1024 ** 3).toFixed(1)
})

const totalLoadedRamBytes = computed(() =>
  (status.value?.loaded_models ?? []).reduce((sum, m) => sum + (m.size_bytes ?? 0), 0),
)

const totalLoadedVramBytes = computed(() =>
  (status.value?.loaded_models ?? []).reduce((sum, m) => sum + (m.size_vram_bytes ?? 0), 0),
)

function formatSizeGb(bytes: number): string {
  return (bytes / 1024 ** 3).toFixed(1)
}

function isLoaded(name: string): boolean {
  return !!status.value?.loaded_models.some((m) => m.name === name)
}

function loadedModel(name: string) {
  return status.value?.loaded_models.find((m) => m.name === name)
}

async function refresh() {
  refreshing.value = true
  try {
    await store.fetchOllamaStatus()
  } finally {
    refreshing.value = false
  }
}

async function unload(name: string) {
  unloading.value = name
  try {
    await store.unloadOllamaModel(name)
    toast.success(`${name} déchargé de la RAM`)
  } catch {
    toast.error(`Impossible de décharger ${name}`)
  } finally {
    unloading.value = null
  }
}

onMounted(() => {
  refresh()
  pollTimer = setInterval(refresh, 10_000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <Card>
    <CardHeader class="flex flex-row items-center justify-between space-y-0">
      <div class="flex items-center gap-3">
        <div class="rounded-md bg-primary/10 p-2">
          <Cpu class="h-5 w-5 text-primary" />
        </div>
        <div>
          <CardTitle class="flex items-center gap-2">
            Ollama
            <Badge
              v-if="serviceStatus === 'running'"
              class="bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
            >
              En cours
            </Badge>
            <Badge
              v-else-if="serviceStatus === 'stopped'"
              class="bg-amber-500/15 text-amber-600 hover:bg-amber-500/20 dark:text-amber-400"
            >
              Arrêté
            </Badge>
            <Badge
              v-else-if="serviceStatus === 'not-installed'"
              variant="destructive"
            >
              Non installé
            </Badge>
          </CardTitle>
          <CardDescription>
            Supervision du daemon local — modèles chargés en RAM et disque
          </CardDescription>
        </div>
      </div>
      <Button variant="outline" size="icon" :disabled="refreshing" @click="refresh">
        <Loader2 v-if="refreshing" class="h-4 w-4 animate-spin" />
        <RefreshCw v-else class="h-4 w-4" />
      </Button>
    </CardHeader>

    <CardContent class="space-y-4">
      <div v-if="!status" class="space-y-2">
        <Skeleton class="h-4 w-48" />
        <Skeleton class="h-4 w-64" />
      </div>

      <!-- Not installed -->
      <Alert v-else-if="serviceStatus === 'not-installed'" variant="destructive">
        <XCircle class="h-4 w-4" />
        <AlertTitle>Ollama n'est pas installé</AlertTitle>
        <AlertDescription>
          <p>Exécute le script d'installation depuis la racine du projet :</p>
          <pre class="mt-2 rounded bg-muted px-3 py-2 text-xs font-mono">./scripts/install-ollama.sh</pre>
        </AlertDescription>
      </Alert>

      <!-- Stopped -->
      <Alert v-else-if="serviceStatus === 'stopped'">
        <AlertTriangle class="h-4 w-4" />
        <AlertTitle>Ollama est installé mais arrêté</AlertTitle>
        <AlertDescription>
          <p>Relance le service avec :</p>
          <pre class="mt-2 rounded bg-muted px-3 py-2 text-xs font-mono">brew services start ollama  <span class="text-muted-foreground"># macOS</span>
systemctl start ollama      <span class="text-muted-foreground"># Linux</span></pre>
        </AlertDescription>
      </Alert>

      <!-- Running -->
      <template v-else-if="serviceStatus === 'running'">
        <!-- Meta info -->
        <div class="grid gap-3 sm:grid-cols-3">
          <div class="flex items-start gap-2 rounded-md border bg-muted/30 p-3">
            <Terminal class="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div>
              <p class="text-xs text-muted-foreground">Installation</p>
              <p class="text-sm font-medium">{{ installMethodLabel }}</p>
              <p v-if="status.binary_path" class="mt-0.5 truncate text-xs font-mono text-muted-foreground">{{ status.binary_path }}</p>
            </div>
          </div>
          <div class="flex items-start gap-2 rounded-md border bg-muted/30 p-3">
            <HardDrive class="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div>
              <p class="text-xs text-muted-foreground">Modèles installés</p>
              <p class="text-sm font-medium">
                {{ status.installed_models.length }}
                <span class="font-normal text-muted-foreground">({{ totalDiskGb }} Go)</span>
              </p>
            </div>
          </div>
          <div class="flex items-start gap-2 rounded-md border bg-muted/30 p-3">
            <Activity class="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div class="min-w-0">
              <p class="text-xs text-muted-foreground">Chargés en RAM</p>
              <p class="text-sm font-medium">
                {{ status.loaded_models.length }}
                <span v-if="status.loaded_models.length > 0" class="font-normal text-muted-foreground">
                  ({{ formatSizeGb(totalLoadedRamBytes) }} Go)
                </span>
              </p>
              <p
                v-if="totalLoadedVramBytes > 0"
                class="mt-0.5 text-xs text-muted-foreground"
              >
                dont {{ formatSizeGb(totalLoadedVramBytes) }} Go GPU
              </p>
            </div>
          </div>
        </div>

        <!-- Installed models list -->
        <div v-if="status.installed_models.length > 0" class="space-y-2">
          <p class="text-xs font-medium text-muted-foreground">Modèles</p>
          <div class="space-y-1.5">
            <div
              v-for="m in status.installed_models"
              :key="String(m.name ?? '')"
              class="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
            >
              <div class="flex min-w-0 items-center gap-2">
                <span class="truncate font-mono">{{ m.name }}</span>
                <Badge
                  v-if="isLoaded(String(m.name ?? ''))"
                  class="bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
                >
                  Chargé
                </Badge>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <span class="text-xs text-muted-foreground">
                  <template v-if="isLoaded(String(m.name ?? ''))">
                    {{ formatSizeGb(loadedModel(String(m.name ?? ''))?.size_bytes ?? 0) }} Go en RAM<template
                      v-if="(loadedModel(String(m.name ?? ''))?.size_vram_bytes ?? 0) > 0"
                    >
                      · {{ formatSizeGb(loadedModel(String(m.name ?? ''))?.size_vram_bytes ?? 0) }} Go GPU
                    </template>
                  </template>
                  <template v-else-if="typeof m.size === 'number'">
                    {{ formatSizeGb(m.size) }} Go
                  </template>
                </span>
                <Button
                  v-if="isLoaded(String(m.name ?? ''))"
                  variant="outline"
                  size="sm"
                  :disabled="unloading === m.name"
                  @click="unload(String(m.name ?? ''))"
                >
                  <Loader2 v-if="unloading === m.name" class="h-3 w-3 animate-spin" />
                  <PowerOff v-else class="h-3 w-3" />
                  Libérer la RAM
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div
          v-else
          class="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground"
        >
          Aucun modèle installé. Télécharge un modèle depuis la section « Configuration LLM ».
        </div>
      </template>
    </CardContent>
  </Card>
</template>
