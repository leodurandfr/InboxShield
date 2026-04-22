# InboxShield — API Endpoints

## Vue d'ensemble

API REST FastAPI. Préfixe : `/api/v1`. Réponses en JSON. Documentation auto-générée via Swagger UI (`/docs`) et ReDoc (`/redoc`).

## Authentification

En Phase 1 (single-user, auto-hébergé), l'authentification est optionnelle :
- Si `settings.app_password` est défini → auth par session cookie (login avec mot de passe)
- Si non défini → accès libre (réseau local uniquement)

En Phase 3, un système JWT pourrait être ajouté pour le multi-utilisateur.

---

## Comptes — `/api/v1/accounts`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/accounts` | Liste tous les comptes |
| `POST` | `/accounts` | Ajouter un compte |
| `GET` | `/accounts/{id}` | Détail d'un compte |
| `PUT` | `/accounts/{id}` | Modifier un compte |
| `DELETE` | `/accounts/{id}` | Supprimer un compte |
| `POST` | `/accounts/test-connection` | Tester une connexion IMAP (avant sauvegarde) |
| `POST` | `/accounts/{id}/poll` | Forcer un polling immédiat |
| `GET` | `/accounts/{id}/folders` | Lister les dossiers IMAP |
| `PUT` | `/accounts/{id}/folder-mapping` | Mettre à jour le mapping des dossiers |
| `PUT` | `/accounts/{id}/category-actions` | Configurer catégorie → dossier IMAP |

### `POST /accounts`

```json
// Request
{
  "name": "GMX Personnel",
  "email": "leo@gmx.fr",
  "password": "xxx",
  "imap_host": "imap.gmx.com",    // Optionnel si auto-détecté
  "imap_port": 993                  // Optionnel si auto-détecté
}

// Response 201
{
  "id": "uuid",
  "name": "GMX Personnel",
  "email": "leo@gmx.fr",
  "provider": "gmx",
  "is_active": true,
  "folder_mapping": {
    "inbox": "INBOX",
    "sent": "Sent",
    "spam": "Spam",
    "trash": "Trash"
  },
  "created_at": "2026-02-24T10:00:00Z"
}
```

### `POST /accounts/test-connection`

Teste la connexion sans sauvegarder. Retourne les dossiers disponibles si succès.

```json
// Request
{
  "email": "leo@gmx.fr",
  "password": "xxx",
  "imap_host": "imap.gmx.com",
  "imap_port": 993
}

// Response 200
{
  "success": true,
  "provider": "gmx",
  "folders": ["INBOX", "Sent", "Drafts", "Spam", "Trash"],
  "suggested_mapping": {
    "inbox": "INBOX",
    "sent": "Sent",
    "spam": "Spam",
    "trash": "Trash"
  }
}

// Response 400 (échec)
{
  "success": false,
  "error": "AUTH_FAILED",
  "message": "Identifiants incorrects"
}
```

---

## Emails — `/api/v1/emails`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/emails` | Liste paginée des emails |
| `GET` | `/emails/{id}` | Détail d'un email (métadonnées + classification) |
| `POST` | `/emails/{id}/move` | Déplacer un email |
| `POST` | `/emails/{id}/flag` | Changer un flag (lu, important…) |
| `POST` | `/emails/{id}/reclassify` | Forcer une re-classification LLM |
| `POST` | `/emails/bulk-action` | Action en masse sur plusieurs emails |

### `GET /emails`

```
GET /emails?account_id=uuid&category=newsletter&page=1&per_page=20&sort=-date
```

**Filtres query params :**
- `account_id` — Filtrer par compte
- `category` — Filtrer par catégorie
- `processing_status` — pending, classified, failed…
- `is_read` — true/false
- `is_phishing` — true/false
- `folder` — Dossier IMAP
- `from_address` — Recherche partielle
- `subject` — Recherche partielle
- `date_from` / `date_to` — Plage de dates
- `sort` — Tri : `date`, `-date` (desc), `from_address`, `category`
- `page` / `per_page` — Pagination (défaut : page=1, per_page=20)

```json
// Response 200
{
  "items": [
    {
      "id": "uuid",
      "account_id": "uuid",
      "from_address": "newsletter@figma.com",
      "from_name": "Figma",
      "subject": "What's new in Figma — February 2026",
      "date": "2026-02-24T08:30:00Z",
      "folder": "Newsletters",
      "is_read": true,
      "has_attachments": false,
      "processing_status": "classified",
      "classification": {
        "category": "newsletter",
        "confidence": 0.94,
        "status": "auto",
        "classified_by": "sender_profile"
      }
    }
  ],
  "total": 1250,
  "page": 1,
  "per_page": 20,
  "pages": 63
}
```

