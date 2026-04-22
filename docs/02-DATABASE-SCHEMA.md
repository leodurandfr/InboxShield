# InboxShield — Database Schema

## Vue d'ensemble

Base de données PostgreSQL 16. ORM : SQLAlchemy 2.0 avec Alembic pour les migrations.

```
accounts ──< account_settings (1:1)
    │
    ├──────< emails ──────< classifications
    │          │                   │
    │          │                   └──── corrections
    │          │
    │          ├──────< actions
    │          │
    │          ├──────< email_urls
    │          │
    │          └──────< email_threads (N:1)
    │
    ├──────< rules
    │
    ├──────< sender_profiles ──< sender_category_stats
    │              │
    │              └──── newsletters (1:1)
    │
    └──────< activity_logs

settings (table singleton — config globale)
```

Légende : `──<` = relation one-to-many, `(1:1)` = one-to-one

---

## Changements par rapport à la v1

| Problème identifié | Solution |
|---|---|
| Un expéditeur = une seule catégorie (Amazon envoie promo ET transactional) | Nouvelle table `sender_category_stats` : tracking par couple (expéditeur, catégorie) |
| Pas de statut de traitement sur les emails | Ajout de `processing_status` sur `emails` (pending, processing, classified, failed) |
| Settings uniquement global | Nouvelle table `account_settings` pour les réglages par compte |
| Pas de stratégie de rétention | Ajout de `is_archived` sur `emails` + politique de rétention configurable |
| `body_excerpt` trop court (~500 chars) | Augmenté à ~2000 chars, configurable dans settings |
| Pas de threading pour Reply Tracking | Nouvelle table `email_threads` pour regrouper les conversations |
| Pas de log d'activité dédié | Nouvelle table `activity_logs` pour le feed du dashboard |

---

## Tables

### accounts

Comptes IMAP/SMTP configurés. Les credentials sont chiffrés avec Fernet.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `name` | VARCHAR(255) | NOT NULL | Nom affiché ("GMX Personnel", "Gmail Pro"…) |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Adresse email |
| `provider` | VARCHAR(50) | | Provider détecté (gmx, gmail, outlook, custom…) |
| `imap_host` | VARCHAR(255) | NOT NULL | Serveur IMAP |
| `imap_port` | INTEGER | NOT NULL, default 993 | Port IMAP |
| `smtp_host` | VARCHAR(255) | | Serveur SMTP |
| `smtp_port` | INTEGER | default 587 | Port SMTP |
| `username` | VARCHAR(255) | NOT NULL | Identifiant IMAP |
| `encrypted_password` | TEXT | NOT NULL | Mot de passe chiffré (Fernet) |
| `use_ssl` | BOOLEAN | default TRUE | Connexion SSL/TLS |
| `is_active` | BOOLEAN | default TRUE | Compte actif (polling activé) |
| `last_poll_at` | TIMESTAMP | | Dernier polling réussi |
| `last_poll_error` | TEXT | | Dernière erreur de polling (NULL si OK) |
| `last_uid` | BIGINT | default 0 | Dernier UID IMAP traité |
| `folder_mapping` | JSONB | default '{}' | Mapping dossiers IMAP |
| `created_at` | TIMESTAMP | NOT NULL, default now() | Date de création |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | Dernière modification |

**Index :**
- `idx_accounts_email` sur `email`
- `idx_accounts_is_active` sur `is_active`

**`folder_mapping` exemple :**
```json
{
  "inbox": "INBOX",
  "sent": "[Gmail]/Sent Mail",
  "spam": "Junk",
  "trash": "Trash",
  "newsletters": "Newsletters",
  "quarantine": "InboxShield/Quarantine"
}
```

---

### account_settings

Mapping catégorie → dossier IMAP, spécifique à chaque compte (les noms de dossiers diffèrent entre providers). Tout le reste de la config est global dans `settings`.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id, UNIQUE, NOT NULL | Compte associé |




| `default_category_action` | JSONB | default '{}' | Mapping catégorie → dossier IMAP par défaut |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**`default_category_action` exemple :**
```json
{
  "newsletter": { "action": "move", "folder": "Newsletters" },
  "spam": { "action": "move", "folder": "Junk" },
  "phishing": { "action": "move", "folder": "InboxShield/Quarantine" },
  "promotion": { "action": "move", "folder": "Promotions" }
}
```

