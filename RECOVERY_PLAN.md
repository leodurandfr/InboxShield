# Plan de récupération InboxShield

État au 2026-04-23 : squelette cohérent mais non démarrable. Ce plan décrit les étapes pour rendre l'app bootable, puis fonctionnelle.

Les fichiers manquants ont été identifiés en comparant les imports de `backend/app/main.py` et des routeurs avec l'arborescence réelle. Références de spec : `docs/01-ARCHITECTURE.md`, `docs/02-DATABASE-SCHEMA.md`, `docs/04-API-ENDPOINTS.md`, `docs/05-FRONTEND-UI.md`.

---

## Phase 0 — État nettoyé ✅ (déjà fait)

- [x] Suppression des 541 duplicats `*_HHMMSS`
- [x] Suppression des 15 `_tmp_*` vides
- [x] Nettoyage des `.DS_Store` et `__pycache__`
- [x] Reconstruction de `frontend/node_modules/` (symlinks pnpm cassés par Synology)
- [x] Renommage `files/` → `docs/` + permissions standard
- [x] `.gitignore` créé
- [x] Premier commit git

---

## Phase 1 — Fondations backend ✅ (complétée — l'app importe sans erreur)

Objectif : `python -c "from app.main import app"` réussit. ✅

### 1.1 Module base de données (`app/db/`)
- [x] Créer `app/db/__init__.py`
- [x] Créer `app/db/database.py` — engine async SQLAlchemy, session factory
- [x] Créer `app/db/base.py` — `Base = DeclarativeBase` + mixins (UUID, Timestamp)

### 1.2 Dépendances API (`app/api/deps.py`)
- [x] Créer `app/api/deps.py` avec `get_db()` dependency (commit-on-success, rollback-on-error)

### 1.3 Models SQLAlchemy manquants (selon `docs/02-DATABASE-SCHEMA.md`)
- [x] `app/models/__init__.py` — réexporte tous les models pour Alembic
- [x] `app/models/account.py` — tables `accounts` + `account_settings`
- [x] `app/models/action.py` — table `actions`
- [x] `app/models/activity_log.py` — table `activity_logs`
- [x] `app/models/newsletter.py` — table `newsletters`
- [x] `app/models/sender_profile.py` — tables `sender_profiles` + `sender_category_stats`
- [x] Alignement des 4 existants : ajout de `Email.reply_to`, `Rule.category`, `Settings.initial_fetch_since`

### 1.4 Schemas Pydantic manquants
- [x] `app/schemas/account.py` — `AccountCreate`, `AccountUpdate`, `AccountResponse`, `TestConnection*`, `FolderMappingUpdate`, `CategoryActionsUpdate`
- [x] `app/schemas/common.py` — `PaginatedResponse[T]`
- [x] `app/schemas/activity.py`, `newsletter.py`, `sender.py`, `review.py`, `thread.py`
- [x] `app/schemas/analytics.py` enrichi (ConfusionMatrix, PerformanceMetrics, HourlyHeatmap)
- [x] `app/schemas/system.py` enrichi (OllamaManagerStatus, LLMStatus)
- [x] `app/schemas/settings.py` : ajout `has_api_key`

### 1.5 Services manquants
- [x] `app/services/encryption.py` — Fernet encrypt/decrypt depuis `settings.encryption_key`
- [x] `app/services/ollama_manager.py` — stub avec `get_status()` (health HTTP) + `restart()`
- [x] `app/services/ws_manager.py` — `ConnectionManager` singleton (WebSocket broadcast)
- [x] `app/services/thread_service.py` — `resolve_or_create_thread`, `normalize_subject`, `update_thread_reply_status`
- [x] `app/services/threshold_service.py` — `evaluate_and_adjust_threshold` (Phase 3 stub fonctionnel)
- [x] `app/services/newsletter_service.py` — `compute_newsletter_stats`, `unsubscribe_newsletter` stub

### 1.6 Routeurs API manquants
- [x] `app/api/activity.py` — GET `/` (feed paginé)
- [x] `app/api/newsletters.py` — list, stats, unsubscribe unitaire + bulk
- [x] `app/api/review.py` — list, approve, correct, bulk-approve
- [x] `app/api/senders.py` — list, detail, block/unblock
- [x] `app/api/threads.py` — list, stats, detail, resolve/ignore
- [x] `app/api/websocket.py` — endpoint `/ws` avec ping/pong

