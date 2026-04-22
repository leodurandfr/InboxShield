# InboxShield — Architecture

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                        Utilisateur                            │
│                     (navigateur web)                          │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼───────────────────────────────────┐
│                      Nginx (reverse proxy)                    │
│                                                               │
│   /              → Frontend (Vue SPA)                         │
│   /api/*         → Backend (FastAPI :8000)                    │
└───────┬──────────────────────────────┬───────────────────────┘
        │                              │
        ▼                              ▼
┌───────────────┐          ┌───────────────────────────────────┐
│   Frontend    │          │           Backend (FastAPI)         │
│   Vue 3 SPA   │          │                                    │
│               │          │  ┌─────────────┐ ┌──────────────┐ │
│  • Dashboard  │          │  │  API Routes  │ │  Scheduler   │ │
│  • Rules      │  HTTP    │  │  /api/v1/*   │ │ (APScheduler)│ │
│  • Analytics  │◄────────►│  └──────┬──────┘ └──────┬───────┘ │
│  • Settings   │          │         │               │          │
│  • Review     │          │         ▼               ▼          │
│               │          │  ┌──────────────────────────────┐ │
│               │          │  │         Services              │ │
│               │          │  │                               │ │
│               │          │  │  • IMAPService                │ │
│               │          │  │  • LLMService                 │ │
│               │          │  │  • ClassifierService          │ │
│               │          │  │  • RuleEngine                 │ │
│               │          │  │  • UnsubscribeService         │ │
│               │          │  │  • AnalyticsService           │ │
│               │          │  └──────┬───────────┬───────────┘ │
│               │          │         │           │              │
│               │          └─────────┼───────────┼──────────────┘
└───────────────┘                    │           │
                                     │           │
                          ┌──────────▼──┐  ┌─────▼──────────┐
                          │ PostgreSQL  │  │  LLM Provider   │
                          │             │  │                 │
                          │ • emails    │  │ Ollama (local)  │
                          │ • accounts  │  │    — ou —       │
                          │ • rules     │  │ Claude API      │
                          │ • actions   │  │ OpenAI API      │
                          │ • analytics │  │ Mistral API     │
                          └─────────────┘  └────────────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │  Serveur IMAP   │
                                          │  (GMX, Gmail…)  │
                                          └─────────────────┘
```

## Composants détaillés

### 1. Frontend (Vue 3 + Vite)

Application SPA servie par Nginx. Communique exclusivement avec le backend via API REST.

**Pages principales :**

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Vue d'ensemble : stats, feed d'activité, état de l'inbox |
| Emails | `/emails` | Liste des emails traités, filtrable par catégorie/statut |
| Review Queue | `/review` | Emails en attente de validation manuelle |
| Rules | `/rules` | Éditeur de règles en langage naturel + règles automatiques |
| Analytics | `/analytics` | Graphiques, tendances, top expéditeurs |
| Unsubscribe | `/unsubscribe` | Gestion des newsletters, bulk unsubscribe |
| Settings | `/settings` | Comptes IMAP, config LLM, préférences |

**Principes UI :**
- Tailwind CSS + Shadcn-vue pour le prototypage rapide (remplaçable par un design system custom ultérieurement)
- Responsive (desktop-first, utilisable sur mobile)
- Dark mode supporté
- Temps réel via polling API (ou WebSocket en v2)

### 2. Backend (FastAPI)

Process unique qui contient l'API REST et le scheduler de polling.

#### 2.1 API Routes

```
/api/v1/
├── auth/
│   ├── POST   /login                  # Authentification
│   └── POST   /logout                 # Déconnexion
│
├── accounts/
│   ├── GET    /                        # Liste des comptes IMAP
│   ├── POST   /                        # Ajouter un compte
│   ├── PUT    /{id}                    # Modifier un compte
│   ├── DELETE /{id}                    # Supprimer un compte
│   └── POST   /{id}/test              # Tester la connexion IMAP
│
├── emails/
│   ├── GET    /                        # Liste emails (paginée, filtrable)
│   ├── GET    /{id}                    # Détail d'un email
│   ├── POST   /{id}/classify          # Re-classifier manuellement
│   ├── POST   /{id}/move              # Déplacer vers un dossier
│   └── POST   /{id}/action            # Exécuter une action (archive, delete, flag)
│
├── review/
│   ├── GET    /                        # Emails en review queue
│   ├── POST   /{id}/approve           # Valider la classification proposée
│   └── POST   /{id}/correct           # Corriger la classification
│
├── rules/
│   ├── GET    /                        # Liste des règles
│   ├── POST   /                        # Créer une règle
│   ├── PUT    /{id}                    # Modifier une règle
│   ├── DELETE /{id}                    # Supprimer une règle
│   ├── POST   /{id}/toggle            # Activer/désactiver une règle
│   └── POST   /test                    # Tester une règle sur des emails récents
│
├── analytics/
│   ├── GET    /overview                # Stats globales
│   ├── GET    /volume                  # Volume par période
│   ├── GET    /categories              # Répartition par catégorie
│   ├── GET    /senders                 # Top expéditeurs
│   └── GET    /actions                 # Historique des actions AI
│
├── unsubscribe/
│   ├── GET    /newsletters             # Liste des newsletters détectées
│   ├── POST   /{id}/unsubscribe       # Lancer la désinscription
│   └── POST   /{id}/block             # Bloquer l'expéditeur
│
├── settings/
│   ├── GET    /                        # Configuration actuelle
│   └── PUT    /                        # Mettre à jour la configuration
│
└── system/
    ├── GET    /health                  # Healthcheck
    ├── GET    /status                  # Statut du scheduler, connexion IMAP, Ollama
    └── GET    /logs                    # Logs récents du système
```

#### 2.2 Services

**IMAPService** — Gère toutes les interactions avec les serveurs IMAP.
- Connexion / déconnexion
- Fetch des nouveaux emails (depuis le dernier UID connu)
- Déplacement entre dossiers
- Suppression / archivage
- Flag (lu, important, spam)
- Détection automatique des noms de dossiers selon le provider

**LLMService** — Abstraction au-dessus des différents providers LLM.
- Interface commune pour Ollama, Claude, OpenAI, Mistral
- Construction des prompts (system + user)
- Parsing des réponses structurées (JSON)
- Gestion des timeouts et retries
- Tracking du nombre de tokens utilisés

```python
# Interface commune
class LLMService:
    async def classify(email: EmailData) -> Classification
    async def analyze_phishing(email: EmailData) -> PhishingAnalysis
    async def interpret_rule(rule_text: str, email: EmailData) -> RuleAction
    async def draft_reply(email: EmailData, tone: str) -> str
```

**ClassifierService** — Orchestre la classification d'un email.
1. Vérifie si l'expéditeur est déjà connu → classification directe
2. Sinon, construit le contexte (expéditeur, sujet, extrait body, URLs)
3. Ajoute les few-shot examples des corrections passées
4. Appelle le LLMService
5. Retourne catégorie + score de confiance + explication

**RuleEngine** — Évalue les règles utilisateur sur chaque email.
1. Charge les règles actives depuis la DB
2. Pour les règles structurées (expéditeur = X → action Y), évaluation directe
3. Pour les règles en langage naturel, appel au LLMService pour interprétation
4. Résolution des conflits (priorité des règles)
5. Retourne la liste des actions à exécuter

**UnsubscribeService** — Gère la désinscription des newsletters.
- Parse les headers `List-Unsubscribe` et `List-Unsubscribe-Post`
- Cherche les liens de désinscription dans le body HTML (via BeautifulSoup)
- Exécute la désinscription (HTTP POST ou mailto)
- Suivi du statut (en cours, réussie, échouée)

**AnalyticsService** — Agrège les données pour le dashboard.
- Requêtes SQL optimisées pour les stats
- Cache des calculs fréquents
- Export des données

#### 2.3 Scheduler (APScheduler)

Intégré au process FastAPI, le scheduler exécute les tâches périodiques :

| Job | Fréquence | Description |
|---|---|---|
| `poll_emails` | Configurable (1-30 min) | Fetch des nouveaux emails via IMAP, classification, actions |
| `cleanup_old_logs` | 1x/jour | Suppression des logs de plus de 30 jours |
| `refresh_analytics` | 1x/heure | Recalcul des stats agrégées |
| `check_imap_health` | 5 min | Vérifie que la connexion IMAP est active |

### 3. Base de données (PostgreSQL)

Schéma détaillé dans [02-DATABASE-SCHEMA.md](./02-DATABASE-SCHEMA.md).

**Tables principales :**
- `accounts` — Comptes IMAP configurés (credentials chiffrés)
- `emails` — Emails indexés avec métadonnées et classification
- `classifications` — Résultat de la classification AI par email
- `rules` — Règles de tri (structurées et langage naturel)
- `actions` — Historique des actions effectuées (déplacer, archiver, flag…)
- `sender_profiles` — Profil par expéditeur (catégorie apprise, fréquence, dernier mail)
- `corrections` — Corrections manuelles (pour le few-shot learning)
- `settings` — Configuration globale de l'application
- `newsletters` — Newsletters détectées et leur statut d'abonnement

### 4. LLM Provider

Architecture pluggable pour supporter plusieurs providers :

```
LLMService (interface)
├── OllamaProvider     → localhost:11434  (défaut)
├── AnthropicProvider  → api.anthropic.com
├── OpenAIProvider     → api.openai.com
└── MistralProvider    → api.mistral.ai
```

Chaque provider implémente la même interface. Le choix est fait dans les settings. Un seul provider actif à la fois.

## Flux de données

### Flux principal : polling et classification

```
1. Scheduler déclenche poll_emails
         │
2. IMAPService.fetch_new_emails()
         │ (depuis le dernier UID connu)
         │
3. Pour chaque email :
         │
         ├─► SenderProfile existe ?
         │     OUI → Classification directe (sans LLM)
         │     NON ↓
         │
         ├─► ClassifierService.classify(email)
         │     │
         │     ├─► Construit le prompt (expéditeur, sujet, extrait, URLs)
         │     ├─► Injecte les few-shot examples (corrections passées)
         │     ├─► Appelle LLMService.classify()
         │     └─► Retourne { catégorie, confiance, explication }
         │
         ├─► Confiance >= seuil ?
         │     OUI → RuleEngine.evaluate(email, classification)
         │     │       │
         │     │       └─► Actions automatiques (déplacer, flag, archiver…)
         │     │
         │     NON → Ajout à la Review Queue
         │
4. Sauvegarde en base (email, classification, actions)
         │
5. Log de l'activité
```

### Flux : correction manuelle (apprentissage)

```
1. Utilisateur ouvre la Review Queue
         │
2. Voit l'email + classification proposée + explication
         │
3. Approuve ou corrige
         │
         ├─► Si approuvé : exécute l'action, sauvegarde
         │
         └─► Si corrigé :
               │
               ├─► Met à jour la classification
               ├─► Exécute la nouvelle action
               ├─► Sauvegarde la correction en base
               ├─► Met à jour le SenderProfile
               └─► La correction sera utilisée comme few-shot example
                   pour les futurs emails similaires
```

### Flux : règle en langage naturel

```
1. Utilisateur crée une règle : "Archive les newsletters tech
   que je n'ai pas lues depuis plus d'un mois"
         │
2. Pour chaque email entrant :
         │
         ├─► RuleEngine charge les règles actives
         │
         ├─► Règles structurées → évaluation directe (rapide)
         │
         ├─► Règles en langage naturel →
         │     │
         │     ├─► Construit le prompt : règle + contexte email
         │     ├─► LLMService.interpret_rule()
         │     └─► Retourne { match: bool, action, confiance }
         │
         └─► Résolution des conflits (priorité)
               │
               └─► Exécution des actions
```

## Structure du projet

```
inboxshield/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app + startup/shutdown
│   │   ├── config.py                  # Settings (Pydantic BaseSettings)
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # Dépendances communes (DB session, auth)
│   │   │   ├── accounts.py
│   │   │   ├── emails.py
│   │   │   ├── review.py
│   │   │   ├── rules.py
│   │   │   ├── analytics.py
│   │   │   ├── unsubscribe.py
│   │   │   ├── settings.py
│   │   │   └── system.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── imap_service.py        # Connexion et opérations IMAP
│   │   │   ├── llm_service.py         # Interface commune LLM
│   │   │   ├── classifier.py          # Logique de classification
│   │   │   ├── rule_engine.py         # Évaluation des règles
│   │   │   ├── unsubscribe.py         # Désinscription newsletters
│   │   │   ├── analytics.py           # Agrégation stats
│   │   │   └── scheduler.py           # APScheduler jobs
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Interface abstraite LLMProvider
│   │   │   ├── ollama.py              # Provider Ollama
│   │   │   ├── anthropic.py           # Provider Claude
│   │   │   ├── openai.py              # Provider OpenAI
│   │   │   ├── mistral.py             # Provider Mistral AI
│   │   │   └── prompts.py             # Templates de prompts
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── email.py
│   │   │   ├── classification.py
│   │   │   ├── rule.py
│   │   │   ├── action.py
│   │   │   ├── sender_profile.py
│   │   │   ├── correction.py
│   │   │   └── newsletter.py
│   │   │
│   │   ├── schemas/                   # Pydantic schemas (request/response)
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── email.py
│   │   │   ├── rule.py
│   │   │   └── ...
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── database.py            # Engine + SessionLocal
│   │       └── base.py                # Base model SQLAlchemy
│   │
│   ├── alembic/                       # Migrations DB
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── stores/                    # Pinia stores
│   │   │   ├── emails.ts
│   │   │   ├── rules.ts
│   │   │   ├── analytics.ts
│   │   │   └── settings.ts
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Emails.vue
│   │   │   ├── ReviewQueue.vue
│   │   │   ├── Rules.vue
│   │   │   ├── Analytics.vue
│   │   │   ├── Unsubscribe.vue
│   │   │   └── Settings.vue
│   │   ├── components/
│   │   │   ├── common/                # Composants réutilisables
│   │   │   ├── dashboard/
│   │   │   ├── emails/
│   │   │   ├── rules/
│   │   │   └── analytics/
│   │   ├── composables/               # Logique réutilisable (useApi, useAuth…)
│   │   ├── styles/                    # Design system custom
│   │   └── utils/
│   │
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── nginx.conf
├── .env.example
├── README.md
└── docs/                              # Cette documentation
```

## Docker Compose (production)

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://inboxshield:password@postgres:5432/inboxshield
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - postgres
      - ollama
    restart: always

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: always

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=inboxshield
      - POSTGRES_USER=inboxshield
      - POSTGRES_PASSWORD=password
    restart: always

  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    restart: always

volumes:
  postgres_data:
  ollama_data:
```

## Sécurité

- **Credentials IMAP** : chiffrés en base avec Fernet (clé dérivée d'un secret dans `.env`)
- **API** : authentification par session ou token JWT (single user pour le MVP)
- **CORS** : restreint au domaine du frontend
- **HTTPS** : via Nginx (certificat Let's Encrypt ou self-signed en local)
- **Docker** : containers isolés, réseau interne
- **Pas d'exposition directe** de PostgreSQL ou Ollama vers l'extérieur

---

*Document précédent : [00-PROJECT-OVERVIEW.md](./00-PROJECT-OVERVIEW.md)*
*Document suivant : [02-DATABASE-SCHEMA.md](./02-DATABASE-SCHEMA.md)*
