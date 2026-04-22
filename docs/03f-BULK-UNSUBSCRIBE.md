# Feature : Bulk Unsubscribe

> Phase 2

## Objectif

Identifier toutes les newsletters et abonnements, afficher des statistiques de lecture, et permettre la désinscription en un clic.

## Détection des newsletters

### Sources de détection

1. **Header `List-Unsubscribe`** — Standard RFC 2369, présent dans la majorité des newsletters légitimes
2. **Classification AI** — Catégorie `newsletter` ou `promotion` assignée par le LLM
3. **Sender profile** — `is_newsletter = TRUE` dans `sender_profiles`
4. **Patterns HTML** — Liens contenant "unsubscribe", "désabonner", "opt-out" dans le `body_html_excerpt`

### Extraction du lien de désinscription

```python
async def extract_unsubscribe_info(email: Email) -> UnsubscribeInfo | None:
    # 1. Header List-Unsubscribe (le plus fiable)
    list_unsub = email.headers.get("List-Unsubscribe", "")
    if list_unsub:
        # Peut contenir une URL et/ou un mailto
        # Format : <https://example.com/unsub>, <mailto:unsub@example.com>
        urls = re.findall(r'<(https?://[^>]+)>', list_unsub)
        mailtos = re.findall(r'<(mailto:[^>]+)>', list_unsub)
        
        # Vérifier List-Unsubscribe-Post (one-click RFC 8058)
        has_one_click = "List-Unsubscribe=One-Click" in email.headers.get("List-Unsubscribe-Post", "")
        
        return UnsubscribeInfo(
            link=urls[0] if urls else None,
            mailto=mailtos[0] if mailtos else None,
            method="http_post" if has_one_click else ("http_get" if urls else "mailto")
        )
    
    # 2. Fallback : chercher dans le HTML
    if email.body_html_excerpt:
        soup = BeautifulSoup(email.body_html_excerpt, "html.parser")
        for link in soup.find_all("a"):
            text = link.get_text().lower()
            href = link.get("href", "")
            if any(kw in text for kw in ["unsubscribe", "désabonner", "désinscri", "opt-out", "se désinscrire"]):
                return UnsubscribeInfo(link=href, method="manual")
    
    return None
```

## Méthodes de désinscription

| Méthode | Fiabilité | Processus |
|---|---|---|
| `http_post` (One-Click RFC 8058) | ★★★★★ | POST sur l'URL avec `List-Unsubscribe=One-Click` → instantané |
| `http_get` | ★★★★ | GET sur l'URL de désinscription → peut nécessiter une confirmation |
| `mailto` | ★★★ | Envoi d'un email vide à l'adresse de désinscription |
| `manual` | ★★ | Lien trouvé dans le HTML → l'utilisateur doit cliquer et confirmer manuellement |

### Exécution automatique

```python
async def unsubscribe(newsletter: Newsletter) -> bool:
    newsletter.subscription_status = "unsubscribing"
    
    if newsletter.unsubscribe_method == "http_post":
        # RFC 8058 One-Click
        response = await httpx.post(
            newsletter.unsubscribe_link,
            data={"List-Unsubscribe": "One-Click"},
            timeout=10
        )
        success = response.status_code in (200, 202, 204)
        
    elif newsletter.unsubscribe_method == "http_get":
        response = await httpx.get(newsletter.unsubscribe_link, timeout=10)
        success = response.status_code == 200
        
    elif newsletter.unsubscribe_method == "mailto":
        # Envoyer un email vide via SMTP
        await smtp_service.send(
            account_id=newsletter.account_id,
            to=newsletter.unsubscribe_mailto,
            subject="Unsubscribe",
            body=""
        )
        success = True  # On ne peut pas vérifier la confirmation
    
    else:  # manual
        success = False  # L'utilisateur doit le faire lui-même
    
    newsletter.subscription_status = "unsubscribed" if success else "failed"
    newsletter.unsubscribed_at = datetime.utcnow() if success else None
    
    return success
```

## Interface utilisateur

### Vue liste des newsletters

| Newsletter | Reçus | Lus | Taux | Fréquence | Action |
|---|---|---|---|---|---|
| Figma Newsletter | 24 | 18 | 75% | ~7 jours | [Se désabonner] |
| Amazon Deals | 156 | 3 | 2% | ~1 jour | [Se désabonner] |
| Substack - Tech Digest | 12 | 12 | 100% | ~7 jours | Garder |
| LinkedIn Notifications | 89 | 0 | 0% | ~1 jour | [Se désabonner] |

### Indicateurs visuels

- **Taux de lecture < 10%** → Badge rouge "Jamais lu" → suggestion forte de désinscription
- **Taux de lecture > 70%** → Badge vert "Actif" → pas de suggestion
- **Fréquence > 1/jour** → Badge orange "Très fréquent"
- **Méthode = manual** → Icône info "Désinscription manuelle requise"

### Actions en masse

- "Se désabonner de tout ce que je ne lis pas" (taux < 10%)
- Sélection multiple → "Se désabonner des sélectionnés"
- Filtre par statut : tous, abonnés, désabonnés, échoués

## Calcul du taux de lecture

Le taux est estimé à partir du flag `\Seen` IMAP :

```python
async def update_newsletter_stats(newsletter: Newsletter):
    emails = await get_emails_from_sender(newsletter.account_id, newsletter.sender_address)
    
    newsletter.total_received = len(emails)
    newsletter.total_read = sum(1 for e in emails if e.is_read)
    
    if len(emails) >= 2:
        dates = sorted([e.date for e in emails])
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        newsletter.frequency_days = sum(intervals) / len(intervals)
```

## Limitations

- **`http_get` désinscriptions** : Certains services redirigent vers une page de confirmation. InboxShield ne peut pas cliquer sur un bouton de confirmation (pas de headless browser). Dans ce cas, le statut passe à `failed` avec un message invitant l'utilisateur à cliquer manuellement.
- **Newsletters sans lien de désinscription** : Certaines newsletters peu scrupuleuses n'incluent pas de header `List-Unsubscribe` ni de lien dans le body. Seul recours : bloquer l'expéditeur via `sender_profiles.is_blocked`.
- **Délai de prise en compte** : Après désinscription, les newsletters peuvent continuer à arriver pendant quelques jours/semaines.

---

*Feature précédente : [03e-REVIEW-QUEUE.md](./03e-REVIEW-QUEUE.md)*
*Feature suivante : [03g-REPLY-TRACKING.md](./03g-REPLY-TRACKING.md)*