### `POST /emails/bulk-action`

```json
// Request
{
  "email_ids": ["uuid1", "uuid2", "uuid3"],
  "action": {
    "type": "move",
    "folder": "Archive"
  }
}

// Response 200
{
  "success": 3,
  "failed": 0,
  "results": [
    { "email_id": "uuid1", "status": "success" },
    { "email_id": "uuid2", "status": "success" },
    { "email_id": "uuid3", "status": "success" }
  ]
}
```

---

## Review Queue — `/api/v1/review`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/review` | Emails en attente de review |
| `POST` | `/review/{email_id}/approve` | Approuver la classification |
| `POST` | `/review/{email_id}/correct` | Corriger la classification |
| `POST` | `/review/bulk-approve` | Approuver en masse |
| `GET` | `/review/stats` | Stats de la review queue |

### `GET /review`

```
GET /review?account_id=uuid&group_by=sender&sort=confidence
```

**Filtres :**
- `account_id` — Par compte
- `group_by` — `sender` (regroupe par expéditeur) ou `none`
- `sort` — `confidence` (croissant, les moins sûrs en premier), `-date`

```json
// Response 200
{
  "items": [
    {
      "email": {
        "id": "uuid",
        "from_address": "promo@unknown-shop.com",
        "subject": "Offre spéciale -50%",
        "date": "2026-02-24T07:00:00Z",
        "body_excerpt": "Profitez de notre offre exclusive..."
      },
      "classification": {
        "category": "promotion",
        "confidence": 0.55,
        "explanation": "Email commercial avec offre promotionnelle, mais l'expéditeur est inconnu",
        "is_spam": false,
        "is_phishing": false
      }
    }
  ],
  "total": 8,
  "grouped": null
}
```

### `POST /review/{email_id}/correct`

```json
// Request
{
  "corrected_category": "spam",
  "note": "C'est clairement du spam"
}

// Response 200
{
  "classification": {
    "category": "spam",
    "status": "corrected",
    "confidence": 1.0
  },
  "correction": {
    "original_category": "promotion",
    "corrected_category": "spam"
  },
  "actions_executed": [
    { "type": "move", "folder": "Spam", "status": "success" }
  ]
}
```

---

## Règles — `/api/v1/rules`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/rules` | Lister toutes les règles |
| `POST` | `/rules` | Créer une règle |
| `GET` | `/rules/{id}` | Détail d'une règle |
| `PUT` | `/rules/{id}` | Modifier une règle |
| `DELETE` | `/rules/{id}` | Supprimer une règle |
| `POST` | `/rules/{id}/test` | Tester une règle sur un email |
| `PUT` | `/rules/reorder` | Réordonner les priorités |

### `POST /rules`

```json
// Règle structurée
{
  "name": "LinkedIn notifications → archive",
  "type": "structured",
  "account_id": null,
  "priority": 10,
  "conditions": {
    "operator": "AND",
    "rules": [
      { "field": "from_address", "op": "contains", "value": "@linkedin.com" },
      { "field": "category", "op": "equals", "value": "notification" }
    ]
  },
  "actions": [
    { "type": "move", "folder": "Archive" },
    { "type": "flag", "value": "read" }
  ]
}

// Règle langage naturel (Phase 2)
{
  "name": "Newsletters non lues",
  "type": "natural",
  "natural_text": "Archive les newsletters que je n'ai pas ouvertes depuis plus d'un mois",
  "actions": [
    { "type": "archive" }
  ]
}
```

### `POST /rules/{id}/test`

Teste une règle sur un email existant sans exécuter les actions :

```json
// Request
{
  "email_id": "uuid"
}

// Response 200
{
  "matches": true,
  "matched_conditions": ["from_address contains @linkedin.com", "category equals notification"],
  "actions_preview": [
    { "type": "move", "folder": "Archive" },
    { "type": "flag", "value": "read" }
  ]
}
```

---

## Newsletters — `/api/v1/newsletters`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/newsletters` | Lister les newsletters détectées |
| `POST` | `/newsletters/{id}/unsubscribe` | Se désabonner |
| `POST` | `/newsletters/bulk-unsubscribe` | Désinscription en masse |
| `GET` | `/newsletters/stats` | Stats globales newsletters |

### `GET /newsletters`

```
GET /newsletters?status=subscribed&sort=-total_received&min_received=5
```

```json
// Response 200
{
  "items": [
    {
      "id": "uuid",
      "name": "Amazon Deals",
      "sender_address": "deals@amazon.fr",
      "total_received": 156,
      "total_read": 3,
      "read_rate": 0.019,
      "frequency_days": 1.2,
      "subscription_status": "subscribed",
      "unsubscribe_method": "http_post",
      "last_received_at": "2026-02-24T06:00:00Z"
    }
  ],
  "total": 34
}
```

