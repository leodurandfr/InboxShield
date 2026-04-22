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

## Phase 1 — Fondations backend (pour que `uvicorn` démarre sans erreur)

Objectif : `python -c "from app.main import app"` réussit.

### 1.1 Module base de données (`app/db/`)
- [ ] Créer `app/db/__init__.py`
- [ ] Créer `app/db/database.py` — engine async SQLAlchemy, session factory (selon `docs/01-ARCHITECTURE.md` §2.3)
- [ ] Créer `app/db/base.py` — `Base = declarative_base()` + import de tous les models pour Alembic

### 1.2 Dépendances API (`app/api/deps.py`)
- [ ] Créer `app/api/deps.py` avec `get_db()` dependency (async session yield)

### 1.3 Models SQLAlchemy manquants (selon `docs/02-DATABASE-SCHEMA.md`)
- [ ] `app/models/__init__.py` — réexporter tous les models
- [ ] `app/models/account.py` — tables `accounts` + `account_settings`
- [ ] `app/models/action.py` — table `actions`
- [ ] `app/models/activity_log.py` — table `activity_logs`
- [ ] `app/models/newsletter.py` — table `newsletters`
- [ ] `app/models/sender_profile.py` — tables `sender_profiles` + `sender_category_stats`
- [ ] Vérifier que les 4 existants (`classification`, `email`, `rule`, `settings`) sont alignés avec la spec

### 1.4 Schemas Pydantic manquants
- [ ] `app/schemas/account.py` — `AccountCreate`, `AccountUpdate`, `AccountResponse`
- [ ] `app/schemas/common.py` — `PaginatedResponse[T]`

### 1.5 Services manquants
- [ ] `app/services/encryption.py` — `encrypt()` / `decrypt()` Fernet (clé depuis `settings.encryption_key`)
- [ ] `app/services/ollama_manager.py` — singleton qui garde un `OllamaProvider` initialisé
- [ ] `app/services/thread_service.py` — stub minimal (reply tracking est Phase 3 du roadmap)

### 1.6 Routeurs API manquants (peuvent être stubs initialement)
- [ ] `app/api/activity.py` — GET `/` (activity feed)
- [ ] `app/api/newsletters.py` — GET/POST selon `docs/04-API-ENDPOINTS.md`
- [ ] `app/api/review.py` — GET/POST approve/correct
- [ ] `app/api/senders.py` — GET `/` (top senders)
- [ ] `app/api/threads.py` — GET `/` (stub — Phase 3)
- [ ] `app/api/websocket.py` — endpoint WebSocket (ou stub)

### 1.7 Migration initiale Alembic
- [ ] Vérifier `alembic/env.py` (importe `Base.metadata` de `app/db/base.py`)
- [ ] `alembic revision --autogenerate -m "initial schema"`
- [ ] `alembic upgrade head` contre une Postgres locale

**Validation Phase 1** : `uvicorn app.main:app --reload` démarre et `GET /api/v1/system/health` retourne `{"status": "healthy"}`.

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