### 1.7 Migration initiale Alembic
- [x] `alembic.ini` créé + `alembic/script.py.mako` + répertoire `versions/`
- [x] `alembic/env.py` importe `Base.metadata` via `app.models`
- [ ] `alembic revision --autogenerate -m "initial schema"` → nécessite une Postgres (Phase 3)
- [ ] `alembic upgrade head` → nécessite une Postgres (Phase 3)

### 1.8 Dépendances
- [x] Ajout de `html2text`, `mail-parser-reply`, `tldextract` dans `pyproject.toml`

**Validation Phase 1** : `python -c "from app.main import app"` réussit ✅. `uvicorn app.main:app` démarre (le scheduler tente la connexion DB et échoue proprement — attendu hors Postgres). Les 60 routes sont enregistrées. Le endpoint `/api/v1/system/health` est fonctionnel mais nécessite PG pour retourner `healthy` (Phase 3).

---

## Phase 2 — Fondations frontend ✅ (complétée — build + type-check verts)

Objectif : `pnpm run dev` sert la SPA et la route `/` charge `DashboardView.vue` sans erreur. ✅

### 2.1 Points d'entrée Vite
- [x] Créer `frontend/index.html`
- [x] Créer `frontend/src/main.ts`
- [x] Créer `frontend/tsconfig.app.json`, `tsconfig.node.json`, `tsconfig.vitest.json`, `env.d.ts`
- [x] Ajouter `compilerOptions.paths` + `baseUrl` au `tsconfig.json` racine (requis par shadcn-vue CLI)

### 2.2 Régénération des pièces manquantes (ampleur découverte à l'exécution)

Le cleanup Synology a détruit bien plus que le plan initial anticipait. Remis en place :

- [x] 28 composants Shadcn-vue via `pnpm dlx shadcn-vue@latest add …` (alert, alert-dialog, avatar, badge, button, calendar, card, checkbox, collapsible, dialog, dropdown-menu, input, label, popover, progress, scroll-area, select, separator, sheet, sidebar, skeleton, sonner, switch, table, tabs, textarea, tooltip)
- [x] `src/lib/utils.ts` — `cn`, `CATEGORY_CONFIG` (9 catégories), `formatRelativeDate`
- [x] `src/composables/useTheme.ts` — dark mode via classe `dark` sur `<html>`, persistance localStorage
- [x] `src/stores/newsletters.ts`, `senders.ts`, `threads.ts`
- [x] Enrichissement `stores/analytics.ts` (performance, confusionMatrix, heatmap, totalCorrections, exportCsv, exporting)
- [x] Enrichissement `stores/emails.ts` (selectedEmail, detailLoading, fetchEmailDetail, closeDetail, flagEmail)
- [x] Enrichissement `stores/settings.ts` (deleteLLMModel)
- [x] `src/components/layout/SiteHeader.vue`
- [x] `src/components/shared/KPICard.vue`, `EmptyState.vue`, `PaginationControls.vue`
- [x] `src/components/rules/RuleCreateForm.vue`
- [x] `src/components/threads/ThreadDetailSheet.vue`
- [x] Correctifs : ajout de `body_html_excerpt` au type `EmailDetail`, fermeture `</div>` manquante dans `RuleListItem.vue`, ordre d'attributs dans `Sonner.vue`, types `ReviewItem` stricts

### 2.3 Validation
- [x] `pnpm run type-check` ✅ exit 0
- [x] `pnpm run build-only` ✅ built in 2.55s
- [x] `pnpm run dev` ✅ `ready in 336 ms`, HTTP 200 sur `/`, `/src/main.ts`, `/src/App.vue`, `/src/views/DashboardView.vue`
- [x] `src/lib/api.ts` pointe vers `/api/v1` (proxyfié par Vite → `http://localhost:8000`)

**Validation Phase 2** : la SPA boote, toutes les vues compilent. Les stubs UI s'afficheront vides tant que le backend n'est pas lancé ; dès que `uvicorn` + Postgres tournent, les vues se peuplent via les appels API existants.

---

## Phase 3 — Stack Docker end-to-end ✅ (complétée — `docker compose up -d` fonctionnel)

Objectif : `docker compose up` lance l'app complète avec Postgres + (Ollama). ✅