---

## Sender Profiles — `/api/v1/senders`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/senders` | Lister les expéditeurs connus |
| `GET` | `/senders/{id}` | Détail (avec category_stats) |
| `POST` | `/senders/{id}/block` | Bloquer un expéditeur |
| `POST` | `/senders/{id}/unblock` | Débloquer |

---

## Analytics — `/api/v1/analytics`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/overview` | KPIs principaux |
| `GET` | `/analytics/categories` | Répartition par catégorie |
| `GET` | `/analytics/volume` | Volume par jour/semaine |
| `GET` | `/analytics/top-senders` | Top expéditeurs |
| `GET` | `/analytics/performance` | Performances du système (temps, taux, tokens) |
| `GET` | `/analytics/confusion-matrix` | Matrice de confusion (corrections) |

### `GET /analytics/overview`

```
GET /analytics/overview?period=30d&account_id=uuid
```

```json
// Response 200
{
  "period": "30d",
  "emails_received": 342,
  "emails_today": 12,
  "review_pending": 5,
  "phishing_blocked": 3,
  "spam_filtered": 28,
  "auto_classification_rate": 0.78,
  "threads_awaiting_response": 2,
  "newsletters_tracked": 34
}
```

---

## Threads — `/api/v1/threads`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/threads` | Conversations avec filtres (awaiting_response, awaiting_reply) |
| `GET` | `/threads/{id}` | Détail du thread + emails |
| `POST` | `/threads/{id}/resolve` | Marquer comme résolu |
| `POST` | `/threads/{id}/ignore` | Marquer comme ignoré |

---

## Activity Feed — `/api/v1/activity`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/activity` | Feed d'activité paginé |

```
GET /activity?account_id=uuid&severity=warning,error&limit=50
```

---

## Settings — `/api/v1/settings`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/settings` | Configuration actuelle |
| `PUT` | `/settings` | Mettre à jour la configuration |
| `GET` | `/settings/llm/models` | Lister les modèles disponibles (Ollama) |
| `POST` | `/settings/llm/test` | Tester la connexion LLM |

### `PUT /settings`

```json
{
  "llm_provider": "ollama",
  "llm_model": "qwen2.5:7b",
  "llm_base_url": "http://ollama:11434",
  "llm_temperature": 0.1,
  "polling_interval_minutes": 5,
  "confidence_threshold": 0.7,
  "auto_mode": true,
  "body_excerpt_length": 2000,
  "retention_days": 90,
  "phishing_auto_quarantine": true
}
```

### `GET /settings/llm/models`

Interroge Ollama pour lister les modèles installés :

```json
// Response 200
{
  "provider": "ollama",
  "models": [
    { "name": "qwen2.5:7b", "size": "4.7 GB", "modified_at": "2026-02-20T10:00:00Z" },
    { "name": "mistral:7b", "size": "4.1 GB", "modified_at": "2026-02-15T08:00:00Z" }
  ]
}
```

---

## System — `/api/v1/system`

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/system/health` | Healthcheck (API + DB + IMAP + LLM) |
| `GET` | `/system/stats` | Stats système (uptime, jobs, queue) |
| `POST` | `/system/cleanup` | Forcer le nettoyage de rétention |

### `GET /system/health`

```json
{
  "status": "healthy",
  "checks": {
    "database": { "status": "ok", "latency_ms": 2 },
    "ollama": { "status": "ok", "model_loaded": "qwen2.5:7b", "latency_ms": 45 },
    "imap_accounts": [
      { "account": "leo@gmx.fr", "status": "ok", "last_poll": "2026-02-24T10:55:00Z" }
    ]
  },
  "scheduler": {
    "running": true,
    "jobs": 4,
    "next_poll": "2026-02-24T11:00:00Z"
  }
}
```

---

## Codes d'erreur

| Code | Signification |
|---|---|
| 200 | Succès |
| 201 | Créé |
| 400 | Requête invalide (validation) |
| 401 | Non authentifié (si app_password défini) |
| 404 | Ressource introuvable |
| 409 | Conflit (email déjà existant, règle en doublon…) |
| 422 | Erreur de validation Pydantic |
| 500 | Erreur serveur |
| 503 | Service indisponible (Ollama down, IMAP unreachable) |

Toutes les erreurs suivent le format :

```json
{
  "error": "ERROR_CODE",
  "message": "Description lisible",
  "details": {}
}
```

---

*Document précédent : [03-FEATURES/03h-ANALYTICS.md](./03-FEATURES/03h-ANALYTICS.md)*
*Document suivant : [05-FRONTEND-UI.md](./05-FRONTEND-UI.md)*
