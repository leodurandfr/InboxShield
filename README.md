# InboxShield

Application open source de gestion intelligente d'emails, auto-hébergée et privacy-first. Utilise un LLM local (Ollama) ou cloud (Claude, OpenAI, Mistral) pour classifier, filtrer et protéger automatiquement les boîtes mail via IMAP.

## Stack

- **Backend** : FastAPI 0.115 (async) · SQLAlchemy 2.0 · PostgreSQL 16 · APScheduler · `uv`
- **Frontend** : Vue 3.5 · Vite 7 · Pinia · Tailwind CSS v4 + Shadcn-vue · `pnpm`
- **Infra** : Docker Compose · Nginx (reverse proxy) · Ollama (LLM local)

La spec complète est dans [`docs/`](docs/) — voir en particulier [`00-PROJECT-OVERVIEW.md`](docs/00-PROJECT-OVERVIEW.md) et [`01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md).

## Options LLM

InboxShield sait parler à trois familles de providers. Choisissez celle qui correspond à votre matériel et vos contraintes de confidentialité :

| Option                | OS supportés    | Accélération | Privacy | Setup | Coût | Quand choisir                                                                 |
| --------------------- | --------------- | ------------ | ------- | ----- | ---- | ----------------------------------------------------------------------------- |
| **Ollama natif**      | macOS, Linux    | GPU (Metal / CUDA) | Totale  | 1 script, ~10 min | Gratuit (hors matériel) | Mac Apple Silicon, Linux avec GPU, données sensibles (prod recommandée). |
| **Ollama container**  | Linux uniquement | CPU (pas de Metal dans Docker) | Totale  | `docker compose up` | Gratuit | Dev rapide sur Linux, tests, environnements éphémères — **lent sans GPU**. |
| **Cloud** (Claude, OpenAI, Mistral) | Tous | N/A (API distante) | Vos emails sortent vers le provider | Clé API dans `.env` | Paiement à l'usage | Pas de GPU local, besoin d'un modèle frontier, setup zéro. |

> **Pourquoi pas Docker pour Ollama sur Mac ?** Le container Linux n'a pas accès au GPU Metal d'Apple Silicon. Ollama natif est 5-10× plus rapide et utilise moins de RAM. Le `docker-compose.mac.yml` retire donc le service `ollama` et pointe le backend vers `host.docker.internal:11434`.

## Quick start

```bash
# 1. Cloner et configurer l'environnement
git clone <votre-fork> inboxshield && cd inboxshield
cp .env.example .env
# Générer une clé Fernet et la coller dans ENCRYPTION_KEY :
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Installer un provider LLM (choisir une option)
./scripts/install-ollama.sh                # Ollama natif (Mac / Linux, recommandé)
# — ou renseigner ANTHROPIC_API_KEY / OPENAI_API_KEY / MISTRAL_API_KEY dans .env

# 3. Lancer la stack
docker compose up -d                                                    # Linux (Ollama container par défaut)
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d    # Mac (Ollama natif)
```

L'UI est servie sur http://localhost:8080 (Nginx → SPA + proxy `/api/v1/*`), l'API directe sur http://localhost:8000.

### À propos du script d'installation Ollama

`./scripts/install-ollama.sh` est idempotent : Homebrew sur Mac, `install.sh` officiel sur Linux. Il installe le binaire, démarre le service (`brew services` / `systemd`), puis pré-pull le modèle défini par `DEFAULT_OLLAMA_MODEL` (défaut `qwen3:8b`). Re-lancez-le sans crainte pour upgrader ou vérifier l'état.

Pour désinstaller : `./scripts/uninstall-ollama.sh` (les modèles dans `~/.ollama/` sont conservés).

La supervision du daemon (modèles chargés en RAM, disque utilisé, déchargement manuel) se fait depuis l'onglet **Paramètres** de l'UI lorsque le provider vaut `ollama`.

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
