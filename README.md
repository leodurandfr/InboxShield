# InboxShield

Application open source de gestion intelligente d'emails, auto-hébergée et privacy-first. Utilise un LLM local (Ollama) ou cloud (Claude, OpenAI, Mistral) pour classifier, filtrer et protéger automatiquement les boîtes mail via IMAP.

## Stack

- **Backend** : FastAPI 0.115 (async) · SQLAlchemy 2.0 · PostgreSQL 16 · APScheduler · `uv`
- **Frontend** : Vue 3.5 · Vite 7 · Pinia · Tailwind CSS v4 + Shadcn-vue · `pnpm`
- **Infra** : Docker Compose · Nginx (reverse proxy) · Ollama (LLM local)

La spec complète est dans [`docs/`](docs/) — voir en particulier [`00-PROJECT-OVERVIEW.md`](docs/00-PROJECT-OVERVIEW.md) et [`01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md).

## Prérequis — Ollama (LLM local)

Si vous utilisez Ollama (provider local recommandé sur Mac pour le GPU Metal), installez-le **avant** `docker compose up` via le script fourni :

```bash
./scripts/install-ollama.sh          # idempotent (Homebrew sur Mac, install.sh officiel sur Linux)
```

Le script installe Ollama nativement, démarre le service (`brew services` / `systemd`), puis pré-pull le modèle `DEFAULT_OLLAMA_MODEL` défini dans `.env` (défaut `qwen3:8b`).

> **Pourquoi pas Docker pour Ollama sur Mac ?** Le container Linux n'a pas accès au GPU Metal. Ollama natif est 5-10× plus rapide et utilise moins de RAM. Le `docker-compose.mac.yml` pointe donc le backend vers `host.docker.internal:11434`.

Pour désinstaller : `./scripts/uninstall-ollama.sh` (les modèles dans `~/.ollama/` sont conservés).

Si vous utilisez exclusivement un provider cloud (Claude, OpenAI, Mistral), renseignez la clé API correspondante dans `.env` et skippez cette étape.

## Démarrage rapide (Docker)

```bash
# 1. Cloner et configurer
cp .env.example .env
# Générer une clé Fernet et la coller dans ENCRYPTION_KEY :
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. (Si LLM local) Installer Ollama sur l'hôte — voir section « Prérequis »
./scripts/install-ollama.sh

# 3. Lancer la stack
docker compose up -d

# (Mac avec Ollama natif — meilleur pour les perfs GPU Metal)
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d
```

L'UI est servie sur http://localhost:8080 (Nginx → SPA + proxy `/api/v1/*`).
L'API directe est sur http://localhost:8000.

## Développement

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head        # nécessite PostgreSQL accessible
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                      # 146 tests
uv run ruff check . && uv run ruff format --check .
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev                           # http://localhost:5173 (proxy API → :8000)
pnpm type-check
pnpm lint
pnpm build
```

### Migrations Alembic

```bash
cd backend
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## Configuration

Toutes les variables d'environnement sont documentées dans [`.env.example`](.env.example) — voir [`docs/06-DEPLOYMENT.md`](docs/06-DEPLOYMENT.md) pour le détail.

## Structure

```
inboxshield/
├── backend/          # FastAPI + SQLAlchemy + Alembic
├── frontend/         # Vue 3 + Vite + Shadcn-vue
├── docs/             # Spec complète (14 fichiers)
├── docker-compose.yml
├── docker-compose.mac.yml
└── .env.example
```

## Licence

À définir.
