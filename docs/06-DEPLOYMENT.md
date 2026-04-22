# InboxShield — Deployment

## Architecture Docker

```
┌─────────────────────────────────────────────┐
│               Docker Compose                 │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ frontend │  │ backend  │  │  postgres  │ │
│  │ (nginx)  │  │ (uvicorn)│  │   (16)     │ │
│  │ :80      │  │ :8000    │  │  :5432     │ │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘ │
│       │              │              │        │
│       │   /api/* ──► │ ────────────►│        │
│       │              │              │        │
│       │              │    ┌─────────┘        │
│       │              │    │                  │
│       │              ▼    │                  │
│       │         ┌──────────┐                 │
│       │         │  ollama   │                │
│       │         │  :11434   │                │
│       │         └──────────┘                 │
│       │                                      │
└───────┼──────────────────────────────────────┘
        │
        ▼
   Navigateur (:80)
```

Le frontend Nginx sert les fichiers statiques ET proxy les requêtes `/api/*` vers le backend.

## Docker Compose

```yaml
version: "3.8"

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "8080:80"
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://inboxshield:${DB_PASSWORD}@postgres:5432/inboxshield
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_started
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=inboxshield
      - POSTGRES_USER=inboxshield
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U inboxshield"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    # GPU passthrough si disponible (optionnel, le M4 Pro utilise la mémoire unifiée)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
```

## Dockerfiles

### Backend

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Lancer les migrations puis le serveur
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Frontend

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Nginx config

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API vers le backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # Swagger docs
    location /docs {
        proxy_pass http://backend:8000;
    }
    location /redoc {
        proxy_pass http://backend:8000;
    }
    location /openapi.json {
        proxy_pass http://backend:8000;
    }
}
```

## Variables d'environnement

Fichier `.env` à la racine :

```bash
# Base de données
DB_PASSWORD=changeme_strong_password

# Chiffrement des credentials IMAP
# Générer avec : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key_here

# Optionnel : clés API pour providers cloud
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
MISTRAL_API_KEY=
```

## Installation

### Prérequis

- Docker + Docker Compose
- ~8 GB de RAM disponibles (5 GB Ollama + 2 GB Postgres + 1 GB Backend)
- ~10 GB d'espace disque (modèle LLM + données)

### Démarrage

```bash
# 1. Cloner le repo
git clone https://github.com/xxx/inboxshield.git
cd inboxshield

# 2. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env : DB_PASSWORD, ENCRYPTION_KEY

# 3. Lancer
docker compose up -d

# 4. Installer le modèle LLM (première fois)
docker compose exec ollama ollama pull qwen2.5:7b

# 5. Ouvrir le navigateur
open http://localhost:8080
```

L'app affiche le wizard de setup au premier lancement.

## Développement local (sans Docker)

Pour le développement, on peut lancer chaque service séparément :

```bash
# Terminal 1 : PostgreSQL (si pas Docker)
# Utiliser une instance locale ou Docker standalone

# Terminal 2 : Ollama
ollama serve

# Terminal 3 : Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 4 : Frontend
cd frontend
npm install
npm run dev
```

Le frontend Vite en mode dev proxy automatiquement `/api/*` vers `localhost:8000` (configuré dans `vite.config.ts`).

## Spécificités Mac Mini M4 Pro

Le Mac Mini M4 Pro avec 24 GB de mémoire unifiée est la cible de déploiement principale.

**Ollama sur Mac :** Pas besoin de Docker pour Ollama sur macOS — il tourne nativement et utilise le Metal Performance Shaders (MPS) pour l'accélération GPU. C'est **significativement plus rapide** que dans un container Docker.

**Recommandation :** En production sur le Mac Mini, faire tourner Ollama en natif (via `brew install ollama` + `ollama serve`) et le reste en Docker. Configurer `OLLAMA_BASE_URL=http://host.docker.internal:11434` dans le compose pour que le backend Docker puisse atteindre l'Ollama natif.

```yaml
# docker-compose.mac.yml (override)
services:
  backend:
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # On retire le service ollama, il tourne en natif
```

```bash
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d
```

## Mise à jour

```bash
git pull
docker compose build
docker compose up -d
# Les migrations Alembic s'exécutent automatiquement au démarrage du backend
```

## Sauvegarde

Les données persistantes à sauvegarder :
- **Volume `postgres_data`** — La base de données
- **Fichier `.env`** — Les clés de chiffrement

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U inboxshield inboxshield > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U inboxshield inboxshield < backup_20260224.sql
```

Le volume `ollama_data` n'a pas besoin de backup (les modèles se retéléchargent avec `ollama pull`).

---

*Document précédent : [05-FRONTEND-UI.md](./05-FRONTEND-UI.md)*
*Document suivant : [07-ROADMAP.md](./07-ROADMAP.md)*