**Logique :** Chaque compte a son propre mapping car les dossiers IMAP varient selon les providers (GMX vs Gmail vs Outlook).

---

### emails

Emails indexés avec métadonnées. Le body complet reste sur le serveur IMAP.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id, NOT NULL | Compte associé |
| `thread_id` | UUID | FK → email_threads.id | Conversation associée |
| `uid` | BIGINT | NOT NULL | UID IMAP du message |
| `message_id` | VARCHAR(512) | | Header Message-ID |
| `in_reply_to` | VARCHAR(512) | | Header In-Reply-To |
| `references` | TEXT | | Header References (liste, séparée par espaces) |
| `from_address` | VARCHAR(255) | NOT NULL | Adresse expéditeur |
| `from_name` | VARCHAR(255) | | Nom affiché de l'expéditeur |
| `to_addresses` | JSONB | | Liste des destinataires |
| `cc_addresses` | JSONB | | Liste CC |
| `subject` | TEXT | | Sujet |
| `body_excerpt` | TEXT | | Extrait texte nettoyé (~2000 chars par défaut) |
| `body_html_excerpt` | TEXT | | Extrait HTML (pour extraction liens/unsubscribe) |
| `has_attachments` | BOOLEAN | default FALSE | Contient des pièces jointes |
| `attachment_names` | JSONB | | Noms des pièces jointes |
| `date` | TIMESTAMP | NOT NULL | Date d'envoi du mail |
| `folder` | VARCHAR(255) | | Dossier IMAP actuel |
| `original_folder` | VARCHAR(255) | | Dossier d'origine (avant déplacement par InboxShield) |
| `is_read` | BOOLEAN | default FALSE | Lu/non lu |
| `is_flagged` | BOOLEAN | default FALSE | Marqué important |
| `size_bytes` | INTEGER | | Taille du message |
| `processing_status` | VARCHAR(20) | NOT NULL, default 'pending' | Statut du pipeline |
| `processing_error` | TEXT | | Erreur si processing_status = 'failed' |
| `is_archived` | BOOLEAN | default FALSE | Archivé dans InboxShield (rétention) |
| `created_at` | TIMESTAMP | NOT NULL, default now() | Date d'indexation |

**Valeurs `processing_status` :**
- `pending` — Fetché, en attente de classification
- `processing` — Classification en cours (envoyé au LLM)
- `classified` — Classifié avec succès
- `failed` — Erreur de classification (LLM timeout, parsing error…)
- `skipped` — Ignoré (expéditeur bloqué, doublon…)

**Index :**
- `idx_emails_account_uid` UNIQUE sur `(account_id, uid)`
- `idx_emails_from_address` sur `from_address`
- `idx_emails_date` sur `date DESC`
- `idx_emails_folder` sur `folder`
- `idx_emails_account_date` sur `(account_id, date DESC)`
- `idx_emails_processing_status` sur `processing_status` WHERE `processing_status IN ('pending', 'processing', 'failed')`
- `idx_emails_thread_id` sur `thread_id`
- `idx_emails_message_id` sur `message_id`
- `idx_emails_not_archived` sur `is_archived` WHERE `is_archived = FALSE`

---

### email_threads

Conversations regroupées. Utilisées pour le Reply Tracking (Phase 3).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id, NOT NULL | Compte associé |
| `subject_normalized` | VARCHAR(512) | | Sujet nettoyé (sans Re:, Fwd:, etc.) |
| `participants` | JSONB | | Liste des adresses impliquées |
| `email_count` | INTEGER | default 1 | Nombre d'emails dans le thread |
| `last_email_at` | TIMESTAMP | | Date du dernier email |
| `awaiting_reply` | BOOLEAN | default FALSE | En attente d'une réponse de l'utilisateur |
| `awaiting_response` | BOOLEAN | default FALSE | En attente d'une réponse d'un tiers |
| `reply_needed_since` | TIMESTAMP | | Depuis quand une réponse est attendue |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**Index :**
- `idx_threads_account_id` sur `account_id`
- `idx_threads_awaiting` sur `(awaiting_reply, awaiting_response)` WHERE `awaiting_reply = TRUE OR awaiting_response = TRUE`

