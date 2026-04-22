# InboxShield — Project Overview

## Vision

InboxShield est une application open source de gestion intelligente d'emails, auto-hébergée et privacy-first. Elle utilise un LLM local (Ollama) pour classifier, filtrer et protéger automatiquement votre boîte mail contre le spam, le phishing et le bruit, tout en offrant un dashboard moderne pour piloter l'ensemble.

**Contrairement aux solutions existantes** (Inbox Zero, SaneBox…) qui dépendent d'APIs cloud et sont limitées à Gmail/Outlook, InboxShield fonctionne avec **n'importe quel provider IMAP** (GMX, Gmail, Outlook, Yahoo, ProtonMail…) et **aucune donnée ne quitte votre réseau**.

## Principes fondateurs

- **Privacy-first** — Toutes les données restent locales. Le LLM tourne sur votre machine via Ollama. Aucun appel à des APIs cloud.
- **Provider-agnostic** — Fonctionne avec tout provider supportant IMAP/SMTP. Pas de dépendance à Gmail ou Outlook.
- **Intelligent par défaut** — Même sans règle configurée, l'app analyse et classifie chaque email entrant (spam, phishing, newsletter, important…).
- **Personnalisable** — Règles en langage naturel pour adapter le comportement à votre workflow.
- **Auto-hébergé** — Tourne sur votre infrastructure (Mac Mini, NAS, VPS…) via Docker.

## Positionnement vs existants

| | InboxShield | Inbox Zero | SaneBox | ClearMail |
|---|---|---|---|---|
| Provider | Tout IMAP | Gmail/Outlook | Gmail/Outlook | Gmail (IMAP) |
| LLM | Local (Ollama) ou Cloud (Claude, OpenAI, Mistral) | Cloud (OpenAI/Anthropic) | Propriétaire | LM Studio |
| Anti-phishing | ✅ Analyse LLM active | ❌ | ❌ | ❌ |
| Règles naturelles | ✅ | ✅ | ❌ | ✅ (config YAML) |
| Dashboard web | ✅ | ✅ | ✅ | ❌ |
| Privacy | Local par défaut (cloud optionnel) | Données envoyées au cloud | Cloud | Local |
| Open source | ✅ | ✅ | ❌ | ✅ |
| Multi-comptes | ✅ | ✅ | ✅ | ❌ |

## Stack technique

### Backend — Python FastAPI

