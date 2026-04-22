# Feature : Analytics & Dashboard

> Phase 2 (base) — Phase 3 (avancé)

## Objectif

Fournir des statistiques visuelles sur l'activité email : volume, répartition par catégorie, top expéditeurs, détection de tendances, et performances du système de classification.

## Dashboard principal

Le dashboard est la page d'accueil de l'application. Il combine :

### 1. Indicateurs clés (KPIs)

Affichés en haut du dashboard sous forme de cartes :

| KPI | Source | Rafraîchissement |
|---|---|---|
| Emails reçus aujourd'hui | `COUNT(emails) WHERE date = today` | Temps réel |
| Emails en review | `COUNT(classifications) WHERE status = 'review'` | Temps réel |
| Phishing bloqués (ce mois) | `COUNT(classifications) WHERE is_phishing AND month = current` | Horaire |
| Spam filtré (ce mois) | `COUNT(classifications) WHERE is_spam AND month = current` | Horaire |
| Taux de classification auto | `classifications WHERE classified_by != 'manual' / total` | Horaire |
| Threads en attente de réponse | `COUNT(email_threads) WHERE awaiting_response = TRUE` | Temps réel |

### 2. Feed d'activité

Flux chronologique des événements récents, alimenté par `activity_logs` :

```
🛡️  Phishing bloqué — "Vérifiez votre compte PayPal" de security@paypa1.xyz
    il y a 12 minutes

📂  3 newsletters déplacées vers Newsletters
    il y a 25 minutes

✅  Review approuvée — email de contact@freelance.com classé "work"
    il y a 1 heure

⚠️  Erreur de polling sur GMX — Connexion timeout
    il y a 2 heures
```

### 3. Répartition par catégorie

Graphique en donut/pie chart montrant la répartition des emails classifiés :

Données : `GROUP BY category, COUNT(*)` sur les emails de la période sélectionnée.

Périodes : Aujourd'hui, 7 jours, 30 jours, 90 jours, tout.

### 4. Volume quotidien

Graphique en barres ou courbe montrant le volume d'emails par jour sur les 30 derniers jours, empilé par catégorie.

### 5. Top expéditeurs

Tableau des expéditeurs les plus actifs :

| Expéditeur | Emails | Catégorie principale | Dernière réception |
|---|---|---|---|
| notifications@linkedin.com | 89 | notification | Aujourd'hui |
| newsletter@substack.com | 24 | newsletter | Hier |
| no-reply@amazon.fr | 18 | transactional | Aujourd'hui |

Source : `sender_profiles` trié par `total_emails DESC`, limité à 20.

## Analytics détaillées (Phase 3)

### Tendances

- **Volume par semaine/mois** : Courbe de tendance, détection d'augmentation anormale
- **Évolution du spam** : Le volume de spam augmente ou diminue ?
- **Heures d'activité** : À quelle heure les emails arrivent (heatmap jour × heure)

### Performances du système

| Métrique | Source | Utilité |
|---|---|---|
| Temps moyen de classification | `AVG(classifications.processing_time_ms)` | Monitorer la performance d'Ollama |
| Taux de review | `COUNT(status='review') / COUNT(*)` | Le seuil de confiance est-il bien calibré ? |
| Taux de correction | `COUNT(status='corrected') / COUNT(*)` | Le LLM fait-il beaucoup d'erreurs ? |
| Classification directe vs LLM | `COUNT(classified_by='sender_profile') vs COUNT(classified_by='llm')` | L'apprentissage fonctionne ? |
| Tokens consommés (cloud) | `SUM(classifications.tokens_used)` | Estimation du coût |

### Matrice de confusion

Pour les utilisateurs avancés : tableau montrant les corrections les plus fréquentes (quelle catégorie est confondue avec quelle autre).

| Proposé \ Corrigé | newsletter | promotion | notification |
|---|---|---|---|
| **newsletter** | — | 12 | 3 |
| **promotion** | 8 | — | 1 |
| **notification** | 2 | 0 | — |

Source : `GROUP BY original_category, corrected_category, COUNT(*)` sur la table `corrections`.

## Cache et performance

Les analytics sont pré-calculées pour éviter des requêtes lourdes à chaque affichage :

- **Job `refresh_analytics`** : Tourne toutes les heures via APScheduler
- **Stockage** : Les résultats agrégés sont mis en cache (cache applicatif Python ou table dédiée)
- **Dashboard temps réel** : Les KPIs simples (compteurs) sont calculés en direct. Les graphiques utilisent le cache

## Export (Phase 3)

- **CSV** : Export des emails classifiés, corrections, stats expéditeurs
- **PDF** : Rapport mensuel avec les KPIs et graphiques (génération via `weasyprint` ou similaire)

---

*Feature précédente : [03g-REPLY-TRACKING.md](./03g-REPLY-TRACKING.md)*
*Document suivant : [04-API-ENDPOINTS.md](../04-API-ENDPOINTS.md)*