**Construction des threads :**
Le threading est construit à partir des headers `In-Reply-To` et `References`. Quand un email arrive avec un `In-Reply-To` qui correspond au `message_id` d'un email existant, ils sont regroupés dans le même thread.

---

### classifications

Résultat de la classification AI pour chaque email.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `email_id` | UUID | FK → emails.id, UNIQUE, NOT NULL | Email classifié |
| `category` | VARCHAR(50) | NOT NULL | Catégorie assignée |
| `confidence` | FLOAT | NOT NULL | Score de confiance (0.0 — 1.0) |
| `explanation` | TEXT | | Explication du LLM |
| `is_spam` | BOOLEAN | default FALSE | Détecté comme spam |
| `is_phishing` | BOOLEAN | default FALSE | Détecté comme phishing |
| `phishing_reasons` | JSONB | | Raisons détaillées du signalement |
| `status` | VARCHAR(20) | NOT NULL, default 'auto' | Statut de la classification |
| `classified_by` | VARCHAR(20) | NOT NULL, default 'llm' | Méthode de classification |
| `llm_provider` | VARCHAR(50) | | Provider utilisé |
| `llm_model` | VARCHAR(100) | | Modèle utilisé |
| `tokens_used` | INTEGER | | Tokens consommés |
| `processing_time_ms` | INTEGER | | Temps de traitement |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**Valeurs `status` :**
- `auto` — Classifié et action exécutée automatiquement
- `review` — En attente de validation (confiance < seuil)
- `approved` — Validé par l'utilisateur depuis la review queue
- `corrected` — Corrigé par l'utilisateur

**Valeurs `classified_by` :**
- `llm` — Classifié par le LLM
- `sender_profile` — Classifié directement via le profil expéditeur (sans appel LLM)
- `rule` — Classifié par une règle structurée (sans appel LLM)
- `manual` — Classifié manuellement par l'utilisateur

**Catégories possibles :**

| Catégorie | Description |
|---|---|
| `important` | Emails nécessitant une attention immédiate |
| `work` | Emails professionnels |
| `personal` | Emails personnels |
| `newsletter` | Newsletters et abonnements |
| `promotion` | Offres commerciales, publicités |
| `notification` | Notifications automatiques (réseaux sociaux, services…) |
| `spam` | Spam classique |
| `phishing` | Tentative de phishing/arnaque |
| `transactional` | Confirmations de commande, factures, reçus |

**Index :**
- `idx_classifications_category` sur `category`
- `idx_classifications_status` sur `status`
- `idx_classifications_is_phishing` sur `is_phishing` WHERE `is_phishing = TRUE`
- `idx_classifications_review` sur `status` WHERE `status = 'review'`

---

### corrections

Corrections manuelles de l'utilisateur. Servent au few-shot learning.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `email_id` | UUID | FK → emails.id, NOT NULL | Email corrigé |
| `classification_id` | UUID | FK → classifications.id, NOT NULL | Classification corrigée |
| `original_category` | VARCHAR(50) | NOT NULL | Catégorie proposée par le LLM |
| `corrected_category` | VARCHAR(50) | NOT NULL | Catégorie choisie par l'utilisateur |
| `original_confidence` | FLOAT | | Confiance du LLM à l'origine |
| `user_note` | TEXT | | Note optionnelle |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |

**Index :**
- `idx_corrections_categories` sur `(original_category, corrected_category)`
- `idx_corrections_created_at` sur `created_at DESC`

**Usage few-shot :** Les N corrections les plus récentes (configurable, défaut 10) sont injectées dans le prompt du LLM comme exemples. Format :
```
Exemple : email de "newsletter@figma.com" avec sujet "Figma Config 2025"
→ Initialement classé "promotion", corrigé en "newsletter"
```

---

### rules

