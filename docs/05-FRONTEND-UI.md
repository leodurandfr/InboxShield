# InboxShield — Frontend & UI

## Stack

- **Vue 3** (Composition API + `<script setup>`)
- **Vite** (build tool)
- **Vue Router** (routing SPA)
- **Pinia** (state management)
- **Tailwind CSS + Shadcn-vue** (prototypage rapide, remplaçable par un design system custom)
- **Lucide Icons** (icônes)
- **Chart.js** ou **Apache ECharts** (graphiques analytics)
- **date-fns** (dates)

## Structure du projet

```
frontend/
├── src/
│   ├── App.vue
│   ├── main.ts
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   ├── accounts.ts
│   │   ├── emails.ts
│   │   ├── review.ts
│   │   ├── rules.ts
│   │   ├── newsletters.ts
│   │   ├── analytics.ts
│   │   ├── activity.ts
│   │   ├── settings.ts
│   │   └── system.ts
│   ├── composables/
│   │   ├── useApi.ts            # Wrapper fetch/axios
│   │   ├── usePolling.ts        # Auto-refresh périodique
│   │   ├── useToast.ts          # Notifications
│   │   └── usePagination.ts     # Pagination réutilisable
│   ├── views/
│   │   ├── DashboardView.vue
│   │   ├── EmailsView.vue
│   │   ├── ReviewView.vue
│   │   ├── RulesView.vue
│   │   ├── NewslettersView.vue
│   │   ├── SendersView.vue
│   │   ├── ThreadsView.vue
│   │   ├── AnalyticsView.vue
│   │   ├── SettingsView.vue
│   │   └── SetupView.vue        # Onboarding (ajout premier compte)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppSidebar.vue
│   │   │   ├── AppHeader.vue
│   │   │   └── AppLayout.vue
│   │   ├── emails/
│   │   │   ├── EmailList.vue
│   │   │   ├── EmailRow.vue
│   │   │   ├── EmailDetail.vue
│   │   │   └── EmailFilters.vue
│   │   ├── review/
│   │   │   ├── ReviewCard.vue
│   │   │   ├── ReviewQueue.vue
│   │   │   └── CategorySelect.vue
│   │   ├── rules/
│   │   │   ├── RuleEditor.vue
│   │   │   ├── ConditionBuilder.vue
│   │   │   └── ActionPicker.vue
│   │   ├── newsletters/
│   │   │   ├── NewsletterList.vue
│   │   │   └── NewsletterCard.vue
│   │   ├── analytics/
│   │   │   ├── KpiCards.vue
│   │   │   ├── CategoryChart.vue
│   │   │   ├── VolumeChart.vue
│   │   │   └── TopSenders.vue
│   │   ├── dashboard/
│   │   │   ├── ActivityFeed.vue
│   │   │   └── QuickStats.vue
│   │   ├── settings/
│   │   │   ├── AccountForm.vue
│   │   │   ├── LlmConfig.vue
│   │   │   └── GeneralConfig.vue
│   │   └── shared/
│   │       ├── ConfidenceBadge.vue
│   │       ├── CategoryBadge.vue
│   │       ├── StatusBadge.vue
│   │       └── EmptyState.vue
│   └── lib/
│       ├── api.ts               # Client API typé
│       ├── types.ts             # Types TypeScript
│       └── utils.ts             # Helpers
├── index.html
├── tailwind.config.js
├── components.json              # Config shadcn-vue
├── tsconfig.json
├── vite.config.ts
└── package.json
```

## Routes

| Route | Vue | Description | Phase |
|---|---|---|---|
| `/` | DashboardView | Dashboard principal + feed | 1 |
| `/setup` | SetupView | Onboarding premier compte | 1 |
| `/emails` | EmailsView | Liste des emails classifiés | 1 |
| `/review` | ReviewView | File de review | 1 |
| `/rules` | RulesView | Gestion des règles | 1 |
| `/newsletters` | NewslettersView | Gestion des newsletters | 2 |
| `/senders` | SendersView | Profils expéditeurs | 2 |
| `/threads` | ThreadsView | Reply tracking | 3 |
| `/analytics` | AnalyticsView | Statistiques détaillées | 2 |
| `/settings` | SettingsView | Configuration | 1 |

## Layout

```
┌─────────────────────────────────────────────────────┐
│  AppHeader (logo, compte actif, healthcheck status)  │
├────────────┬────────────────────────────────────────┤
│            │                                        │
│  Sidebar   │              Main Content              │
│            │                                        │
│  Dashboard │                                        │
│  Emails    │                                        │
│  Review (5)│                                        │
│  Rules     │                                        │
│  Letters   │                                        │
│  Senders   │                                        │
│  Threads   │                                        │
│  Analytics │                                        │
│            │                                        │
│  ───────   │                                        │
│  Settings  │                                        │
│            │                                        │
├────────────┴────────────────────────────────────────┤
│  (Toast notifications en bas à droite)              │
└─────────────────────────────────────────────────────┘
```

La sidebar affiche des badges dynamiques :
- **Review (5)** — Nombre d'emails en review queue
- **Threads (2)** — Nombre de threads en attente de réponse

## Pages principales

### 1. Dashboard (`/`)

Première page vue par l'utilisateur. Résumé de l'état de toutes les boîtes.

