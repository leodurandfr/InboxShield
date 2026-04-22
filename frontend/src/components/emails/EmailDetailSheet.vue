<script setup lang="ts">
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import DOMPurify from 'dompurify'
import {
  Archive,
  Clock,
  Flag,
  FolderInput,
  Inbox,
  Loader2,
  Mail,
  Paperclip,
  RefreshCw,
  ShieldAlert,
  Star,
  Trash2,
  User,
} from 'lucide-vue-next'
import { useEmailsStore } from '@/stores/emails'
import { CATEGORY_CONFIG } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const store = useEmailsStore()
const reclassifying = ref(false)

function getInitials(name: string | null, email: string): string {
  if (name) {
    return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
  }
  return email.charAt(0).toUpperCase()
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('fr-FR', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatBytes(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function onSheetClose(open: boolean) {
  if (!open) {
    store.closeDetail()
    emit('update:open', false)
  }
}

async function moveEmail(folder: string) {
  if (!store.selectedEmail) return
  await store.moveEmail(store.selectedEmail.id, folder)
  toast.success(`Email déplacé vers ${folder}`)
  emit('update:open', false)
  store.closeDetail()
}

async function toggleFlag() {
  if (!store.selectedEmail) return
  await store.flagEmail(store.selectedEmail.id, !store.selectedEmail.is_flagged)
  toast.success(store.selectedEmail.is_flagged ? 'Email marqué important' : 'Marquage retiré')
}

async function reclassify() {
  if (!store.selectedEmail) return
  reclassifying.value = true
  try {
    await store.reclassifyEmail(store.selectedEmail.id)
    await store.fetchEmailDetail(store.selectedEmail.id)
    toast.success('Email reclassifié')
  } finally {
    reclassifying.value = false
  }
}

const sanitizedHtml = computed(() => {
  const html = store.selectedEmail?.body_html_excerpt
  if (!html) return null
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'b', 'i', 'em', 'strong', 'u', 's', 'br', 'p', 'div', 'span',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'table', 'thead', 'tbody', 'tr', 'td', 'th',
      'blockquote', 'pre', 'code', 'hr', 'img', 'sup', 'sub',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'width', 'height', 'style', 'class', 'target', 'rel'],
    ADD_ATTR: ['target'],
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
  })
})

// Force all links to open in new tab after sanitization
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})
</script>

