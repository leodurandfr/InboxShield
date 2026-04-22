# InboxShield — Roadmap

## Phase 1 — MVP

> Objectif : une app fonctionnelle qui classe les emails et exécute des actions de base.

### Backend

- [ ] Setup projet Python FastAPI + structure de fichiers
- [ ] Modèles SQLAlchemy + migrations Alembic (toutes les tables)
- [ ] Service IMAP : connexion, test, découverte dossiers, fetch, move, flag
- [ ] Auto-détection provider IMAP (map domaine → host/port)
- [ ] Service LLM : interface abstraite + OllamaProvider
- [ ] Prompt de classification + parsing JSON tolérant
- [ ] ClassifierService : pipeline sender_profile → rules → LLM
- [ ] RuleEngine : évaluation des règles structurées
- [ ] Scheduler APScheduler : poll_emails, cleanup, health check
- [ ] Gestion du premier fetch (onboarding, 100 emails)
- [ ] Review queue : approve, correct, mise à jour sender_profile
- [ ] Few-shot learning : injection des corrections dans le prompt
- [ ] Sender profiles : création, mise à jour, classification directe (count >= 5, > 80%)
- [ ] Activity logs : création d'événements
- [ ] Chiffrement Fernet des credentials IMAP
- [ ] API endpoints : accounts, emails, review, rules, settings, system, activity

### Frontend

- [ ] Setup projet Vue 3 + Vite + Tailwind + Shadcn-vue
- [ ] Layout : sidebar + header + main content
- [ ] Stores Pinia : accounts, emails, review, rules, settings, activity, system
- [ ] Composable `useApi` (client HTTP typé)
- [ ] Composable `usePolling` (rafraîchissement auto)
- [ ] **Setup wizard** : ajout compte, config LLM, premier scan, progression
- [ ] **Dashboard** : KPI cards + activity feed + bouton "forcer polling"
- [ ] **Emails** : liste paginée + filtres + détail email + classification
- [ ] **Review queue** : carte par email, approve/correct, groupement par expéditeur
- [ ] **Rules** : liste, création/édition règle structurée, condition builder, action picker, drag-and-drop priorité
- [ ] **Settings** : comptes (CRUD, test connexion), LLM (provider, modèle, test), classification (seuil, auto_mode), rétention
- [ ] Composants partagés : ConfidenceBadge, CategoryBadge, StatusBadge, EmptyState
- [ ] Dark mode
- [ ] Toasts de notification

### Infra

- [ ] Docker Compose : backend + frontend + postgres + ollama
- [ ] Dockerfiles : backend (Python) + frontend (Node build + Nginx)
- [ ] Nginx : SPA fallback + proxy /api/*
- [ ] docker-compose.mac.yml (Ollama natif)
- [ ] `.env.example` avec documentation des variables
- [ ] README.md avec instructions d'installation

### Critères de validation Phase 1

- [ ] Ajouter un compte GMX, tester la connexion, fetch réussi
- [ ] Les 100 derniers emails sont classifiés par Ollama (qwen2.5:7b)
- [ ] Les emails sont triés dans les bons dossiers IMAP
- [ ] La review queue fonctionne : approve/correct met à jour la DB et IMAP
- [ ] Les corrections améliorent les futures classifications (few-shot)
- [ ] Les sender_profiles se construisent et classent sans LLM après 5 classifications identiques
- [ ] Le polling récupère les nouveaux emails automatiquement
- [ ] Le dashboard affiche les KPIs et le feed d'activité en temps réel

---

## Phase 2 — Fonctionnalités avancées

> Objectif : intelligence plus poussée, newsletters, analytics.

### Backend

- [ ] Provider LLM cloud : AnthropicProvider, OpenAIProvider, MistralProvider
- [ ] Règles en langage naturel : interprétation par le LLM
- [ ] Détection phishing avancée : analyse heuristique des URLs (homoglyphes, display ≠ href, raccourcisseurs)
- [ ] Table `email_urls` : extraction et analyse des URLs
- [ ] Quarantaine automatique des phishing
- [ ] Service Unsubscribe : extraction List-Unsubscribe, désinscription HTTP/mailto
- [ ] Service Newsletters : détection, stats de lecture, fréquence
- [ ] Analytics : endpoints overview, categories, volume, top-senders, performance
- [ ] Cache analytics (rafraîchissement horaire)
- [ ] Cold email detection (bonus)

### Frontend

- [ ] **Newsletters** : liste avec stats (reçus, lus, taux, fréquence), désinscription un clic, désinscription en masse
- [ ] **Senders** : liste des profils expéditeurs, détail avec category_stats, bloquer/débloquer
- [ ] **Analytics** : KPIs, répartition catégories (donut chart), volume quotidien (bar chart), top expéditeurs, performances système
- [ ] **Rules** : éditeur de règles en langage naturel (textarea + preview)
- [ ] Détail email enrichi : URLs suspectes avec indicateurs visuels, phishing_reasons
- [ ] Notifications améliorées : alerte phishing dans le header

### Critères de validation Phase 2

- [ ] Désinscription réussie via List-Unsubscribe (HTTP POST)
- [ ] Les URLs suspectes sont détectées et affichées
- [ ] Les analytics montrent des données cohérentes
- [ ] Les règles en langage naturel fonctionnent (interprétation LLM)
- [ ] Switch entre Ollama et un provider cloud fonctionne

---

## Phase 3 — Features avancées

> Objectif : reply tracking, multi-comptes enrichi, export.

### Backend

- [ ] Email threading : construction des threads via In-Reply-To/References
- [ ] Reply tracking : détection awaiting_response / awaiting_reply
- [ ] Analytics avancées : tendances, heatmap horaire, matrice de confusion
- [ ] Export CSV/PDF des données
- [ ] Apprentissage avancé : ajustement dynamique du seuil de confiance basé sur le taux de correction

### Frontend

- [ ] **Threads** : vue conversations, indicateurs "en attente", actions résoudre/ignorer
- [ ] **Analytics avancées** : matrice de confusion, tendances, heatmap
- [ ] Export : boutons CSV/PDF dans analytics et emails
- [ ] Multi-comptes enrichi : switch de compte dans le header, stats comparatives
- [ ] Responsive mobile amélioré

---

## Idées futures (non planifiées)

- **WebSocket** pour le temps réel (remplacer le polling frontend)
- **Résumé AI** des emails longs (TL;DR)
- **Réponse suggérée** par le LLM pour les emails importants
- **Application mobile** (ou PWA)
- **Multi-utilisateur** avec authentification JWT
- **Plugin navigateur** pour afficher les catégories dans le webmail
- **Intégration calendrier** (détecter les invitations dans les emails)
- **Webhook** pour les intégrations externes (Slack, Discord, Home Assistant…)

---

*Document précédent : [06-DEPLOYMENT.md](./06-DEPLOYMENT.md)*