- **Framework** : FastAPI (async, performant, auto-documentation OpenAPI)
- **IMAP** : `imap_tools` (connexion, lecture, déplacement, suppression)
- **SMTP** : `aiosmtplib` (envoi d'emails)
- **LLM** : SDK Ollama Python (modèle local) + support APIs cloud (Anthropic Claude, OpenAI, Mistral AI) via configuration
- **Scheduling** : `APScheduler` (polling IMAP périodique, intégré au process FastAPI)
- **ORM** : SQLAlchemy + Alembic (migrations)
- **Parsing HTML** : `beautifulsoup4` (extraction liens unsubscribe, nettoyage contenu)
- **Validation** : Pydantic (modèles de données, validation requêtes API)

### Frontend — Vue 3 + Vite (SPA)

- **Framework** : Vue 3 (Composition API)
- **Build** : Vite
- **State management** : Pinia
- **UI** : Tailwind CSS + Shadcn-vue (prototypage rapide, remplaçable par un design system custom)
- **Routing** : Vue Router
- **HTTP client** : `ofetch` ou `axios`
- **Charts** : Chart.js ou Apache ECharts (analytics)

### Infrastructure

- **Base de données** : PostgreSQL 16
- **LLM** : Ollama (local, par défaut) ou API cloud (Claude, OpenAI, Mistral AI) — configurable dans les settings
- **Conteneurisation** : Docker + Docker Compose
- **Reverse proxy** : Nginx (sert le SPA + proxy vers l'API)

### Architecture déploiement (Docker Compose)

```yaml
services:
  backend:    # FastAPI + APScheduler (API + worker dans le même process)
  frontend:   # Vue SPA servie par Nginx
  postgres:   # Base de données
  ollama:     # LLM local
```

Un seul `docker-compose up` pour tout lancer. Pas de worker séparé.

## Modèles LLM supportés

### Modèles locaux (Ollama) — Privacy-first, recommandé

Pour un Mac Mini M4 Pro :

| Modèle | Taille | Vitesse | Usage |
|---|---|---|---|
| `qwen2.5:7b` | 4.7 GB | ~40 tok/s | **Recommandé** — Meilleur rapport qualité/vitesse pour la classification |
| `mistral:7b` | 4.1 GB | ~45 tok/s | Alternative solide, bon en français |
| `qwen2.5:14b` | 9.0 GB | ~20 tok/s | Plus précis, plus lent |
| `llama3:8b` | 4.7 GB | ~35 tok/s | Bon généraliste |

### APIs cloud (optionnel) — Pour plus de puissance

| Provider | Modèle | Notes |
|---|---|---|
| Anthropic | Claude Sonnet / Haiku | Très bon en classification et analyse |
| OpenAI | GPT-4o / GPT-4o-mini | Largement utilisé, bien documenté |
| Mistral AI | Mistral Small / Large | Modèles européens, bon en français |

Le choix local vs cloud est configurable dans les settings. Le mode local est le défaut (privacy-first).

## Target hardware

- **Production** : Mac Mini M4 Pro (Docker Desktop, "Start when you log in", restart: always)
- **Développement** : MacBook Pro / toute machine avec Docker
- **Alternative** : NAS Synology (Docker), VPS Linux, Raspberry Pi 5

## Providers IMAP supportés (cibles)

| Provider | IMAP Host | SMTP Host | Notes |
|---|---|---|---|
| GMX | `imap.gmx.net:993` | `mail.gmx.net:587` | Provider principal cible |
| Gmail | `imap.gmail.com:993` | `smtp.gmail.com:587` | Nécessite App Password |
| Outlook | `outlook.office365.com:993` | `smtp.office365.com:587` | |
| Yahoo | `imap.mail.yahoo.com:993` | `smtp.mail.yahoo.com:587` | |
| ProtonMail | `127.0.0.1:1143` | `127.0.0.1:1025` | Via ProtonMail Bridge |
| Fastmail | `imap.fastmail.com:993` | `smtp.fastmail.com:587` | |
| Custom | Configurable | Configurable | Tout serveur IMAP/SMTP |

## Fonctionnalités principales (résumé)

Les détails de chaque fonctionnalité sont documentés dans les fichiers `03-FEATURES/`.

1. **Classification AI automatique** — Chaque email est analysé et catégorisé (Important, Travail, Personnel, Newsletter, Promotion, Spam, Phishing, Notification)
2. **Détection spam & phishing** — Analyse active des URLs, domaines, patterns d'arnaque, urgence artificielle
3. **Règles en langage naturel** — "Archive les newsletters que je ne lis jamais", "Tout ce qui vient d'Amazon → Important"
4. **Review queue** — Les emails classifiés avec un faible score de confiance sont mis en attente de validation manuelle. Les corrections alimentent un système d'apprentissage (mémorisation expéditeurs + few-shot prompting) pour améliorer les futures classifications.
5. **Bulk unsubscribe** — Scan des newsletters, stats par expéditeur, désinscription en un clic
6. **Reply tracking** — Suivi des emails en attente de réponse (envoyés et reçus)
7. **Analytics** — Volume, top expéditeurs, répartition par catégorie, tendances
8. **Multi-comptes** — Gérer plusieurs boîtes mail IMAP dans une seule interface
9. **Dashboard** — Vue d'ensemble en temps réel de l'activité et des actions AI

## Roadmap phases

### Phase 1 — MVP (Core)
- Connexion IMAP (single account)
- Classification AI par Ollama (catégories de base)
- Règles de tri automatiques (catégorie → dossier IMAP)
- Dashboard avec feed d'activité
- Review queue
- Settings (IMAP, Ollama, fréquence polling)

### Phase 2 — Intelligence
- Règles en langage naturel
- Détection phishing avancée
- Cold email blocker
- Bulk unsubscribe
- Analytics de base
- Notifications (email en quarantaine, phishing détecté)

### Phase 3 — Complet
- Multi-comptes
- Reply tracking
- Analytics avancées
- Export / rapports
- Mode apprentissage avancé (few-shot prompting basé sur les corrections utilisateur)

---

*Document suivant : [01-ARCHITECTURE.md](./01-ARCHITECTURE.md)*
