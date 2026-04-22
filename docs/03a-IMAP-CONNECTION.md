# Feature : Connexion IMAP & Polling

> Phase 1 (MVP)

## Objectif

Connecter un ou plusieurs comptes email via IMAP, récupérer les nouveaux messages en continu et maintenir la synchronisation bidirectionnelle (déplacements, flags).

## Bibliothèque

**`imap_tools`** (Python) — Wrapper haut niveau au dessus de `imaplib`.

Pourquoi `imap_tools` plutôt que `imaplib` brut :
- API intuitive avec des objets Python typés (`MailMessage`, `MailAttachment`)
- Gestion transparente de l'encodage (MIME, RFC 2047, charsets exotiques)
- Fetch par critères (UID, date, expéditeur…) en une ligne
- Gestion propre des flags et des dossiers

## Flux de connexion

```
Utilisateur saisit email + mot de passe
        │
        ▼
Auto-détection du provider (via domaine)
        │
        ▼
Test de connexion IMAP (SSL/TLS)
        │
        ├── Succès → Découverte des dossiers
        │                  │
        │                  ▼
        │            Mapping automatique des dossiers
        │            (INBOX, Sent, Spam, Trash…)
        │                  │
        │                  ▼
        │            Sauvegarde compte en base
        │            (password chiffré Fernet)
        │                  │
        │                  ▼
        │            Premier fetch (N derniers emails)
        │
        └── Échec → Message d'erreur détaillé
                    (auth failed, host unreachable, SSL error…)
```

## Auto-détection du provider

À partir du domaine de l'adresse email, on déduit automatiquement les paramètres IMAP :

```python
PROVIDER_MAP = {
    "gmx.com":       {"host": "imap.gmx.com",       "port": 993},
    "gmx.fr":        {"host": "imap.gmx.com",       "port": 993},
    "gmail.com":     {"host": "imap.gmail.com",      "port": 993},
    "outlook.com":   {"host": "outlook.office365.com","port": 993},
    "hotmail.com":   {"host": "outlook.office365.com","port": 993},
    "yahoo.com":     {"host": "imap.mail.yahoo.com", "port": 993},
    "yahoo.fr":      {"host": "imap.mail.yahoo.com", "port": 993},
    "fastmail.com":  {"host": "imap.fastmail.com",   "port": 993},
    "protonmail.com":{"host": "127.0.0.1",           "port": 1143, "note": "ProtonMail Bridge requis"},
    "icloud.com":    {"host": "imap.mail.me.com",    "port": 993},
}
```

Si le domaine n'est pas dans la map → formulaire manuel (host, port, SSL).

## Découverte des dossiers IMAP

Les noms de dossiers varient énormément selon les providers. InboxShield doit mapper les dossiers logiques aux noms réels :

| Dossier logique | GMX | Gmail | Outlook | Fastmail |
|---|---|---|---|---|
| Inbox | `INBOX` | `INBOX` | `INBOX` | `INBOX` |
| Sent | `Sent` | `[Gmail]/Sent Mail` | `Sent Items` | `Sent` |
| Drafts | `Drafts` | `[Gmail]/Drafts` | `Drafts` | `Drafts` |
| Spam | `Spam` | `[Gmail]/Spam` | `Junk Email` | `Junk Mail` |
| Trash | `Trash` | `[Gmail]/Trash` | `Deleted Items` | `Trash` |

**Stratégie de mapping :**
1. Lister tous les dossiers via `mailbox.folder.list()`
2. Utiliser les attributs IMAP spéciaux (`\Sent`, `\Trash`, `\Junk`, `\Drafts`) quand disponibles
3. Fallback sur les noms courants (matching case-insensitive)
4. Permettre à l'utilisateur de corriger manuellement le mapping

## Polling : récupération des nouveaux emails

### Mécanisme

APScheduler exécute un job `poll_emails` à intervalle configurable (défaut : 5 minutes).

```python
async def poll_emails(account_id: UUID):
    account = await get_account(account_id)
    
    with MailBox(account.imap_host, account.imap_port).login(
        account.username, 
        decrypt(account.encrypted_password)
    ) as mailbox:
        # Fetch uniquement les emails plus récents que le dernier UID
        messages = mailbox.fetch(
            AND(uid=UidRange(account.last_uid + 1, "*")),
            mark_seen=False,  # Ne pas marquer comme lu
            bulk=True
        )
        
        for msg in messages:
            email = await save_email(account, msg)
            # → emails.processing_status = 'pending'
        
        # Mettre à jour le dernier UID traité
        await update_last_uid(account)
```

### Données extraites par email