Règles de tri définies par l'utilisateur.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id | Compte ciblé (NULL = tous les comptes) |
| `name` | VARCHAR(255) | NOT NULL | Nom de la règle |
| `type` | VARCHAR(20) | NOT NULL | 'structured' ou 'natural' |
| `priority` | INTEGER | default 0 | Priorité (plus élevé = exécuté en premier) |
| `is_active` | BOOLEAN | default TRUE | Activée/désactivée |
| `conditions` | JSONB | | Conditions structurées (type='structured') |
| `natural_text` | TEXT | | Texte en langage naturel (type='natural') |
| `actions` | JSONB | NOT NULL | Actions à exécuter |
| `match_count` | INTEGER | default 0 | Nombre de matchs |
| `last_matched_at` | TIMESTAMP | | Dernier match |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**Format `conditions` (type='structured') :**
```json
{
  "operator": "AND",
  "rules": [
    { "field": "from_address", "op": "contains", "value": "@amazon.fr" },
    { "field": "subject", "op": "contains", "value": "livraison" }
  ]
}
```

**Opérateurs :** `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`, `regex`, `in_list`

**Champs filtrables :** `from_address`, `from_name`, `to_addresses`, `subject`, `body_excerpt`, `category`, `is_spam`, `is_phishing`, `has_attachments`

**Format `actions` :**
```json
[
  { "type": "move", "folder": "Newsletters" },
  { "type": "flag", "value": "read" }
]
```

**Types d'actions :** `move`, `archive`, `delete`, `flag` (read/unread/important), `mark_spam`, `block_sender`

**Index :**
- `idx_rules_account_active` sur `(account_id, is_active)`
- `idx_rules_priority` sur `priority DESC`

---

### actions

Historique de toutes les actions exécutées par le système.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `email_id` | UUID | FK → emails.id, NOT NULL | Email concerné |
| `account_id` | UUID | FK → accounts.id, NOT NULL | Compte concerné |
| `action_type` | VARCHAR(50) | NOT NULL | Type d'action |
| `action_details` | JSONB | | Détails (dossier cible, flag…) |
| `trigger` | VARCHAR(50) | NOT NULL | Ce qui a déclenché l'action |
| `rule_id` | UUID | FK → rules.id | Règle associée (si applicable) |
| `status` | VARCHAR(20) | NOT NULL, default 'success' | 'success', 'failed', 'pending' |
| `error_message` | TEXT | | Message d'erreur si échec |
| `is_reversible` | BOOLEAN | default TRUE | Action annulable |
| `reversed_at` | TIMESTAMP | | Date d'annulation (si annulée) |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |

**Valeurs `trigger` :** `auto_classification`, `rule_structured`, `rule_natural`, `manual`, `bulk_action`, `sender_profile`

**Index :**
- `idx_actions_email_id` sur `email_id`
- `idx_actions_created_at` sur `created_at DESC`
- `idx_actions_account_date` sur `(account_id, created_at DESC)`

---

### sender_profiles

Profil par expéditeur. Utilisé pour l'apprentissage et la classification directe.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id, NOT NULL | Compte associé |
| `email_address` | VARCHAR(255) | NOT NULL | Adresse de l'expéditeur |
| `display_name` | VARCHAR(255) | | Dernier nom affiché |
| `domain` | VARCHAR(255) | | Domaine extrait |
| `primary_category` | VARCHAR(50) | | Catégorie la plus fréquente |
| `total_emails` | INTEGER | default 0 | Nombre total de mails reçus |
| `last_email_at` | TIMESTAMP | | Date du dernier mail |
| `is_newsletter` | BOOLEAN | default FALSE | Identifié comme newsletter |
| `is_blocked` | BOOLEAN | default FALSE | Expéditeur bloqué |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**Index :**
- `idx_sender_profiles_address` UNIQUE sur `(account_id, email_address)`
- `idx_sender_profiles_domain` sur `domain`
- `idx_sender_profiles_blocked` sur `is_blocked` WHERE `is_blocked = TRUE`

---

### sender_category_stats

Statistiques de classification par couple (expéditeur, catégorie). Résout le problème d'un expéditeur qui envoie plusieurs types d'emails.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `sender_profile_id` | UUID | FK → sender_profiles.id, NOT NULL | Profil expéditeur |
| `category` | VARCHAR(50) | NOT NULL | Catégorie |
| `count` | INTEGER | default 0 | Nombre de fois classé dans cette catégorie |
| `corrected_count` | INTEGER | default 0 | Nombre de corrections vers cette catégorie |
| `last_seen_at` | TIMESTAMP | | Dernier mail dans cette catégorie |

