# Feature : Détection Spam & Phishing

> Phase 1 (basique) — Phase 2 (avancée)

## Objectif

Détecter les emails de spam et les tentatives de phishing/arnaque via l'analyse combinée du LLM et de règles heuristiques. Les phishing détectés sont automatiquement mis en quarantaine.

## Différence spam vs phishing

| | Spam | Phishing |
|---|---|---|
| **Intent** | Commercial non sollicité | Vol d'identifiants, arnaque financière |
| **Danger** | Nuisance | Risque de sécurité réel |
| **Action** | Déplacer vers Spam | **Quarantaine** + alerte utilisateur |
| **Détection** | Patterns de contenu | Analyse d'URLs + patterns d'arnaque |

## Pipeline de détection (Phase 1)

La détection spam/phishing fait partie du prompt de classification standard. Le LLM évalue simultanément la catégorie ET le caractère frauduleux :

```json
{
  "category": "phishing",
  "confidence": 0.95,
  "explanation": "Faux email PayPal demandant une vérification de compte",
  "is_spam": false,
  "is_phishing": true,
  "phishing_reasons": [
    "Expéditeur prétend être PayPal mais domaine = paypa1-security.xyz",
    "URL dans le corps ne pointe pas vers paypal.com",
    "Urgence artificielle : 'Votre compte sera suspendu sous 24h'"
  ]
}
```

## Analyse heuristique des URLs (Phase 2)

En plus du LLM, des règles automatiques analysent les URLs extraites dans `email_urls` :

### Vérifications automatiques

| Règle | Détection | Exemple |
|---|---|---|
| **URL ≠ texte affiché** | Le `href` ne correspond pas au texte du lien | Texte : "paypal.com" → href : "paypa1-secure.xyz" |
| **Homoglyphes** | Caractères visuellement similaires dans le domaine | "аpple.com" (а cyrillique) vs "apple.com" |
| **Raccourcisseurs** | URL raccourcie dans un email "officiel" | bit.ly/xyz dans un mail soi-disant de ta banque |
| **Sous-domaine trompeur** | Domaine légitime en sous-domaine | "paypal.com.malicious.xyz" |
| **IP directe** | URL pointant vers une IP au lieu d'un domaine | "http://192.168.1.1/login" |
| **Nombre excessif d'URLs** | Email avec 10+ liens (typique des scams) | Offre "trop belle pour être vraie" |

### Implémentation

```python
def analyze_urls(email_id: UUID, urls: list[ExtractedUrl]) -> list[SuspiciousUrl]:
    suspicious = []
    for url in urls:
        reasons = []
        
        # Texte affiché ≠ URL réelle
        if url.display_text and url.display_text != url.href:
            display_domain = extract_domain(url.display_text)
            actual_domain = extract_domain(url.href)
            if display_domain and display_domain != actual_domain:
                reasons.append(f"Lien trompeur : affiche '{display_domain}' mais pointe vers '{actual_domain}'")
        
        # Homoglyphes
        if has_homoglyphs(url.domain):
            reasons.append(f"Domaine avec caractères suspects : {url.domain}")
        
        # Raccourcisseur
        if url.domain in SHORTENER_DOMAINS:
            reasons.append(f"Raccourcisseur d'URL ({url.domain}) dans un email officiel")
        
        # IP directe
        if is_ip_address(url.domain):
            reasons.append("URL pointant vers une adresse IP directe")
        
        if reasons:
            suspicious.append(SuspiciousUrl(url=url, reasons=reasons))
    
    return suspicious
```

## Patterns de phishing courants (Phase 2)

Le LLM est guidé par des indicateurs supplémentaires ajoutés au prompt :

```
INDICATEURS DE PHISHING À VÉRIFIER :
- Urgence artificielle ("compte suspendu", "action requise immédiatement")
- Demande d'identifiants ou d'informations bancaires
- Fautes d'orthographe dans un email "officiel"
- Expéditeur ne correspondant pas au domaine prétendu
- Pièce jointe suspecte (.exe, .scr, .zip non sollicité)
- Offre trop belle pour être vraie (gain, héritage, lot gagné)
- Pression émotionnelle (menace, peur, curiosité)
```

## Actions automatiques

| Détection | Action par défaut | Configurable |
|---|---|---|
| `is_spam = true` | Déplacer vers le dossier Spam | Oui (`account_settings.default_category_action`) |
| `is_phishing = true` | Déplacer vers `InboxShield/Quarantine` | Oui (`phishing_auto_quarantine`) |
| `is_phishing = true` + haute confiance | Quarantaine + `activity_logs` avec `severity = 'warning'` | — |

## Quarantaine

Le dossier `InboxShield/Quarantine` est créé automatiquement sur le serveur IMAP lors de la première détection de phishing. Les emails en quarantaine :
- Sont visibles dans le dashboard avec un badge d'alerte
- Peuvent être restaurés (déplacés vers Inbox) si c'est un faux positif
- La restauration crée une correction et met à jour le `sender_profile`

## Métriques

- Nombre de phishing détectés (par jour/semaine/mois)
- Taux de faux positifs (phishing restaurés par l'utilisateur)
- URLs suspectes les plus fréquentes
- Domaines les plus ciblés

---

*Feature précédente : [03b-AI-CLASSIFICATION.md](./03b-AI-CLASSIFICATION.md)*
*Feature suivante : [03d-RULES-ENGINE.md](./03d-RULES-ENGINE.md)*
