# InboxShield

Application open source de gestion intelligente d'emails, auto-hébergée et privacy-first. Utilise un LLM local (Ollama) ou cloud (Claude, OpenAI, Mistral) pour classifier, filtrer et protéger automatiquement les boîtes mail via IMAP.

## Stack

- **Backend** : FastAPI 0.115 (async) · SQLAlchemy 2.0 · PostgreSQL 16 · APScheduler · `uv`
- **Frontend** : Vue 3.5 · Vite 7 · Pinia · Tailwind CSS v4 + Shadcn-vue · `pnpm`
- **Infra** : Docker Compose · Nginx (reverse proxy) · Ollama (LLM local)

La spec complète est dans [`docs/`](docs/) — voir en particulier [`00-PROJECT-OVERVIEW.md`](docs/00-PROJECT-OVERVIEW.md) et [`01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md).

## Démarrage rapide (Docker)

```bash
# 1. Cloner et configurer
cp .env.example .env
# Générer une clé Fernet et la coller dans ENCRYPTION_KEY :
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Lancer la stack
docker compose up -d

# (Mac avec Ollama natif — meilleur pour les perfs GPU Metal)
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d

# 3. Installer un modèle Ollama
docker compose exec ollama ollama pull qwen2.5:7b
# ou, Mac natif : ollama pull qwen2.5:7b
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
