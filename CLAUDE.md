# InboxShield

Application open source de gestion intelligente d'emails, auto-hebergee et privacy-first.
Utilise un LLM local (Ollama) ou cloud (Claude, OpenAI, Mistral) pour classifier, filtrer et proteger automatiquement les boites mail via IMAP.

## Documentation

Toute la spec detaillee est dans `docs/`. Consulter ces fichiers AVANT d'implementer une feature :

- `00-PROJECT-OVERVIEW.md` — Vision, stack, positionnement
- `01-ARCHITECTURE.md` — Architecture complete, structure du projet, flux de donnees
- `02-DATABASE-SCHEMA.md` — Schema PostgreSQL complet (toutes les tables, index, relations)
- `03a-IMAP-CONNECTION.md` — Connexion IMAP, polling, auto-detection provider
- `03b-AI-CLASSIFICATION.md` — Pipeline de classification (sender_profile -> rules -> LLM)
- `03c-SPAM-PHISHING-DETECTION.md` — Detection spam/phishing, analyse URLs
- `03d-RULES-ENGINE.md` — Moteur de regles (structurees + langage naturel)
- `03e-REVIEW-QUEUE.md` — Review queue, apprentissage, few-shot
- `03f-BULK-UNSUBSCRIBE.md` — Desinscription newsletters
- `03g-REPLY-TRACKING.md` — Suivi des reponses (Phase 3)
- `03h-ANALYTICS.md` — Analytics et dashboard
- `04-API-ENDPOINTS.md` — Tous les endpoints API REST
- `05-FRONTEND-UI.md` — Frontend, composants, stores, routes
- `06-DEPLOYMENT.md` — Docker, Dockerfiles, Nginx, variables d'environnement
- `07-ROADMAP.md` — Roadmap par phases avec checklist

## Stack technique

### Backend (Python 3.12)
- **Framework** : FastAPI 0.115 (async)
- **ORM** : SQLAlchemy 2.0 + Alembic (migrations)
- **DB** : PostgreSQL 16
- **IMAP** : `imap_tools`
- **SMTP** : `aiosmtplib`
- **LLM** : SDK Ollama Python + Anthropic/OpenAI/Mistral SDKs (installes)
- **Scheduling** : APScheduler (integre au process FastAPI)
- **Parsing** : `beautifulsoup4`
- **Validation** : Pydantic v2
- **Chiffrement** : Fernet (cryptography)
- **Package manager** : `uv` (pyproject.toml, pas requirements.txt)
- **HTTP client** : `httpx` (async)

### Frontend (TypeScript)
- **Framework** : Vue 3.5 (Composition API, `<script setup>`)
- **Build** : Vite 7
- **State** : Pinia 3
- **UI** : Tailwind CSS v4 + Shadcn-vue (60+ composants installes)
- **Icons** : Lucide (lucide-vue-next)
- **Charts** : Chart.js ou Apache ECharts (a choisir en Phase 2)
- **Dates** : date-fns
- **Router** : Vue Router
- **Toasts** : vue-sonner
- **Package manager** : `pnpm`

