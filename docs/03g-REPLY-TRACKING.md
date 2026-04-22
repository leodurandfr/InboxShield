# Feature : Reply Tracking

> Phase 3

## Objectif

Suivre les emails envoyés qui attendent une réponse et les emails reçus auxquels l'utilisateur n'a pas encore répondu. Éviter que des conversations importantes tombent dans l'oubli.

## Deux types de tracking

| Type | Question | Donnée |
|---|---|---|
| **Awaiting response** | "J'ai envoyé un email, on m'a répondu ?" | `email_threads.awaiting_response = TRUE` |
| **Awaiting reply** | "On m'a écrit, j'ai répondu ?" | `email_threads.awaiting_reply = TRUE` |

## Construction des threads

Les emails sont regroupés en conversations via les headers IMAP standards :

```python
async def assign_thread(email: Email) -> UUID:
    # 1. Chercher un thread existant via In-Reply-To
    if email.in_reply_to:
        parent = await get_email_by_message_id(email.account_id, email.in_reply_to)
        if parent and parent.thread_id:
            return parent.thread_id
    
    # 2. Chercher via References (liste de Message-IDs)
    if email.references:
        ref_ids = email.references.split()
        for ref_id in reversed(ref_ids):  # Plus récent en premier
            parent = await get_email_by_message_id(email.account_id, ref_id)
            if parent and parent.thread_id:
                return parent.thread_id
    
    # 3. Fallback : matching par sujet normalisé (sans Re:, Fwd:)
    normalized = normalize_subject(email.subject)
    existing_thread = await find_thread_by_subject(email.account_id, normalized)
    if existing_thread and (datetime.utcnow() - existing_thread.last_email_at).days < 30:
        return existing_thread.id
    
    # 4. Nouveau thread
    thread = await create_thread(
        account_id=email.account_id,
        subject_normalized=normalized,
        participants=[email.from_address] + (email.to_addresses or [])
    )
    return thread.id
```

### Normalisation du sujet

```python
def normalize_subject(subject: str) -> str:
    """Supprime Re:, Fwd:, Tr:, RE:, FW: et variantes."""
    cleaned = re.sub(
        r'^(\s*(Re|Fwd|Fw|Tr|AW|Antw)\s*:\s*)+', 
        '', 
        subject or '', 
        flags=re.IGNORECASE
    )
    return cleaned.strip()
```

## Détection du statut de réponse

À chaque nouvel email dans un thread, le statut est réévalué :

```python
async def update_thread_status(thread: EmailThread, new_email: Email, account: Account):
    user_addresses = [account.email]  # Adresses de l'utilisateur
    
    is_from_user = new_email.from_address in user_addresses
    is_to_user = any(addr in user_addresses for addr in (new_email.to_addresses or []))
    
    if is_from_user:
        # L'utilisateur a envoyé un email dans ce thread
        thread.awaiting_reply = False  # Il a répondu
        thread.awaiting_response = True  # Maintenant il attend une réponse
        thread.reply_needed_since = datetime.utcnow()
        
    elif is_to_user:
        # L'utilisateur a reçu un email dans ce thread
        thread.awaiting_response = False  # On lui a répondu
        thread.awaiting_reply = True  # Maintenant c'est à lui de répondre
        thread.reply_needed_since = datetime.utcnow()
    
    thread.email_count += 1
    thread.last_email_at = new_email.date
    thread.participants = list(set(
        (thread.participants or []) + [new_email.from_address] + (new_email.to_addresses or [])
    ))
```

## Interface utilisateur

### Vue "En attente de réponse"

Liste les threads où `awaiting_response = TRUE`, triés par `reply_needed_since ASC` (le plus ancien en premier) :

| Conversation | Envoyé à | En attente depuis | Actions |
|---|---|---|---|
| Devis projet refonte | client@bigcorp.com | 5 jours | [Relancer] [Résolu] |
| Question garantie | support@apple.com | 2 jours | [Relancer] [Résolu] |

### Vue "À répondre"

Liste les threads où `awaiting_reply = TRUE` :

| Conversation | De | Reçu depuis | Actions |
|---|---|---|---|
| Invitation meetup | organisateur@event.com | 3 jours | [Répondre*] [Ignorer] |
| Facture en attente | compta@fournisseur.fr | 1 jour | [Répondre*] [Ignorer] |

*\*"Répondre" ouvre le client email natif via `mailto:`*

### Alertes

- **Nudge après X jours** : Si un thread est en attente depuis plus de 3 jours (configurable), il est mis en évidence dans le dashboard
- **Compteur dans la nav** : Badge "2 en attente" dans la barre de navigation

## Résolution manuelle

L'utilisateur peut marquer un thread comme "Résolu" / "Ignoré" :
- **Résolu** : `awaiting_response = FALSE`, `awaiting_reply = FALSE`
- **Ignoré** : Idem, mais loggé différemment (ne contribue pas aux stats)

Utile pour :
- Conversations qui n'attendent pas vraiment de réponse (remerciements, FYI…)
- Emails envoyés sans attente de réponse (envoi de documents, etc.)

## Limites

- InboxShield ne peut voir que les emails dans les dossiers scannés. Si l'utilisateur répond depuis un autre client et que le mail envoyé est dans un dossier "Sent" non scanné, le tracking ne sera pas mis à jour.
- Le scan du dossier "Sent" est nécessaire pour la détection des réponses de l'utilisateur. Il est activé par défaut mais peut impacter la performance (dossier Sent souvent volumineux).
- Le fallback par sujet peut créer des faux regroupements si deux conversations différentes ont le même sujet.

---

*Feature précédente : [03f-BULK-UNSUBSCRIBE.md](./03f-BULK-UNSUBSCRIBE.md)*
*Feature suivante : [03h-ANALYTICS.md](./03h-ANALYTICS.md)*
