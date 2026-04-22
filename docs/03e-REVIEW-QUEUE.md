# Feature : Review Queue & Apprentissage

> Phase 1 (MVP)

## Objectif

Les emails classifiés avec une confiance inférieure au seuil (défaut : 0.7) sont mis en attente dans une file de review. L'utilisateur valide ou corrige la classification, et ces corrections alimentent l'apprentissage du système.

## Flux de la Review Queue

```
Email classifié avec confiance < seuil
        │
        ▼
  classification.status = 'review'
        │
        ▼
  Affiché dans la Review Queue (dashboard)
        │
        ├── Utilisateur approuve → status = 'approved'
        │                          → Exécuter les actions
        │                          → Mettre à jour sender_category_stats (+1)
        │
        └── Utilisateur corrige → status = 'corrected'
                                 → Créer une entrée corrections
                                 → Exécuter les actions (nouvelle catégorie)
                                 → Mettre à jour sender_category_stats (+2 corrected)
                                 → Mettre à jour sender_profile si nécessaire
```

## Interface de la Review Queue

Chaque email dans la queue affiche :
- **Expéditeur** + **sujet** + **date**
- **Catégorie proposée** par le LLM avec le **score de confiance** (barre visuelle)
- **Explication** du LLM (pourquoi cette catégorie)
- **Extrait du corps** (body_excerpt)
- **Boutons d'action rapide :**
  - ✓ Approuver (garde la catégorie proposée)
  - ✎ Corriger (dropdown avec les autres catégories)
  - ⊘ Ignorer (laisser en review pour plus tard)

### Actions en masse

- "Tout approuver" (pour les utilisateurs qui font confiance au LLM)
- "Approuver toutes les newsletters" (filtre par catégorie)
- Sélection multiple + action commune

## Mécanisme d'apprentissage

L'apprentissage repose sur deux mécanismes complémentaires :

### 1. Mémorisation par expéditeur (`sender_category_stats`)

Chaque classification (auto ou manuelle) incrémente le compteur de la catégorie pour cet expéditeur :

```python
async def update_sender_stats(email: Email, category: str, is_correction: bool):
    profile = await get_or_create_sender_profile(email.account_id, email.from_address)
    
    stats = await get_or_create_category_stats(profile.id, category)
    stats.count += 1
    if is_correction:
        stats.corrected_count += 2  # Poids double pour les corrections
    stats.last_seen_at = datetime.utcnow()
    
    # Mettre à jour la catégorie principale
    all_stats = await get_all_category_stats(profile.id)
    total = sum(s.count for s in all_stats)
    dominant = max(all_stats, key=lambda s: s.count)
    
    profile.primary_category = dominant.category
    profile.total_emails = total
```

**Seuil de classification directe :**
- `count >= 5` pour cette catégorie ET représente > 80% du total → classification sans LLM
- Sinon → LLM (le contexte du mail est nécessaire pour distinguer)

### 2. Few-shot dans le prompt LLM (`corrections`)

Les N dernières corrections (défaut : 10) sont injectées dans le prompt du LLM :

```python
async def build_few_shot_examples(account_id: UUID, max_examples: int = 10) -> str:
    corrections = await get_recent_corrections(account_id, limit=max_examples)
    
    examples = []
    for c in corrections:
        email = await get_email(c.email_id)
        examples.append(
            f'- Email de "{email.from_address}", sujet "{email.subject}" '
            f'→ {c.corrected_category} (initialement classé {c.original_category})'
        )
    
    return "\n".join(examples)
```

Ce mécanisme permet au LLM de "voir" les préférences de l'utilisateur et d'adapter ses futures classifications.

## Évolution du seuil de confiance

Le seuil de confiance (défaut : 0.7) détermine quels emails passent en review :

| Seuil | Comportement |
|---|---|
| 0.9 | Très conservateur : beaucoup d'emails en review, peu d'erreurs auto |
| 0.7 | **Équilibré (défaut)** : bon compromis confiance/volume |
| 0.5 | Permissif : peu de review, plus de risques d'erreurs |
| 0.0 | Tout est auto (pas de review, mode YOLO) |

L'utilisateur peut ajuster ce seuil par compte (`account_settings.confidence_threshold`) ou globalement (`settings.confidence_threshold`).

## Auto-mode vs Manual-mode

| Mode | Comportement |
|---|---|
| `auto_mode = TRUE` (défaut) | Confiance ≥ seuil → action exécutée automatiquement. Confiance < seuil → Review Queue |
| `auto_mode = FALSE` | **Tout** passe par la Review Queue. Rien n'est exécuté automatiquement. Utile au début pour valider le comportement du LLM |

**Recommandation onboarding :** Commencer en `auto_mode = FALSE` pendant quelques jours, corriger les erreurs, puis passer en `auto_mode = TRUE` une fois satisfait.

## Gestion du volume

Pour éviter que la review queue ne devienne ingérable :
- **Tri par confiance croissante** : Les emails les moins sûrs apparaissent en premier
- **Groupement par expéditeur** : "5 emails de newsletter@substack.com classés promotion — Tout approuver ?"
- **Expiration** : Après X jours en review (configurable, défaut : 7), les emails sont auto-approuvés avec la catégorie proposée
- **Compteur visible** : Badge dans la navigation avec le nombre d'emails en attente

---

*Feature précédente : [03d-RULES-ENGINE.md](./03d-RULES-ENGINE.md)*
*Feature suivante : [03f-BULK-UNSUBSCRIBE.md](./03f-BULK-UNSUBSCRIBE.md)*