**Index :**
- `idx_sender_cat_stats_profile_cat` UNIQUE sur `(sender_profile_id, category)`

**Logique de classification directe (sans LLM) :**
1. Chercher le `sender_profile` de l'expéditeur
2. Regarder la `sender_category_stats` : si une catégorie a `count >= 5` ET représente > 80% du total → classification directe
3. Si l'expéditeur a plusieurs catégories significatives (ex: Amazon = 60% transactional + 35% promotion) → passer par le LLM car le contexte du mail est nécessaire
4. Une correction utilisateur ajoute +2 au `corrected_count` (poids double vs classification auto)

---

### newsletters

Newsletters détectées avec statut d'abonnement.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id, NOT NULL | Compte associé |
| `sender_profile_id` | UUID | FK → sender_profiles.id | Profil expéditeur lié |
| `name` | VARCHAR(255) | | Nom de la newsletter |
| `sender_address` | VARCHAR(255) | NOT NULL | Adresse d'envoi |
| `unsubscribe_link` | TEXT | | URL de désinscription |
| `unsubscribe_mailto` | VARCHAR(255) | | Adresse mailto de désinscription |
| `unsubscribe_method` | VARCHAR(20) | | 'http_post', 'http_get', 'mailto', 'manual' |
| `subscription_status` | VARCHAR(20) | default 'subscribed' | Statut d'abonnement |
| `total_received` | INTEGER | default 0 | Nombre total reçus |
| `total_read` | INTEGER | default 0 | Nombre lus |
| `frequency_days` | FLOAT | | Fréquence estimée (jours entre 2 envois) |
| `last_received_at` | TIMESTAMP | | Dernier envoi reçu |
| `unsubscribed_at` | TIMESTAMP | | Date de désinscription |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

**Valeurs `subscription_status` :** `subscribed`, `unsubscribing`, `unsubscribed`, `failed`

**Index :**
- `idx_newsletters_account_sender` UNIQUE sur `(account_id, sender_address)`
- `idx_newsletters_status` sur `subscription_status`

---

### email_urls

URLs extraites des emails pour l'analyse de phishing.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `email_id` | UUID | FK → emails.id, NOT NULL | Email source |
| `url` | TEXT | NOT NULL | URL réelle (href) |
| `display_text` | TEXT | | Texte affiché du lien |
| `domain` | VARCHAR(255) | | Domaine extrait de l'URL |
| `is_suspicious` | BOOLEAN | default FALSE | Marqué suspect |
| `suspicion_reason` | TEXT | | Raison détaillée |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |

**Détection d'URLs suspectes :**
- Texte affiché ≠ URL réelle (ex: texte = "paypal.com", href = "paypa1-secure.xyz")
- Domaine avec homoglyphes (caractères visuellement similaires)
- Raccourcisseurs d'URL (bit.ly, tinyurl…) dans un mail "officiel"
- Domaine très récent ou inconnu

**Index :**
- `idx_email_urls_email_id` sur `email_id`
- `idx_email_urls_suspicious` sur `is_suspicious` WHERE `is_suspicious = TRUE`

---

### activity_logs

Journal d'activité pour le feed du dashboard.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Identifiant unique |
| `account_id` | UUID | FK → accounts.id | Compte concerné |
| `event_type` | VARCHAR(50) | NOT NULL | Type d'événement |
| `severity` | VARCHAR(20) | default 'info' | 'info', 'warning', 'error', 'success' |
| `title` | VARCHAR(255) | NOT NULL | Titre court |
| `details` | JSONB | | Détails structurés |
| `email_id` | UUID | FK → emails.id | Email lié (si applicable) |
| `created_at` | TIMESTAMP | NOT NULL, default now() | |