<template>
  <Sheet :open="open" @update:open="onSheetClose">
    <SheetContent side="right" class="sm:max-w-xl p-0 flex flex-col">
      <SheetHeader class="sr-only">
        <SheetTitle>Détail de l'email</SheetTitle>
        <SheetDescription>Informations détaillées et actions</SheetDescription>
      </SheetHeader>

      <!-- Loading skeleton -->
      <div v-if="store.detailLoading" class="flex-1 space-y-4 p-6">
        <div class="flex items-start gap-3">
          <Skeleton class="h-10 w-10 rounded-full" />
          <div class="flex-1 space-y-2">
            <Skeleton class="h-5 w-48" />
            <Skeleton class="h-3 w-32" />
          </div>
        </div>
        <Skeleton class="h-6 w-24 rounded-full" />
        <Skeleton class="h-4 w-full" />
        <Skeleton class="h-4 w-3/4" />
        <Separator />
        <Skeleton class="h-32 w-full" />
      </div>

      <!-- Detail content -->
      <template v-else-if="store.selectedEmail">
        <ScrollArea class="flex-1">
          <div class="space-y-5 p-6">
            <!-- Header: sender + date -->
            <div class="flex items-start gap-3">
              <Avatar class="h-10 w-10 shrink-0">
                <AvatarFallback>
                  {{ getInitials(store.selectedEmail.from_name, store.selectedEmail.from_address) }}
                </AvatarFallback>
              </Avatar>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold">
                  {{ store.selectedEmail.from_name || store.selectedEmail.from_address }}
                </p>
                <p v-if="store.selectedEmail.from_name" class="text-xs text-muted-foreground">
                  {{ store.selectedEmail.from_address }}
                </p>
                <p class="mt-0.5 text-xs text-muted-foreground">
                  <Clock class="mr-1 inline h-3 w-3" />{{ formatDate(store.selectedEmail.date) }}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                :class="store.selectedEmail.is_flagged ? 'text-amber-500' : 'text-muted-foreground'"
                title="Marquer important"
                @click="toggleFlag"
              >
                <Star class="h-4 w-4" :class="{ 'fill-current': store.selectedEmail.is_flagged }" />
              </Button>
            </div>

            <!-- Subject -->
            <h2 class="text-base font-medium leading-snug">
              {{ store.selectedEmail.subject || '(sans sujet)' }}
            </h2>

            <!-- Classification -->
            <div v-if="store.selectedEmail.classification" class="flex flex-wrap items-center gap-2">
              <Badge :class="CATEGORY_CONFIG[store.selectedEmail.classification.category]?.bgClass">
                {{ CATEGORY_CONFIG[store.selectedEmail.classification.category]?.label ?? store.selectedEmail.classification.category }}
              </Badge>
              <Badge variant="secondary" class="tabular-nums text-xs">
                {{ Math.round(store.selectedEmail.classification.confidence * 100) }}% confiance
              </Badge>
              <Badge variant="outline" class="text-xs">
                {{ store.selectedEmail.classification.classified_by }}
              </Badge>
              <Badge
                v-if="store.selectedEmail.classification.status === 'review'"
                variant="outline"
                class="border-amber-300 text-amber-700 dark:text-amber-400"
              >
                en review
              </Badge>
            </div>

            <!-- Phishing warning -->
            <div
              v-if="store.selectedEmail.classification?.category === 'phishing'"
              class="flex items-center gap-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300"
            >
              <ShieldAlert class="h-4 w-4 shrink-0" />
              Cet email a été identifié comme potentiel phishing. Soyez prudent avec les liens et pièces jointes.
            </div>

            <!-- Recipients -->
            <div class="space-y-1.5 text-sm">
              <div v-if="store.selectedEmail.to_addresses?.length" class="flex gap-2">
                <span class="shrink-0 text-xs font-medium text-muted-foreground">À :</span>
                <span class="text-xs">{{ store.selectedEmail.to_addresses.join(', ') }}</span>
              </div>
              <div v-if="store.selectedEmail.cc_addresses?.length" class="flex gap-2">
                <span class="shrink-0 text-xs font-medium text-muted-foreground">Cc :</span>
                <span class="text-xs">{{ store.selectedEmail.cc_addresses.join(', ') }}</span>
              </div>
            </div>

            <!-- Metadata row -->
            <div class="flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span v-if="store.selectedEmail.folder" class="flex items-center gap-1">
                <FolderInput class="h-3 w-3" />
                {{ store.selectedEmail.folder }}
              </span>
              <span v-if="store.selectedEmail.size_bytes" class="flex items-center gap-1">
                <Mail class="h-3 w-3" />
                {{ formatBytes(store.selectedEmail.size_bytes) }}
              </span>
              <span v-if="store.selectedEmail.has_attachments" class="flex items-center gap-1">
                <Paperclip class="h-3 w-3" />
                {{ store.selectedEmail.attachment_names?.length ?? 0 }} pièce(s) jointe(s)
              </span>
            </div>

            <!-- Attachments list -->
            <div v-if="store.selectedEmail.attachment_names?.length" class="flex flex-wrap gap-1.5">
              <Badge
                v-for="name in store.selectedEmail.attachment_names"
                :key="name"
                variant="outline"
                class="gap-1 text-xs"
              >
                <Paperclip class="h-3 w-3" />
                {{ name }}
              </Badge>
            </div>

            <Separator />

            <!-- Body content -->
            <div v-if="sanitizedHtml" class="space-y-2">
              <p class="text-xs font-medium text-muted-foreground">Contenu</p>
              <div class="email-html-content rounded-md bg-muted/50 p-3 text-sm leading-relaxed overflow-x-auto" v-html="sanitizedHtml" />
            </div>
            <div v-else-if="store.selectedEmail.body_excerpt" class="space-y-2">
              <p class="text-xs font-medium text-muted-foreground">Contenu</p>
              <div class="rounded-md bg-muted/50 p-3">
                <p class="whitespace-pre-wrap text-sm leading-relaxed">{{ store.selectedEmail.body_excerpt }}</p>
              </div>
            </div>
            <div v-else class="flex flex-col items-center py-6 text-center">
              <Mail class="mb-2 h-8 w-8 text-muted-foreground/30" />
              <p class="text-xs text-muted-foreground">Aucun contenu disponible</p>
            </div>
          </div>
        </ScrollArea>

        <!-- Footer actions -->
        <SheetFooter class="border-t px-6 py-3">
          <div class="flex w-full items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button variant="outline" size="sm">
                  <FolderInput class="h-4 w-4" />
                  Déplacer
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem @click="moveEmail('INBOX')">
                  <Inbox class="h-4 w-4" /> Boîte de réception
                </DropdownMenuItem>
                <DropdownMenuItem @click="moveEmail('Archive')">
                  <Archive class="h-4 w-4" /> Archive
                </DropdownMenuItem>
                <DropdownMenuItem @click="moveEmail('Spam')">
                  <Flag class="h-4 w-4" /> Spam
                </DropdownMenuItem>
                <DropdownMenuItem @click="moveEmail('Trash')">
                  <Trash2 class="h-4 w-4" /> Corbeille
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button variant="outline" size="sm" @click="toggleFlag">
              <Star class="h-4 w-4" :class="{ 'fill-amber-500 text-amber-500': store.selectedEmail.is_flagged }" />
              {{ store.selectedEmail.is_flagged ? 'Retirer' : 'Important' }}
            </Button>

            <Button
              variant="outline"
              size="sm"
              class="ml-auto"
              :disabled="reclassifying"
              @click="reclassify"
            >
              <Loader2 v-if="reclassifying" class="h-4 w-4 animate-spin" />
              <RefreshCw v-else class="h-4 w-4" />
              Reclassifier
            </Button>
          </div>
        </SheetFooter>
      </template>

      <!-- Error / no data -->
      <div v-else class="flex flex-1 flex-col items-center justify-center p-6">
        <User class="mb-2 h-8 w-8 text-muted-foreground/30" />
        <p class="text-sm text-muted-foreground">Email introuvable</p>
      </div>
    </SheetContent>
  </Sheet>
</template>
