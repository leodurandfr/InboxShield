<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { TrendingUp, Mail, Clock, BarChart3, Users, RefreshCw, RotateCcw, FlaskConical, Loader2, AlertTriangle, Settings, CircleStop, Play } from 'lucide-vue-next'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmailTable from '@/components/emails/EmailTable.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { usePolling } from '@/composables/usePolling'
import { onWsEvent } from '@/composables/useWebSocket'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

const router = useRouter()
const dashboard = useDashboardStore()

async function handlePollAll() {
  const res = await dashboard.pollAll()
  if (res) {
    const count = res.total_new_emails ?? 0
    if (res.llm_warning) {
      toast.warning(res.llm_warning)
    }
    if (count > 0) {
      toast.success(`${count} nouveau${count > 1 ? 'x' : ''} email${count > 1 ? 's' : ''} récupéré${count > 1 ? 's' : ''}`)
    } else {
      toast.info('Aucun nouvel email')
    }
  }
}

async function handleReanalyzeAll() {
  const res = await dashboard.reanalyzeAll()
  if (res) {
    if (res.llm_warning) {
      toast.warning(res.llm_warning)
    }
    const count = res.total_fetched ?? 0
    if (count > 0) {
      toast.success(`${count} email${count > 1 ? 's' : ''} récupéré${count > 1 ? 's' : ''} et en cours d'analyse`)
    } else {
      toast.info('Aucun email trouvé')
    }
  }
}

async function handleCancelAnalysis() {
  const res = await dashboard.cancelAnalysis()
  if (res) {
    const count = res.cancelled ?? 0
    if (count > 0) {
      toast.success(`Analyse arrêtée (${count} tâche${count > 1 ? 's' : ''} annulée${count > 1 ? 's' : ''})`)
    } else {
      toast.info('Aucune analyse en cours')
    }
  }
}

async function handleResumeClassification() {
  const res = await dashboard.resumeClassification()
  if (res) {
    const count = res.total_queued ?? 0
    if (count > 0) {
      toast.success(`Classification reprise pour ${count} email${count > 1 ? 's' : ''}`)
    } else {
      toast.info('Aucun email en attente')
    }
  }
}

// Test email
const testEmailOpen = ref(false)
const testEmailSending = ref(false)
const testEmailForm = ref({
  from_address: 'test@example.com',
  from_name: 'Test Sender',
  subject: 'Test email',
  body: 'This is a test email for classification debugging.',
})

async function handleCreateTestEmail() {
  testEmailSending.value = true
  try {
    const res = await dashboard.createTestEmail(testEmailForm.value)
    if (res) {
      const cat = res.classification?.category ?? 'inconnu'
      const conf = res.classification?.confidence
        ? `${Math.round(res.classification.confidence * 100)}%`
        : '?'
      toast.success(`Email test classifié : ${cat} (${conf})`)
      testEmailOpen.value = false
    }
  } finally {
    testEmailSending.value = false
  }
}

// Fallback polling (longer interval when WS is connected)
usePolling(() => dashboard.fetchAll(), 60_000)

// Real-time updates via WebSocket
onWsEvent('poll_complete', () => dashboard.fetchAll())
onWsEvent('classification_progress', (data) => {
  dashboard.updateClassificationProgress(data.processed as number, data.total as number)
})
onWsEvent('classification_complete', () => {
  dashboard.setClassificationComplete()
  dashboard.fetchAll()
})
onWsEvent('classification_cancelled', (data) => {
  dashboard.setClassificationCancelled(data.remaining as number)
  dashboard.fetchAll()
})
onWsEvent('email_classifying', (data) => {
  dashboard.markEmailClassifying(data.email_id as string, {
    from_name: data.from_name as string | undefined,
    from_address: data.from_address as string | undefined,
    subject: data.subject as string | undefined,
    date: data.date as string | undefined,
  })
})
onWsEvent('email_classified', (data) => {
  // Local update: remove from pending, no API hammering
  dashboard.markEmailClassified(data.email_id as string)
  // Only refresh stats + recent (lightweight) — pending list is already updated locally
  dashboard.fetchStats()
  dashboard.fetchRecentEmails()
})

// LLM status message
const llmStatusMessage = computed(() => {
  const status = dashboard.stats?.llm_status
  if (!status) return ''
  if (!status.configured) return 'Aucun provider LLM selectionne.'
  if (status.error) return status.error
  return 'LLM non disponible.'
})
</script>