| Donnée | Source | Stockage |
|---|---|---|
| UID | IMAP UID | `emails.uid` |
| Message-ID | Header `Message-ID` | `emails.message_id` |
| In-Reply-To | Header `In-Reply-To` | `emails.in_reply_to` |
| References | Header `References` | `emails.references` |
| From | Header `From` (parsé) | `emails.from_address` + `from_name` |
| To | Header `To` (parsé) | `emails.to_addresses` (JSONB) |
| CC | Header `Cc` (parsé) | `emails.cc_addresses` (JSONB) |
| Subject | Header `Subject` (décodé) | `emails.subject` |
| Date | Header `Date` (parsé) | `emails.date` |
| Body text | `msg.text` (imap_tools) | `emails.body_excerpt` (tronqué) |
| Body HTML | `msg.html` (imap_tools) | `emails.body_html_excerpt` (tronqué) |
| Attachments | `msg.attachments` | `emails.has_attachments` + `attachment_names` |
| Flags | IMAP flags | `emails.is_read`, `is_flagged` |
| Size | `msg.size` | `emails.size_bytes` |
| Folder | Dossier courant | `emails.folder` |

### Nettoyage du body

Le body HTML est nettoyé avant stockage :
1. Strip HTML avec `beautifulsoup4` (garder uniquement le texte)
2. Supprimer les signatures (heuristique : après `--`, `___`, ou patterns courants)
3. Supprimer les citations (lignes commençant par `>`)
4. Supprimer les espaces multiples et lignes vides
5. Tronquer à `settings.body_excerpt_length` caractères (défaut 2000)

Le HTML brut est aussi conservé (tronqué) dans `body_html_excerpt` pour l'extraction des URLs (phishing) et des liens de désinscription.

## Actions IMAP (écriture)

InboxShield effectue des opérations d'écriture sur le serveur IMAP :

| Action | Commande IMAP | Fonction `imap_tools` |
|---|---|---|
| Déplacer un email | COPY + DELETE | `mailbox.move(uid, folder)` |
| Marquer comme lu | SET FLAG \Seen | `mailbox.flag(uid, MailMessageFlags.SEEN, True)` |
| Marquer comme non lu | UNSET FLAG \Seen | `mailbox.flag(uid, MailMessageFlags.SEEN, False)` |
| Marquer important | SET FLAG \Flagged | `mailbox.flag(uid, MailMessageFlags.FLAGGED, True)` |
| Supprimer | COPY to Trash | `mailbox.move(uid, trash_folder)` |

**Toutes les actions IMAP sont loguées dans la table `actions`** avec `is_reversible = TRUE`, permettant un undo.

## Health check

Un job `check_imap_health` tourne toutes les 5 minutes :
- Tente une connexion IMAP sur chaque compte actif
- Met à jour `accounts.last_poll_error` en cas d'échec
- Crée une entrée `activity_logs` avec `event_type = 'poll_error'` + `severity = 'error'`
- Après 3 échecs consécutifs → désactive le polling et notifie le dashboard

## Premier fetch (onboarding)

À la connexion d'un nouveau compte, InboxShield effectue un fetch initial :
- Récupère les **100 derniers emails** de l'INBOX (configurable)
- Classe chaque email (en batch, limité à 5 concurrent pour ne pas surcharger Ollama)
- Populer les `sender_profiles` et `sender_category_stats`
- L'utilisateur voit le dashboard se remplir progressivement

## Sécurité

- **Credentials** : Le mot de passe IMAP est chiffré avec Fernet (clé dérivée d'une variable d'environnement `ENCRYPTION_KEY`). Jamais stocké en clair.
- **Connexions** : Toujours SSL/TLS (port 993 par défaut). Pas de connexion en clair.
- **Timeouts** : Timeout de connexion IMAP à 30 secondes, timeout de fetch à 60 secondes.
- **Rate limiting** : Respect des limites IMAP du provider (GMX : pas de limite connue, Gmail : 2500 requêtes/jour).

## Gestion des erreurs

| Erreur | Comportement |
|---|---|
| Auth failed | Log error, marque le compte en erreur, notifie le dashboard |
| Connexion timeout | Retry dans 1 minute (max 3 retries), puis skip ce cycle |
| Dossier introuvable | Log warning, continue avec les dossiers valides |
| Email malformé | Log warning, save avec les données disponibles, `processing_status = 'failed'` |
| Quota IMAP dépassé | Pause polling pendant 15 minutes, notifie le dashboard |

---

*Feature suivante : [03b-AI-CLASSIFICATION.md](./03b-AI-CLASSIFICATION.md)*