- [x] Créer `.env.example` (variables listées dans `docs/06-DEPLOYMENT.md`)
- [x] Vérifier `docker-compose.yml` et `docker-compose.mac.yml` (config valide via `docker compose config`)
- [x] Vérifier `backend/Dockerfile` (build réussit en ~6s avec cache) + ajout `.dockerignore`
- [x] Créer `frontend/Dockerfile` (build multi-stage pnpm + Nginx 1.27-alpine) + `.dockerignore`
- [x] Enrichir `nginx.conf` : ajout du proxy WebSocket `/api/v1/ws` (Upgrade headers, 3600s timeout)
- [x] Génération de la migration initiale Alembic `256a2db15dc2_initial_schema.py` (autogenerate contre Postgres 16 dans le compose)
- [x] `docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d` : 3 conteneurs up (postgres healthy, backend, frontend)
- [x] Validation end-to-end : `GET http://localhost:8080/` → 200 (SPA), `GET http://localhost:8080/api/v1/system/health` → 200 proxyfié (db ok, scheduler running, 4 jobs)
- [ ] Pull modèle Ollama (`ollama pull qwen2.5:7b`) — étape utilisateur, hors scope CI

**Validation Phase 3** : accès à l'UI via `http://localhost:8080` en passant par Nginx ✅. API `/api/v1/*` proxyfiée correctement. Volume `postgres_data` persistant. Stack tear-down propre avec `docker compose down -v`.

---

## Phase 4 — Implémentation fonctionnelle des stubs ✅ (complétée — 146 tests verts)

- [x] `api/activity.py` — filtres `account_id` / `event_type` / `severity` + pagination (déjà implémenté en Phase 1.6)
- [x] `api/newsletters.py` — list + stats + désinscription unitaire & bulk ; endpoint renommé `/bulk-unsubscribe` pour matcher le frontend
- [x] `api/review.py` — approve / correct / bulk-approve (déléguent à `classifier.approve_classification` / `correct_classification` qui font le few-shot + sender_stats) + **nouvel endpoint `/review/stats`** (total_pending, by_category, oldest_pending)
- [x] `api/senders.py` — list + detail + block/unblock (déjà implémenté en Phase 1.6)
- [x] `api/websocket.py` — ConnectionManager + endpoint + broadcast utilisé par le classifier (`email_classifying`, `email_classified`)
- [x] `services/newsletter_service.py` — **désinscription réelle** : POST RFC 8058 One-Click, GET, mailto via aiosmtplib + `extract_unsubscribe_info` (headers + fallback HTML) + `detect_or_update_newsletter`
- [x] `services/ollama_manager.py` — `is_running` / `list_installed_models` / `has_model` / `pull_model` (stream `/api/pull`) / `auto_pull_if_missing` / `delete_model`
- [x] `services/thread_service.py` — `update_thread_reply_status` calcule désormais `awaiting_reply` / `awaiting_response` / `reply_needed_since` à partir de `user_email` vs `from_address` / `to_addresses` + maintient `participants`. Ajout de `resolve_thread` / `ignore_thread`.

**Validation Phase 4** : `python -c "from app.main import app"` → 67 routes enregistrées. `pytest tests/` → 146 tests passent. Smoke-tests des helpers `extract_unsubscribe_info` et `normalize_subject` OK.

---

## Phase 5 — Qualité ✅ (complétée)

- [x] Tests : `pytest` passe — 146/146 verts, ajout de `pythonpath`/`testpaths` dans `pyproject.toml`
- [x] `ruff check .` propre — per-file-ignores pour les migrations Alembic, `app/llm/prompts.py`, `tests/test_url_analysis.py`, `app/main.py` (E402 intentionnel), `test_session*.py` (scripts bootstrap)
- [x] `ruff format .` — 35 fichiers reformatés
- [x] Correctifs hors-formattage : `_h2t` → `_get_h2t()`, `max_body` → `config` dans `fetch_emails_since`, `attributes` importé dans conftest, suppression de variables mortes, migration `PaginatedResponse` vers PEP 695 generics, renommage `BATCH_SIZE` → `batch_size`
- [x] Frontend : `pnpm run lint` propre (0 warnings / 0 errors) — création de `eslint.config.ts` (Vue 3 + TS + oxlint + prettier), suppression de 3 imports inutilisés (`Loader2`, `MessageSquare`, `onWsEvent`) + `CategoryKey`, `Email`, `PaginatedResponse`
- [x] `README.md` minimal (stack, démarrage Docker, workflows dev backend/frontend, liens vers `docs/`)
- [x] Commit + tag `v0.1.0-recovered`

---

## Notes

- **Pas de backwards-compat** à maintenir — le code n'a jamais été publié
- **Pas de données à migrer** — base de dev vierge
- **Priorité** : Phase 1 + 2 pour démarrer. Le reste peut être itératif.
- **Backup** : `InboxShield_BACKUP_20260423_010813.tar.gz` à conserver jusqu'à validation complète de Phase 2.
