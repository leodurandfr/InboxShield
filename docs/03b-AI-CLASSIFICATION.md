# Feature : Classification AI

> Phase 1 (MVP)

## Objectif

Classifier automatiquement chaque email entrant dans une catégorie, avec un score de confiance, en utilisant un LLM local (Ollama) ou cloud (Claude, OpenAI, Mistral).

## Pipeline de classification

```
Email (processing_status = 'pending')
        │
        ▼
   Expéditeur bloqué ?
        ├── OUI → skip (processing_status = 'skipped')
        │
        ▼
   Sender profile existant ?
        ├── OUI → Catégorie dominante (>80%, count >= 5) ?
        │            ├── OUI → Classification directe (classified_by = 'sender_profile')
        │            └── NON → Passer au LLM
        │
        ▼
   Règle structurée matchée ?
        ├── OUI → Classification par règle (classified_by = 'rule')
        │
        ▼
   Appel LLM
        │
        ▼
   Confiance >= seuil ?
        ├── OUI → status = 'auto' → Exécuter les actions
        └── NON → status = 'review' → Review Queue
```

Ce pipeline à 3 niveaux (sender_profile → rules → LLM) minimise les appels au LLM. Sur une boîte mature, on estime que **60-80% des emails** sont classés sans LLM.

## Interface LLM abstraite

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def classify(self, prompt: str) -> ClassificationResult:
        """Envoie un prompt et retourne la classification."""
        pass

class OllamaProvider(BaseLLMProvider):
    """Provider pour Ollama (local)."""
    
class AnthropicProvider(BaseLLMProvider):
    """Provider pour l'API Anthropic (Claude)."""

class OpenAIProvider(BaseLLMProvider):
    """Provider pour l'API OpenAI."""

class MistralProvider(BaseLLMProvider):
    """Provider pour l'API Mistral."""
```

**Sélection du provider :** Défini dans `settings.llm_provider`. Le service instancie le bon provider au démarrage.

## Prompt de classification

Le prompt est construit dynamiquement pour chaque email :

```
SYSTEM:
Tu es un assistant spécialisé dans la classification d'emails.
Classifie l'email suivant dans UNE des catégories : important, work, personal, 
newsletter, promotion, notification, spam, phishing, transactional.

Réponds UNIQUEMENT en JSON valide avec ce format :
{
  "category": "...",
  "confidence": 0.0-1.0,
  "explanation": "...",
  "is_spam": false,
  "is_phishing": false,
  "phishing_reasons": []
}

CORRECTIONS RÉCENTES (few-shot) :
- Email de "newsletter@figma.com", sujet "Figma Config 2025" → newsletter (initialement classé promotion)
- Email de "no-reply@amazon.fr", sujet "Votre commande a été expédiée" → transactional
[... max N exemples récents ...]

USER:
De : {from_name} <{from_address}>
À : {to_addresses}
Sujet : {subject}
Date : {date}
Pièces jointes : {attachment_names ou "Aucune"}

Corps :
{body_excerpt}
```

### Stratégies du prompt

- **Température basse (0.1)** : Réponses déterministes, moins de créativité, plus de cohérence
- **Format JSON strict** : Le LLM est contraint de répondre en JSON. Si le parsing échoue, retry 1 fois avec un prompt renforcé
- **Few-shot dynamique** : Les corrections récentes de l'utilisateur sont injectées comme exemples. Plus l'utilisateur corrige, plus le LLM s'améliore
- **Pas de system prompt trop long** : On garde le prompt court pour les modèles 7B (fenêtre de contexte limitée)

## Parsing de la réponse LLM

```python
async def parse_llm_response(raw: str) -> ClassificationResult:
    # 1. Tenter un JSON.parse direct
    # 2. Si échec : chercher le premier bloc {...} dans la réponse
    # 3. Si échec : regex sur les champs individuels
    # 4. Si échec : processing_status = 'failed'
    
    # Validation :
    # - category doit être dans la liste autorisée
    # - confidence entre 0.0 et 1.0
    # - is_phishing = True → phishing_reasons ne doit pas être vide
```

Le parsing est volontairement tolérant : les modèles 7B ne respectent pas toujours le format JSON (markdown autour, commentaires, champs en désordre…).

## Modèles recommandés

| Modèle | VRAM | Vitesse* | Qualité | Notes |
|---|---|---|---|---|
| `qwen2.5:7b` | ~5 GB | ~800ms | ★★★★ | **Recommandé.** Excellent en classification JSON |
| `mistral:7b` | ~5 GB | ~900ms | ★★★★ | Bon en français, légèrement moins structuré |
| `llama3:8b` | ~5.5 GB | ~1s | ★★★ | Plus généraliste, parfois verbose |
| `gemma2:9b` | ~6 GB | ~1.2s | ★★★★ | Bon en raisonnement, plus lent |
| `phi3:3.8b` | ~2.5 GB | ~400ms | ★★★ | Rapide mais moins fiable sur les cas limites |

*\*Vitesse estimée sur Mac Mini M4 Pro 24 GB*

Pour les providers cloud, Claude Haiku ou GPT-4o-mini sont recommandés (bon rapport qualité/coût pour de la classification).

## Métriques collectées

Chaque classification enregistre :
- `llm_provider` + `llm_model` — Pour comparer les performances
- `tokens_used` — Pour estimer les coûts (providers cloud)
- `processing_time_ms` — Pour monitorer les performances
- `classified_by` — Pour mesurer le ratio LLM vs sender_profile vs rule

Ces métriques alimentent les analytics (taux de classification directe, temps moyen, coût estimé).

## Traitement en batch

Au premier fetch (onboarding) ou en cas de retard de polling, plusieurs emails arrivent d'un coup. Le traitement est limité à **5 appels LLM concurrents** (configurable) pour :
- Ne pas surcharger Ollama (un seul modèle en mémoire)
- Éviter les rate limits des APIs cloud
- Garder le Mac Mini réactif

```python
semaphore = asyncio.Semaphore(5)

async def classify_batch(emails: list[Email]):
    tasks = [classify_with_semaphore(email, semaphore) for email in emails]
    await asyncio.gather(*tasks)
```

## Fallback en cas d'erreur LLM

| Erreur | Comportement |
|---|---|
| LLM timeout (>30s) | Retry 1 fois. Si échec → `processing_status = 'failed'` |
| JSON invalide | Retry avec prompt renforcé ("Réponds UNIQUEMENT en JSON"). Si échec → `failed` |
| Catégorie inconnue | Force la catégorie la plus proche ou → `review` |
| Ollama down | Tous les emails restent `pending`, retry au prochain cycle de polling |
| API cloud rate limited | Backoff exponentiel (1s, 2s, 4s…), max 3 retries |

Les emails en `failed` peuvent être reclassifiés manuellement ou via un bouton "Retry" dans le dashboard.

---

*Feature précédente : [03a-IMAP-CONNECTION.md](./03a-IMAP-CONNECTION.md)*
*Feature suivante : [03c-SPAM-PHISHING-DETECTION.md](./03c-SPAM-PHISHING-DETECTION.md)*