**Composants :**
- `QuickStats` — Cartes KPI (emails aujourd'hui, review pending, phishing bloqués, taux auto)
- `ActivityFeed` — Flux chronologique des 20 derniers événements
- Bouton "Forcer le polling" pour une actualisation immédiate

**Rafraîchissement :** Polling API toutes les 30 secondes via `usePolling`.

### 2. Emails (`/emails`)

Liste paginée de tous les emails classifiés avec filtres.

**Composants :**
- `EmailFilters` — Barre de filtres : compte, catégorie, statut, date, recherche texte
- `EmailList` + `EmailRow` — Tableau avec : expéditeur, sujet, date, catégorie (badge couleur), confiance, dossier
- `EmailDetail` — Panel latéral ou modal avec les détails complets : classification, explication LLM, URLs extraites, actions disponibles

**Interactions :**
- Clic sur un email → ouvre le détail
- Actions rapides : déplacer, re-classifier, bloquer l'expéditeur
- Sélection multiple → actions en masse

### 3. Review Queue (`/review`)

File d'attente des emails à faible confiance.

**Composants :**
- `ReviewQueue` — Liste des emails en review, triés par confiance croissante
- `ReviewCard` — Carte par email : expéditeur, sujet, extrait, catégorie proposée + confidence bar, explication
- `CategorySelect` — Dropdown des catégories pour la correction
- Actions : Approuver (✓), Corriger (✎), Ignorer (⊘)
- En tête : "Tout approuver" / "Approuver par catégorie"

**Groupement par expéditeur :** Si 5 emails du même expéditeur sont en review → afficher un groupe avec "Tout approuver pour cet expéditeur".

### 4. Rules (`/rules`)

Gestion des règles de tri.

**Composants :**
- Liste des règles avec drag-and-drop pour réordonner les priorités
- `RuleEditor` — Formulaire de création/édition
- `ConditionBuilder` — UI visuelle pour construire les conditions (champ → opérateur → valeur, boutons AND/OR)
- `ActionPicker` — Sélection des actions (déplacer vers…, marquer comme…, bloquer)
- Toggle actif/inactif par règle
- Compteur de matchs et "Dernier match il y a…"

### 5. Newsletters (`/newsletters`)

**Composants :**
- `NewsletterList` — Tableau : nom, expéditeur, reçus, lus, taux, fréquence, statut, action
- `NewsletterCard` — Vue carte alternative
- Indicateurs visuels : badge rouge (jamais lu), vert (actif), orange (très fréquent)
- Boutons : Se désabonner, Désinscription en masse ("Tout ce que je ne lis pas")
- Filtres : statut (abonné/désabonné), taux de lecture

### 6. Settings (`/settings`)

**Sections :**
- **Comptes** — Liste des comptes, ajouter/modifier/supprimer, tester la connexion
- **LLM** — Provider, modèle (dropdown des modèles Ollama), température, test de connexion
- **Classification** — Seuil de confiance (slider), auto_mode (toggle), excerpt length
- **Rétention** — Durées de rétention
- **Sécurité** — Mot de passe de l'app
- **Système** — Healthcheck, version, forcer le nettoyage

### 7. Setup (`/setup`)

Wizard d'onboarding au premier lancement (aucun compte configuré) :

1. **Bienvenue** — Explication rapide d'InboxShield
2. **Ajouter un compte** — Email + mot de passe, test de connexion, mapping dossiers
3. **Configurer le LLM** — Vérifier qu'Ollama fonctionne, sélectionner le modèle
4. **Premier scan** — Lancer le fetch initial des 100 derniers emails, afficher la progression
5. **Terminé** — Redirection vers le dashboard

## Composants partagés

### `ConfidenceBadge`

Affiche le score de confiance avec une couleur :
- `>= 0.8` → Vert
- `>= 0.6` → Orange
- `< 0.6` → Rouge

### `CategoryBadge`

Badge coloré par catégorie :
- `important` → Rouge
- `work` → Bleu
- `personal` → Violet
- `newsletter` → Cyan
- `promotion` → Orange
- `notification` → Gris
- `spam` → Gris foncé
- `phishing` → Rouge vif + icône ⚠
- `transactional` → Vert

### `EmptyState`

Illustration + message quand une liste est vide ("Aucun email en review — tout est trié !").

## Stores Pinia

Chaque store encapsule les appels API et le state local :

```typescript
// stores/review.ts
export const useReviewStore = defineStore('review', () => {
  const items = ref<ReviewItem[]>([])
  const total = ref(0)
  const loading = ref(false)

  async function fetch(filters?: ReviewFilters) {
    loading.value = true
    const data = await api.get('/review', { params: filters })
    items.value = data.items
    total.value = data.total
    loading.value = false
  }

  async function approve(emailId: string) {
    await api.post(`/review/${emailId}/approve`)
    items.value = items.value.filter(i => i.email.id !== emailId)
    total.value--
  }

  async function correct(emailId: string, category: string, note?: string) {
    await api.post(`/review/${emailId}/correct`, { corrected_category: category, note })
    items.value = items.value.filter(i => i.email.id !== emailId)
    total.value--
  }

  return { items, total, loading, fetch, approve, correct }
})
```

## Dark mode

Supporté via Tailwind (`dark:` prefix) + classe `dark` sur `<html>`. Toggle dans le header. Préférence sauvegardée en localStorage.

## Responsive

Desktop-first. La sidebar se collapse en menu hamburger sur mobile. Les tableaux passent en vue carte sur petit écran.

---

*Document précédent : [04-API-ENDPOINTS.md](./04-API-ENDPOINTS.md)*
*Document suivant : [06-DEPLOYMENT.md](./06-DEPLOYMENT.md)*
