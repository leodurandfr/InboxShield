# Feature : Moteur de règles

> Phase 1 (règles structurées) — Phase 2 (langage naturel)

## Objectif

Permettre à l'utilisateur de définir des règles de tri personnalisées. Deux types : structurées (conditions explicites, évaluées sans LLM) et en langage naturel (interprétées par le LLM).

## Ordre d'évaluation

```
Email classifié
      │
      ▼
  Règles par priorité décroissante
      │
      ├── Règle structurée → Évaluation locale (pas de LLM)
      │
      ├── Règle naturelle → Interprétation LLM
      │
      └── Aucune règle matchée → Action par défaut selon catégorie
                                  (via account_settings.default_category_action)
```

**Règle de priorité :** Les règles sont évaluées par `priority DESC`. La première règle qui matche est exécutée (stop-on-first-match). Cela évite les conflits.

## Règles structurées (Phase 1)

### Format des conditions

```json
{
  "operator": "AND",
  "rules": [
    { "field": "from_address", "op": "contains", "value": "@amazon.fr" },
    { "field": "category", "op": "equals", "value": "promotion" }
  ]
}
```

Supporte le nesting pour des conditions complexes :

```json
{
  "operator": "OR",
  "rules": [
    {
      "operator": "AND",
      "rules": [
        { "field": "from_address", "op": "contains", "value": "@linkedin.com" },
        { "field": "category", "op": "equals", "value": "notification" }
      ]
    },
    {
      "operator": "AND",
      "rules": [
        { "field": "from_address", "op": "contains", "value": "@twitter.com" },
        { "field": "subject", "op": "contains", "value": "a aimé" }
      ]
    }
  ]
}
```

### Opérateurs disponibles

| Opérateur | Description | Exemple |
|---|---|---|
| `equals` | Égalité stricte | `category equals "spam"` |
| `not_equals` | Différent de | `from_address not_equals "boss@company.com"` |
| `contains` | Contient (case-insensitive) | `subject contains "facture"` |
| `not_contains` | Ne contient pas | `subject not_contains "Re:"` |
| `starts_with` | Commence par | `from_address starts_with "no-reply"` |
| `ends_with` | Finit par | `from_address ends_with "@amazon.fr"` |
| `regex` | Expression régulière | `subject regex "^(Fwd|Tr)\s?:"` |
| `in_list` | Dans une liste | `category in_list ["spam", "promotion"]` |

### Champs filtrables

| Champ | Type | Description |
|---|---|---|
| `from_address` | string | Adresse de l'expéditeur |
| `from_name` | string | Nom affiché |
| `to_addresses` | string (cherche dans la liste) | Destinataires |
| `subject` | string | Sujet |
| `body_excerpt` | string | Extrait du corps |
| `category` | string | Catégorie AI assignée |
| `is_spam` | boolean | Détecté spam |
| `is_phishing` | boolean | Détecté phishing |
| `has_attachments` | boolean | A des pièces jointes |

### Évaluation

```python
def evaluate_structured_rule(rule: Rule, email: Email, classification: Classification) -> bool:
    """Évalue une règle structurée. Pas d'appel LLM."""
    conditions = rule.conditions
    return _evaluate_group(conditions, email, classification)

def _evaluate_group(group: dict, email, classification) -> bool:
    operator = group["operator"]  # AND / OR
    results = [_evaluate_condition(r, email, classification) for r in group["rules"]]
    
    if operator == "AND":
        return all(results)
    elif operator == "OR":
        return any(results)
```

## Règles en langage naturel (Phase 2)

### Concept

L'utilisateur écrit une règle en français (ou anglais) :

> "Archive les notifications LinkedIn que je ne lis jamais"
> "Déplace les newsletters tech dans le dossier Tech"
> "Marque comme important tout email de mon client @bigcorp.com"

### Interprétation par le LLM

Le LLM reçoit la règle en langage naturel + les métadonnées de l'email et détermine si la règle s'applique :

```
SYSTEM:
Tu es un assistant de tri d'emails. On te donne une règle en langage naturel et 
un email. Détermine si la règle s'applique à cet email.

Réponds UNIQUEMENT en JSON :
{
  "matches": true/false,
  "reason": "explication courte"
}

RÈGLE : "Archive les notifications LinkedIn que je ne lis jamais"

EMAIL :
De : notifications-noreply@linkedin.com
Sujet : Vous avez 5 nouvelles notifications
Catégorie : notification
```

### Coût des règles naturelles

Chaque règle naturelle nécessite un appel LLM par email. Pour limiter le coût :
- Les règles naturelles sont évaluées **après** les règles structurées
- Si une règle structurée a déjà matché → les règles naturelles sont sautées
- Le nombre de règles naturelles actives est limité (suggéré : max 10)

## Actions

Les actions sont communes aux deux types de règles :

```json
[
  { "type": "move", "folder": "Newsletters/Tech" },
  { "type": "flag", "value": "read" }
]
```

| Type d'action | Description | Paramètres |
|---|---|---|
| `move` | Déplacer vers un dossier IMAP | `folder` (nom du dossier) |
| `archive` | Archiver (retirer de l'inbox) | — |
| `delete` | Déplacer vers la corbeille | — |
| `flag` | Changer un flag | `value`: read, unread, important |
| `mark_spam` | Marquer comme spam | — |
| `block_sender` | Bloquer l'expéditeur | — |

### Exécution

```python
async def execute_actions(email: Email, actions: list[dict], trigger: str, rule_id: UUID = None):
    for action_def in actions:
        try:
            if action_def["type"] == "move":
                await imap_service.move(email.account_id, email.uid, action_def["folder"])
                email.folder = action_def["folder"]
            elif action_def["type"] == "flag":
                await imap_service.set_flag(email.account_id, email.uid, action_def["value"])
            # ... etc
            
            # Log l'action
            await save_action(
                email_id=email.id,
                action_type=action_def["type"],
                action_details=action_def,
                trigger=trigger,
                rule_id=rule_id,
                status="success",
                is_reversible=True
            )
        except Exception as e:
            await save_action(..., status="failed", error_message=str(e))
```

## Exemples de règles préconfigurées (suggestions)

Au premier lancement, InboxShield suggère des règles utiles :

| Nom | Type | Conditions | Actions |
|---|---|---|---|
| Spam → Junk | structured | `category = "spam"` | move → Spam |
| Phishing → Quarantaine | structured | `is_phishing = true` | move → InboxShield/Quarantine |
| Newsletters → dossier | structured | `category = "newsletter"` | move → Newsletters |
| Promotions → dossier | structured | `category = "promotion"` | move → Promotions |
| Notifications → lues | structured | `category = "notification"` | flag → read |

L'utilisateur peut les activer/désactiver/modifier librement.

---

*Feature précédente : [03c-SPAM-PHISHING-DETECTION.md](./03c-SPAM-PHISHING-DETECTION.md)*
*Feature suivante : [03e-REVIEW-QUEUE.md](./03e-REVIEW-QUEUE.md)*
