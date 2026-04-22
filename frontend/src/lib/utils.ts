import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNowStrict } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

type CategoryKey =
  | 'important'
  | 'work'
  | 'personal'
  | 'newsletter'
  | 'promotion'
  | 'notification'
  | 'spam'
  | 'phishing'
  | 'transactional'

interface CategoryMeta {
  label: string
  bgClass: string
  color: string
}

export const CATEGORY_CONFIG: Record<string, CategoryMeta> = {
  important: {
    label: 'Important',
    bgClass: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30',
    color: '#ef4444',
  },
  work: {
    label: 'Travail',
    bgClass: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30',
    color: '#3b82f6',
  },
  personal: {
    label: 'Personnel',
    bgClass: 'bg-violet-500/15 text-violet-700 dark:text-violet-400 border-violet-500/30',
    color: '#8b5cf6',
  },
  newsletter: {
    label: 'Newsletter',
    bgClass: 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/30',
    color: '#06b6d4',
  },
  promotion: {
    label: 'Promotion',
    bgClass: 'bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/30',
    color: '#f97316',
  },
  notification: {
    label: 'Notification',
    bgClass: 'bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/30',
    color: '#6b7280',
  },
  spam: {
    label: 'Spam',
    bgClass: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30',
    color: '#f59e0b',
  },
  phishing: {
    label: 'Phishing',
    bgClass: 'bg-red-600/15 text-red-700 dark:text-red-400 border-red-600/30',
    color: '#dc2626',
  },
  transactional: {
    label: 'Transactionnel',
    bgClass: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
    color: '#10b981',
  },
}

export function formatRelativeDate(dateInput: string | Date | null | undefined): string {
  if (!dateInput) return '—'
  const date = typeof dateInput === 'string' ? new Date(dateInput) : dateInput
  if (Number.isNaN(date.getTime())) return '—'
  return formatDistanceToNowStrict(date, { addSuffix: true })
}