**Valeurs `event_type` :**
- `email_classified` — Email classifié avec succès
- `email_moved` — Email déplacé dans un dossier
- `phishing_detected` — Phishing détecté
- `spam_detected` — Spam détecté
- `rule_matched` — Règle matchée
- `review_approved` — Review approuvée
- `review_corrected` — Classification corrigée
- `unsubscribe_success` — Désinscription réussie
- `unsubscribe_failed` — Désinscription échouée
- `poll_error` — Erreur de polling IMAP
- `llm_error` — Erreur du LLM
- `account_connected` — Nouveau compte connecté

**Index :**
- `idx_activity_created_at` sur `created_at DESC`
- `idx_activity_account_date` sur `(account_id, created_at DESC)`
- `idx_activity_event_type` sur `event_type`

**Rétention :** Nettoyé automatiquement selon `settings.retention_days`.

---

### settings

Configuration globale de l'application. Table singleton (une seule ligne).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | INTEGER | PK, default 1 | Toujours 1 |
| `llm_provider` | VARCHAR(50) | default 'ollama' | 'ollama', 'anthropic', 'openai', 'mistral' |
| `llm_model` | VARCHAR(100) | default 'qwen2.5:7b' | Modèle sélectionné |
| `llm_base_url` | VARCHAR(255) | | URL du provider |
| `llm_api_key_encrypted` | TEXT | | Clé API chiffrée (providers cloud) |
| `llm_temperature` | FLOAT | default 0.1 | Température (basse = déterministe) |
| `polling_interval_minutes` | INTEGER | default 5 | Fréquence de polling par défaut |
| `confidence_threshold` | FLOAT | default 0.7 | Seuil → Review Queue par défaut |
| `auto_mode` | BOOLEAN | default TRUE | Auto-exécution par défaut |
| `max_few_shot_examples` | INTEGER | default 10 | Corrections injectées dans le prompt |
| `body_excerpt_length` | INTEGER | default 2000 | Longueur de l'extrait pour le LLM |
| `retention_days` | INTEGER | default 90 | Rétention des logs/activity |
| `email_retention_days` | INTEGER | default 365 | Rétention des emails en base (0 = illimité) |
| `phishing_auto_quarantine` | BOOLEAN | default TRUE | Quarantaine auto phishing par défaut |
| `app_password` | TEXT | | Mot de passe d'accès à l'app (hashé, optionnel) |
| `updated_at` | TIMESTAMP | NOT NULL, default now() | |

---

## Relations (résumé)

```
accounts (1) ──── (1) account_settings
accounts (1) ──── (N) emails
accounts (1) ──── (N) rules
accounts (1) ──── (N) sender_profiles
accounts (1) ──── (N) newsletters
accounts (1) ──── (N) activity_logs
accounts (1) ──── (N) email_threads

emails (1) ──── (1) classifications
emails (1) ──── (N) actions
emails (1) ──── (N) email_urls
emails (N) ──── (1) email_threads

classifications (1) ──── (N) corrections

sender_profiles (1) ──── (N) sender_category_stats
sender_profiles (1) ──── (0..1) newsletters

rules (1) ──── (N) actions (via rule_id)
```

## Politique de rétention

| Données | Rétention par défaut | Configurable |
|---|---|---|
| `emails` | 365 jours | `settings.email_retention_days` |
| `activity_logs` | 90 jours | `settings.retention_days` |
| `actions` | 90 jours | `settings.retention_days` |
| `corrections` | Illimité | Non (nécessaire pour l'apprentissage) |
| `sender_profiles` | Illimité | Non |
| `classifications` | Suit la rétention de l'email | — |

Un job schedulé (`cleanup_old_data`) tourne quotidiennement pour :
1. Marquer `is_archived = TRUE` les emails au-delà de `email_retention_days`
2. Supprimer les `activity_logs` et `actions` au-delà de `retention_days`
3. Supprimer les `classifications` et `email_urls` orphelins (email archivé/supprimé)

## Migrations

Gérées par Alembic :

```bash
# Créer une migration
alembic revision --autogenerate -m "description"

# Appliquer les migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

*Document précédent : [01-ARCHITECTURE.md](./01-ARCHITECTURE.md)*
*Document suivant : [03-FEATURES/03a-IMAP-CONNECTION.md](./03-FEATURES/03a-IMAP-CONNECTION.md)*