### Infrastructure
- Docker + Docker Compose
- Nginx (reverse proxy : SPA + proxy /api/*)
- Ollama (LLM local) ou APIs cloud

## Structure du projet

```
inboxshield/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan (scheduler startup/shutdown)
│   │   ├── config.py            # Pydantic BaseSettings
│   │   ├── api/                 # Routes : accounts, emails, review, rules, newsletters, senders, analytics, threads, settings, activity, system
│   │   │   └── deps.py          # Dependencies (get_db)
│   │   ├── services/            # classifier, imap, rule_engine, sender, action, activity, scheduler, encryption, llm_service, url_analysis, newsletter_service, thread_service, threshold_service
│   │   ├── llm/                 # base.py, ollama.py, anthropic.py, openai.py, mistral.py, prompts.py
│   │   ├── models/              # account, email, classification, sender_profile, rule, activity_log, action, newsletter, settings
│   │   ├── schemas/             # Pydantic schemas (request/response) par domaine + common.py
│   │   └── db/                  # database.py (async engine), base.py (UUIDMixin, TimestampMixin)
│   ├── alembic/                 # 2 migrations (initial_schema + add_initial_fetch_since)
│   ├── tests/                   # 135 tests : conftest, test_rule_engine, test_url_analysis, test_llm_service, test_llm_providers, test_encryption, test_api_system
│   ├── pyproject.toml           # Dependencies + config uv
│   └── Dockerfile               # Python 3.12 + uv, auto-migration au startup
├── frontend/
│   ├── src/
│   │   ├── views/               # DashboardView, EmailsView, ReviewView, RulesView, ThreadsView, NewslettersView, SendersView, AnalyticsView, SettingsView
│   │   ├── components/
│   │   │   ├── layout/          # AppSidebar, SiteHeader, PageHeader (implementes)
│   │   │   ├── ui/              # Shadcn-vue (60+ composants)
│   │   │   ├── dashboard/       # (vide — a implementer)
│   │   │   ├── emails/          # (vide — a implementer)
│   │   │   ├── review/          # (vide — a implementer)
│   │   │   ├── rules/           # (vide — a implementer)
│   │   │   └── settings/        # (vide — a implementer)
│   │   ├── stores/              # app, dashboard, emails, review, rules, settings, newsletters, senders, analytics, threads (implementes)
│   │   ├── composables/         # useTheme, usePolling (implementes). Manquant : usePagination
│   │   ├── lib/                 # api.ts (client HTTP type), types.ts (interfaces TS), utils.ts (CATEGORY_CONFIG, formatRelativeDate)
│   │   └── router/              # index.ts (routes avec lazy loading)
│   ├── vite.config.ts
│   ├── nginx.conf               # SPA fallback + API proxy + gzip
│   └── Dockerfile               # Node 20 + pnpm build + Nginx
├── docker-compose.yml           # 4 services : backend, frontend, postgres, ollama
├── docker-compose.mac.yml       # Variante Mac (Ollama natif via host.docker.internal)
├── .env.example
└── docs/                        # 14 fichiers de spec detaillee
```

## Etat d'avancement

### Phase 1 — MVP (complet)

#### Backend — COMPLET
- [x] Setup FastAPI + structure + config
- [x] Modeles SQLAlchemy (11 tables) + 2 migrations Alembic
- [x] Service IMAP : connexion, test, decouverte dossiers, fetch, move, flag, delete
- [x] Auto-detection provider IMAP (15+ providers : GMX, Gmail, Outlook, Yahoo, etc.)
- [x] Interface LLM abstraite + OllamaProvider
- [x] Prompt de classification + parsing JSON tolerant
- [x] ClassifierService : pipeline complet sender_profile → rules → LLM (5 etapes)
- [x] RuleEngine : evaluation regles structurees (7 operateurs, 6 champs)
- [x] Scheduler APScheduler : poll_emails, cleanup, health check, adjust_threshold
- [x] Gestion du premier fetch (onboarding, 100 emails)
- [x] Review queue : approve, correct, mise a jour sender_profile
- [x] Few-shot learning : injection des corrections dans le prompt
- [x] Sender profiles : creation, mise a jour, classification directe
- [x] Activity logs + audit trail
- [x] Chiffrement Fernet des credentials IMAP
- [x] API endpoints : 12 routers (accounts, emails, review, rules, threads, newsletters, senders, analytics, settings, system, activity, websocket)
- [x] WebSocket : ConnectionManager singleton (`ws_manager.py`) + endpoint `/api/v1/ws` pour events temps reel
- [x] Tests unitaires : 135 tests (pytest + pytest-asyncio) — rule_engine, url_analysis, llm_service, encryption, api_system, llm_providers

#### Frontend — COMPLET
- [x] Setup Vue 3 + Vite + Tailwind v4 + Shadcn-vue + TypeScript
- [x] Layout : AppSidebar + SiteHeader + PageHeader
- [x] Stores Pinia : app, dashboard, emails, review, rules, settings, newsletters, senders, analytics, threads (tous implementes)
- [x] Client HTTP type (api.ts) + interfaces TypeScript (types.ts) + utils (CATEGORY_CONFIG, formatRelativeDate)
- [x] Router avec lazy loading
- [x] Dark mode (useTheme composable)
- [x] Toasts (vue-sonner)
- [x] **DashboardView** : 4 KPI cards, table emails recents avec avatars/badges, bouton polling, loading/empty states, clic vers detail
- [x] **EmailsView** : liste paginee, tabs par categorie, recherche expediteur, pagination complete, loading/empty
- [x] **Email detail** : Sheet drawer (clic sur email dans EmailsView ou DashboardView), header expediteur, classification badges, destinataires, metadonnees, pieces jointes, contenu, actions (deplacer, flag, reclassifier)
- [x] **ReviewView** : items avec approve/correct, details collapsibles, bulk approve, selection categorie
- [x] **RulesView** : CRUD regles, toggle actif/inactif, formulaire creation (structured + natural), suppression avec confirmation
- [x] **SettingsView** : CRUD comptes IMAP, test connexion, config LLM (provider/modele/cle API/base URL), pull modeles Ollama avec progression, seuil confiance, auto mode, date initial fetch. UX provider : Ollama → dropdown modeles locaux, Cloud → liste modeles du provider (statique/dynamique), modele par defaut auto, champ cle API conditionnel
- [x] **NewslettersView** : liste paginee, stats (total/abonnees/taux lecture/jamais lues), filtres par statut, taux lecture avec barre, frequence, desinscription unitaire/groupee, selection multiple
- [x] **SendersView** : liste paginee, tabs (tous/newsletters/bloques), recherche, categories avec badges, bloquer/debloquer, detail Sheet avec repartition categories
- [x] **AnalyticsView** : KPI cards, repartition categories, top expediteurs, volume quotidien, performance metrics, matrice de confusion, heatmap jour×heure, export CSV, selection periode (7j/30j/90j)
- [x] **ThreadsView** : stats cards (a repondre/reponse attendue/total/plus ancien), tabs avec filtres, liste conversations avec badges statut, detail Sheet avec timeline emails, actions resolve/ignore
- [x] Composable `usePolling` (rafraichissement automatique periodique — Dashboard 60s, Emails 60s, Review 30s, pause si onglet masque)
- [x] Composable `useWebSocket` (connexion WS singleton, reconnexion backoff exponentiel, ping/pong keep-alive, auto-cleanup listeners)
- [x] Integration WebSocket dans views : Dashboard, Emails, Review, Threads ecoutent les events WS pour refresh temps reel
- [x] Extraction composants : 13 composants extraits des Views monolithiques → `components/{domain}/` (shared: KPICard, PaginationControls; domain: EmailTable, EmailDetailSheet, ReviewItem, RuleCreateForm, RuleListItem, IMAPAccountSection, LLMConfigSection, ThreadDetailSheet, SenderDetailSheet)
- [ ] Setup wizard (onboarding premier compte) — reporte

#### Infra — COMPLET
- [x] Docker Compose : backend + frontend + postgres + ollama
- [x] docker-compose.mac.yml (Ollama natif)
- [x] Dockerfiles : backend (Python 3.12 + uv, venv activation directe, UV_NO_ENV_FILE=1) + frontend (Node 20 + pnpm + Nginx)
- [x] Nginx : SPA fallback + proxy /api/* + WebSocket proxy /api/v1/ws (Upgrade headers, 3600s timeout)
- [x] `.env.example`
- [x] README.md avec instructions d'installation

### Phase 2 — Intelligence (complet)
- [x] Providers LLM cloud : AnthropicProvider, OpenAIProvider, MistralProvider (generate, is_available, list_models + factory + tests)
- [x] Regles en langage naturel : backend (`interpret_rule`, `evaluate_rules` avec LLM) + frontend (formulaire, badge IA, texte affiche) + test endpoint wire
- [x] Detection phishing avancee : analyse URLs complete (11 heuristiques) + integree dans pipeline classifier + injectee dans prompt LLM
- [x] Table `email_urls` + service d'analyse (EmailUrl model, `_save_email_urls()` dans classifier)
- [x] Quarantaine automatique phishing (`phishing_auto_quarantine` dans classifier pipeline)
- [x] Bulk unsubscribe : extraction List-Unsubscribe (http/mailto), service newsletter_service.py, desinscription RFC 8058 + HTTP GET + mailto
- [x] Newsletter detection + stats : detect_or_update_newsletter, compute_newsletter_stats, frequency_days, read_rate
- [x] Analytics : 4 endpoints (overview, categories, volume, top-senders), periodes 7d/30d/90d
- [x] Frontend : pages Newsletters (desinscription groupee), Senders (bloquer/debloquer, detail), Analytics (KPI + charts)
- [x] Settings cloud providers : champ cle API (chiffree), base URL, selection modeles dynamique

### Phase 3 — Avancee (complet)
- [x] Email threading : thread_service.py (normalize_subject, resolve_or_create_thread — 4-step: In-Reply-To → References → Subject match → New)
- [x] Integration threading dans scheduler (apres flush, avant commit, avec try/except)
- [x] Reply tracking : awaiting_reply/awaiting_response, resolve/ignore actions
- [x] API threads : list (avec filtres), stats, detail (avec emails), resolve, ignore (5 endpoints)
- [x] Frontend ThreadsView : stats cards, tabs (tous/a repondre/reponse attendue), liste avec badges, detail Sheet timeline, actions resolve/ignore, polling 60s
- [x] Analytics avancees : confusion matrix, performance metrics, hourly heatmap (4 nouveaux endpoints)
- [x] Export CSV : StreamingResponse avec emails + classifications
- [x] Frontend AnalyticsView enrichi : performance cards (temps moyen, taux review, methodes, tokens), matrice de confusion, heatmap jour×heure, bouton export CSV
- [x] Ajustement dynamique du seuil de confiance : threshold_service.py (evaluate correction rate, ±0.03, bounds 0.5–0.95, job cron quotidien + endpoint API)
- [ ] Multi-comptes enrichi (UI + stats comparatives) — reporte

### Bugfixes notables
- [x] **Toggle regles** : ajout `await db.flush()` dans `update_rule` (api/rules.py) + optimistic update dans le store frontend (stores/rules.ts) pour eviter le snap-back du Switch Radix-Vue en mode controle
- [x] **Settings LLM provider UX** : suppression champ URL Ollama inutile, vidage modeles au changement de provider, modele par defaut auto (claude-sonnet-4/gpt-4o/mistral-large), query param `?provider=` sur `GET /settings/llm/models` pour retourner les modeles du provider selectionne sans attendre la sauvegarde
- [x] **Regles ne s'activent pas** : conditions `{}` falsy en Python → `is None`; route `/reorder` shadowed par `/{rule_id}` → reordonnee; actions des regles matchees ignorees → injectees dans `_execute_post_classification_actions`
- [x] **Filtre "En attente"** : `classification_status=review` → `processing_status=pending`
- [x] **Analyse silencieuse** : LLM `None` → fallback classification en `status=review`; `asyncio.create_task` sans reference → `_background_tasks` set; pas de thread assignment dans `_fetch_and_save_emails_full` → ajoute

## Conventions

### Backend
- API prefixee `/api/v1/`
- Async partout (FastAPI + SQLAlchemy async)
- Reponses JSON avec format d'erreur : `{"error": "CODE", "message": "...", "details": {}}`
- UUIDs pour tous les IDs
- Timestamps UTC
- Credentials IMAP chiffres Fernet (jamais en clair)
- Pagination : `page` + `per_page` (defaut 20)
- Semaphore pour limiter les appels LLM concurrents (max 5)

### Frontend
- Composition API + `<script setup>` exclusivement
- Stores Pinia : un store par domaine
- Client HTTP type dans `lib/api.ts`
- Tailwind v4 + Shadcn-vue pour l'UI
- Dark mode via composable `useTheme` (classe `dark` sur `<html>`)
- Nommage : `*View.vue` pour les pages, composants par domaine dans `components/`
- Container queries (`@container/main`) pour les layouts responsives
- Optimistic updates pour les toggle/switch : mettre a jour le store immediatement, revert en cas d'erreur API
- Switch Radix-Vue : toujours en mode controle (`:checked` + `@update:checked`), necessite update synchrone du store

### Base de donnees
- PostgreSQL 16 + SQLAlchemy 2.0 (async avec asyncpg)
- Migrations via Alembic (`alembic revision --autogenerate`, `alembic upgrade head`)
- 11 tables : accounts, account_settings, emails, email_threads, classifications, corrections, sender_profiles, rules, activity_logs, actions, newsletters, settings
- Mixins : UUIDMixin (id UUID PK), TimestampMixin (created_at, updated_at)
- Index documentes dans `02-DATABASE-SCHEMA.md`
- Politique de retention configurable (defaut: 90j logs, 365j emails)

### Categories d'emails
`important`, `work`, `personal`, `newsletter`, `promotion`, `notification`, `spam`, `phishing`, `transactional`

### Pipeline de classification (ordre)
1. Expediteur bloque ? → skip
2. Sender profile (count >= 5, >80%) ? → classification directe
3. Regle structuree matchee ? → classification par regle
4. Appel LLM → classification AI
5. Confiance >= seuil (0.7) ? → auto / review queue

## Commandes utiles

```bash
# Dev backend
cd backend && uvicorn app.main:app --reload --port 8000

# Dev frontend (pnpm, pas npm)
cd frontend && pnpm dev

# Docker
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:7b

# Docker Mac (Ollama natif)
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d

# Migrations
cd backend && alembic revision --autogenerate -m "description"
cd backend && alembic upgrade head

# Backup DB
docker compose exec postgres pg_dump -U inboxshield inboxshield > backup.sql

# Install deps
cd backend && uv sync
cd frontend && pnpm install
```

## Target hardware
- **Production** : Mac Mini M4 Pro 24 GB (Ollama natif + Docker pour le reste)
- **Dev** : MacBook Pro / toute machine avec Docker
- Sur Mac : Ollama en natif pour les performances GPU (Metal), backend via `host.docker.internal:11434`
