/* ----------------------------------------------------------------
   API response types — mirrors backend Pydantic schemas
   ---------------------------------------------------------------- */

// Common
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

// Account
export interface Account {
  id: string
  name: string
  email: string
  provider: string | null
  imap_host: string
  imap_port: number
  smtp_host: string | null
  smtp_port: number | null
  is_active: boolean
  last_poll_at: string | null
  last_poll_error: string | null
  folder_mapping: Record<string, string>
  created_at: string
}

// Classification
export interface ClassificationSummary {
  category: string
  confidence: number
  status: string
  classified_by: string
}

export interface ClassificationDetail extends ClassificationSummary {
  id: string
  explanation: string | null
  is_spam: boolean
  is_phishing: boolean
  phishing_reasons: string[] | null
  llm_provider: string | null
  llm_model: string | null
  tokens_used: number | null
  processing_time_ms: number | null
  created_at: string
}

// Email
export interface Email {
  id: string
  account_id: string
  from_address: string
  from_name: string | null
  subject: string | null
  date: string
  folder: string | null
  is_read: boolean
  is_flagged: boolean
  has_attachments: boolean
  processing_status: string
  classification: ClassificationSummary | null
}

export interface EmailDetail extends Email {
  to_addresses: string[] | null
  cc_addresses: string[] | null
  body_excerpt: string | null
  body_html_excerpt: string | null
  attachment_names: string[] | null
  original_folder: string | null
  size_bytes: number | null
  message_id: string | null
  thread_id: string | null
  created_at: string
}

// Review
export interface ReviewItem {
  email: {
    id: string
    from_address: string
    from_name: string | null
    subject: string | null
    date: string
    body_excerpt: string | null
  }
  classification: {
    category: string
    confidence: number
    explanation: string | null
    is_spam: boolean
    is_phishing: boolean
  }
}

export interface ReviewStats {
  total_pending: number
  by_category: Record<string, number>
  oldest_pending: string | null
}

// Rule
export interface Rule {
  id: string
  account_id: string | null
  name: string
  type: 'structured' | 'natural'
  priority: number
  is_active: boolean
  category: string | null
  conditions: Record<string, unknown> | null
  natural_text: string | null
  actions: Record<string, unknown>[]
  match_count: number
  last_matched_at: string | null
  created_at: string
  updated_at: string
}

// Activity
export interface ActivityLog {
  id: string
  account_id: string | null
  event_type: string
  severity: string
  title: string
  details: Record<string, unknown> | null
  email_id: string | null
  created_at: string
}

// Settings
export interface Settings {
  llm_provider: string
  llm_model: string
  llm_base_url: string | null
  llm_temperature: number
  polling_interval_minutes: number
  confidence_threshold: number
  auto_mode: boolean
  max_few_shot_examples: number
  body_excerpt_length: number
  retention_days: number
  email_retention_days: number
  phishing_auto_quarantine: boolean
  initial_fetch_since: string | null
  has_api_key: boolean
  has_app_password: boolean
}

// System
export interface HealthResponse {
  status: string
  checks: Record<string, { status: string; latency_ms?: number; error?: string }>
  imap_accounts: { account: string; status: string; last_poll: string | null; error: string | null }[]
  scheduler: { running: boolean; jobs: number; next_poll: string | null }
}

export interface LLMStatus {
  configured: boolean
  available: boolean
  provider: string
  model: string
  error: string | null
}

export interface SystemStats {
  uptime_seconds: number
  emails_processed_today: number
  classifications_today: number
  pending_review: number
  active_accounts: number
  llm_status: LLMStatus | null
}

// Newsletter
export interface Newsletter {
  id: string
  account_id: string
  sender_profile_id: string | null
  name: string | null
  sender_address: string
  unsubscribe_link: string | null
  unsubscribe_mailto: string | null
  unsubscribe_method: string | null
  subscription_status: string
  total_received: number
  total_read: number
  read_rate: number
  frequency_days: number | null
  last_received_at: string | null
  unsubscribed_at: string | null
  created_at: string
  updated_at: string
}

export interface NewsletterStats {
  total_newsletters: number
  total_subscribed: number
  total_unsubscribed: number
  avg_read_rate: number
  never_read_count: number
}

// Sender
export interface Sender {
  id: string
  account_id: string
  email_address: string
  display_name: string | null
  domain: string | null
  primary_category: string | null
  total_emails: number
  last_email_at: string | null
  is_newsletter: boolean
  is_blocked: boolean
  created_at: string
  updated_at: string
}

export interface SenderCategoryStats {
  category: string
  count: number
  corrected_count: number
}

export interface SenderDetail extends Sender {
  category_stats: SenderCategoryStats[]
}

// Analytics
export interface AnalyticsOverview {
  period: string
  emails_received: number
  emails_today: number
  review_pending: number
  phishing_blocked: number
  spam_filtered: number
  auto_classification_rate: number
  newsletters_tracked: number
}

export interface CategoryBreakdown {
  category: string
  count: number
  percentage: number
}

export interface DailyVolume {
  date: string
  total: number
  by_category: Record<string, number>
}

export interface TopSender {
  email_address: string
  display_name: string | null
  total_emails: number
  primary_category: string | null
  last_email_at: string | null
}

// Thread
export interface ThreadEmailSummary {
  id: string
  from_address: string
  from_name: string | null
  subject: string | null
  date: string
  is_read: boolean
  category: string | null
}

export interface Thread {
  id: string
  account_id: string
  subject_normalized: string | null
  participants: string[] | null
  email_count: number
  last_email_at: string | null
  awaiting_reply: boolean
  awaiting_response: boolean
  reply_needed_since: string | null
  created_at: string
  updated_at: string
}

export interface ThreadDetail extends Thread {
  emails: ThreadEmailSummary[]
}

export interface ThreadStats {
  awaiting_reply: number
  awaiting_response: number
  total_threads: number
  oldest_awaiting: string | null
}

// LLM
export interface LLMModel {
  name: string
  size: string | null
  modified_at: string | null
}

// Ollama manager
export interface LoadedModel {
  name: string
  size_bytes: number
  size_vram_bytes: number
  context_length: number
  expires_at: string | null
}

export interface InstalledModel {
  name?: string
  size?: number
  digest?: string
  modified_at?: string
  [key: string]: unknown
}

export interface OllamaStatus {
  running: boolean
  managed_by_us: boolean
  pid: number | null
  binary_path: string | null
  install_method: 'homebrew' | 'systemd' | 'app' | 'docker' | 'unknown' | null
  service_status: 'running' | 'stopped' | 'not-installed' | null
  loaded_models: LoadedModel[]
  installed_models: InstalledModel[]
  total_disk_bytes: number
}
