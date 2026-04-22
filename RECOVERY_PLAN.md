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

## Phase 2 — Fondations frontend (pour que `vite dev` démarre)

Objectif : `pnpm run dev` sert la SPA et la route `/` charge `DashboardView.vue` sans erreur.

### 2.1 Points d'entrée Vite
- [ ] Créer `frontend/index.html` (shell avec `<div id="app">` + `<script type="module" src="/src/main.ts">`)
- [ ] Créer `frontend/src/main.ts` (`createApp(App).use(router).use(createPinia()).mount('#app')`)

### 2.2 Vérifier la chaîne UI
- [ ] `pnpm run build-only` réussit
- [ ] `pnpm run type-check` ne remonte pas d'erreurs bloquantes
- [ ] `pnpm run dev` démarre et sert `/` sans 500

### 2.3 Connexion API
- [ ] Vérifier que `src/lib/api.ts` pointe vers `http://localhost:8000/api/v1/*` en dev
- [ ] Tester un store (`stores/dashboard.ts`) contre le backend

**Validation Phase 2** : `pnpm run dev` + backend lancé → dashboard s'affiche (même avec données vides).

---

## Phase 3 — Stack Docker end-to-end

Objectif : `docker compose up` lance l'app complète avec Postgres + Ollama.

- [ ] Créer `.env.example` (variables listées dans `docs/06-DEPLOYMENT.md`)
- [ ] Vérifier `docker-compose.yml` et `docker-compose.mac.yml`
- [ ] Vérifier `backend/Dockerfile` (build réussit)
- [ ] Vérifier `frontend/Dockerfile` (build multi-stage + Nginx)
- [ ] Vérifier `nginx.conf` (proxy `/api/*` → backend:8000)
- [ ] `docker compose up -d` sans erreur
- [ ] Pull modèle Ollama (`ollama pull qwen2.5:7b`)

**Validation Phase 3** : accès à l'UI via `http://localhost` en passant par Nginx.

---

## Phase 4 — Implémentation fonctionnelle des stubs

Une fois l'app démarrable, remplir les stubs créés en Phase 1.6 :

- [ ] `api/activity.py` — activity feed réel depuis `activity_logs`
- [ ] `api/newsletters.py` — list + unsubscribe (`docs/03f-BULK-UNSUBSCRIBE.md`)
- [ ] `api/review.py` — review queue + apprentissage (`docs/03e-REVIEW-QUEUE.md`)
- [ ] `api/senders.py` — top senders + bloquage
- [ ] `api/websocket.py` — push d'événements (emails classifiés, scheduler tick)
- [ ] `services/ollama_manager.py` — health check, auto-pull modèle
- [ ] `services/thread_service.py` — reply tracking complet

---

## Phase 5 — Qualité

- [ ] Tests : `pytest` passe (les 2 existants + nouveaux)
- [ ] `ruff check .` + `ruff format .` propres
- [ ] Frontend : `pnpm run lint` propre
- [ ] README.md minimal (installation, démarrage)
- [ ] Commit + tag `v0.1.0-recovered`

---

## Notes

- **Pas de backwards-compat** à maintenir — le code n'a jamais été publié
- **Pas de données à migrer** — base de dev vierge
- **Priorité** : Phase 1 + 2 pour démarrer. Le reste peut être itératif.
- **Backup** : `InboxShield_BACKUP_20260423_010813.tar.gz` à conserver jusqu'à validation complète de Phase 2.