<template>
  <PageHeader title="Dashboard" description="Vue d'ensemble de votre boîte mail">
    <div class="flex gap-2">
      <Button
        variant="outline"
        size="sm"
        :disabled="dashboard.polling || dashboard.reanalyzing"
        @click="handlePollAll()"
      >
        <RefreshCw :class="['size-4', { 'animate-spin': dashboard.polling }]" />
        {{ dashboard.polling ? 'Analyse en cours…' : 'Analyser les nouveaux mails' }}
      </Button>
      <AlertDialog>
        <AlertDialogTrigger as-child>
          <Button
            variant="outline"
            size="sm"
            :disabled="dashboard.polling || dashboard.reanalyzing"
          >
            <RotateCcw :class="['size-4', { 'animate-spin': dashboard.reanalyzing }]" />
            {{ dashboard.reanalyzing ? 'Réanalyse en cours…' : 'Tout réanalyser' }}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Tout réanalyser ?</AlertDialogTitle>
            <AlertDialogDescription>
              Tous les emails et classifications seront supprimés, puis les emails seront re-récupérés depuis le serveur IMAP
              à partir de la date configurée dans les paramètres. Cette opération peut prendre du temps.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction @click="handleReanalyzeAll()">Confirmer</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <!-- Stop button: only visible when classification is running -->
      <Button
        v-if="dashboard.classifying"
        variant="destructive"
        size="sm"
        :disabled="dashboard.cancelling"
        @click="handleCancelAnalysis()"
      >
        <CircleStop class="size-4" />
        {{ dashboard.cancelling ? 'Arrêt…' : 'Arrêter' }}
      </Button>
      <!-- Resume button: visible when cancelled with pending emails -->
      <Button
        v-if="!dashboard.classifying && dashboard.pendingResumeCount > 0"
        variant="outline"
        size="sm"
        :disabled="dashboard.resuming"
        @click="handleResumeClassification()"
      >
        <Play v-if="!dashboard.resuming" class="size-4" />
        <Loader2 v-else class="size-4 animate-spin" />
        {{ dashboard.resuming ? 'Reprise…' : `Reprendre (${dashboard.pendingResumeCount})` }}
      </Button>
      <Dialog v-model:open="testEmailOpen">
        <DialogTrigger as-child>
          <Button variant="outline" size="sm">
            <FlaskConical class="size-4" />
            Email test
          </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Créer un email test</DialogTitle>
            <DialogDescription>
              Injecte un faux email et le classifie immédiatement via le LLM.
            </DialogDescription>
          </DialogHeader>
          <div class="grid gap-4 py-4">
            <div class="grid gap-2">
              <Label for="test-from">Expéditeur</Label>
              <Input id="test-from" v-model="testEmailForm.from_address" placeholder="test@example.com" />
            </div>
            <div class="grid gap-2">
              <Label for="test-from-name">Nom</Label>
              <Input id="test-from-name" v-model="testEmailForm.from_name" placeholder="Test Sender" />
            </div>
            <div class="grid gap-2">
              <Label for="test-subject">Sujet</Label>
              <Input id="test-subject" v-model="testEmailForm.subject" placeholder="Sujet de l'email" />
            </div>
            <div class="grid gap-2">
              <Label for="test-body">Contenu</Label>
              <Textarea id="test-body" v-model="testEmailForm.body" placeholder="Corps de l'email…" rows="4" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" @click="testEmailOpen = false">Annuler</Button>
            <Button :disabled="testEmailSending" @click="handleCreateTestEmail()">
              <Loader2 v-if="testEmailSending" class="size-4 animate-spin" />
              <FlaskConical v-else class="size-4" />
              {{ testEmailSending ? 'Classification…' : 'Envoyer et classifier' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  </PageHeader>

  <!-- LLM Status Alert -->
  <Alert
    v-if="dashboard.stats?.llm_status && !dashboard.stats.llm_status.available"
    class="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200"
  >
    <AlertTriangle class="size-4 text-amber-600 dark:text-amber-400" />
    <AlertTitle class="font-medium">LLM non configure</AlertTitle>
    <AlertDescription class="text-amber-800 dark:text-amber-300">
      {{ llmStatusMessage }}
      <router-link to="/settings" class="ml-1 inline-flex items-center gap-1 font-medium underline underline-offset-4 hover:text-amber-900 dark:hover:text-amber-100">
        <Settings class="size-3" />
        Configurer dans les Parametres
      </router-link>
    </AlertDescription>
  </Alert>

  <!-- Section Cards -->
  <div class="grid grid-cols-1 gap-4 *:data-[slot=card]:shadow-xs @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
    <Card class="@container/card">
      <CardHeader>
        <CardDescription>Emails aujourd'hui</CardDescription>
        <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
          {{ dashboard.stats?.emails_processed_today ?? '–' }}
        </CardTitle>
        <CardAction>
          <Badge variant="outline">
            <TrendingUp />
            actif
          </Badge>
        </CardAction>
      </CardHeader>
      <CardFooter class="flex-col items-start gap-1.5 text-sm">
        <div class="line-clamp-1 flex gap-2 font-medium">
          Emails traités <Mail class="size-4" />
        </div>
        <div class="text-muted-foreground">
          Depuis minuit
        </div>
      </CardFooter>
    </Card>

    <Card class="@container/card">
      <CardHeader>
        <CardDescription>En attente de review</CardDescription>
        <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
          {{ dashboard.stats?.pending_review ?? '–' }}
        </CardTitle>
        <CardAction>
          <Badge variant="outline">
            <Clock class="size-3" />
            en attente
          </Badge>
        </CardAction>
      </CardHeader>
      <CardFooter class="flex-col items-start gap-1.5 text-sm">
        <div class="line-clamp-1 flex gap-2 font-medium">
          À vérifier manuellement <Clock class="size-4" />
        </div>
        <div class="text-muted-foreground">
          Confiance insuffisante
        </div>
      </CardFooter>
    </Card>

    <Card class="@container/card">
      <CardHeader>
        <CardDescription>Classifications</CardDescription>
        <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
          {{ dashboard.stats?.classifications_today ?? '–' }}
        </CardTitle>
        <CardAction>
          <Badge variant="outline">
            <TrendingUp />
            +12.5%
          </Badge>
        </CardAction>
      </CardHeader>
      <CardFooter class="flex-col items-start gap-1.5 text-sm">
        <div class="line-clamp-1 flex gap-2 font-medium">
          Classifications AI <BarChart3 class="size-4" />
        </div>
        <div class="text-muted-foreground">
          Depuis le dernier polling
        </div>
      </CardFooter>
    </Card>

    <Card class="@container/card">
      <CardHeader>
        <CardDescription>Comptes actifs</CardDescription>
        <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
          {{ dashboard.stats?.active_accounts ?? '–' }}
        </CardTitle>
        <CardAction>
          <Badge variant="outline">
            <TrendingUp />
            connectés
          </Badge>
        </CardAction>
      </CardHeader>
      <CardFooter class="flex-col items-start gap-1.5 text-sm">
        <div class="line-clamp-1 flex gap-2 font-medium">
          Comptes IMAP <Users class="size-4" />
        </div>
        <div class="text-muted-foreground">
          Surveillance active
        </div>
      </CardFooter>
    </Card>
  </div>

  <!-- Pending Emails (only shown if there are pending emails) -->
  <Card v-if="dashboard.pendingTotal > 0 || dashboard.classificationProgress" class="mt-6">
    <CardHeader>
      <CardTitle class="flex items-center gap-2">
        <Loader2 class="size-4 animate-spin text-muted-foreground" />
        En cours d'analyse
      </CardTitle>
      <CardDescription>
        <template v-if="dashboard.classificationProgress">
          Classification : {{ dashboard.classificationProgress.processed }}/{{ dashboard.classificationProgress.total }} traités
        </template>
        <template v-else>
          {{ dashboard.pendingTotal }} email(s) en attente de classification
        </template>
      </CardDescription>
      <!-- Progress bar -->
      <div v-if="dashboard.classificationProgress" class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          class="h-full rounded-full bg-primary transition-all duration-500"
          :style="{ width: `${Math.round((dashboard.classificationProgress.processed / dashboard.classificationProgress.total) * 100)}%` }"
        />
      </div>
    </CardHeader>
    <CardContent class="px-0 pb-0">
      <EmailTable
        :emails="dashboard.pendingEmails"
        :loading="false"
        :skeleton-rows="3"
        @select="(id) => router.push({ name: 'emails', query: { detail: id } })"
      />
    </CardContent>
  </Card>

  <!-- Recent Emails -->
  <Card class="mt-6">
    <CardHeader>
      <CardTitle>Emails récents</CardTitle>
      <CardDescription>Derniers emails analysés par InboxShield</CardDescription>
    </CardHeader>
    <CardContent class="px-0 pb-0">
      <EmailTable
        :emails="dashboard.recentEmails"
        :loading="dashboard.loading"
        :skeleton-rows="5"
        empty-title="Aucun email analysé"
        empty-description="Ajoutez un compte IMAP dans les Paramètres pour commencer."
        @select="(id) => router.push({ name: 'emails', query: { detail: id } })"
      />
    </CardContent>
  </Card>
</template>
