"""Prompt templates for LLM-based email classification and rule interpretation."""

CLASSIFICATION_SYSTEM_PROMPT = """\
Tu es un assistant spécialisé dans la classification d'emails personnels.
Classifie l'email suivant dans UNE des catégories ci-dessous.

CATÉGORIES (choisir exactement une) :
- important : UNIQUEMENT les emails nécessitant une action URGENTE de l'utilisateur sur ses finances ou sa sécurité réelle. Exemples : facture impayée avec échéance proche, alerte de sécurité Google/Apple sur le PROPRE compte de l'utilisateur, courrier administratif (impôts, banque) demandant une action. Un email n'est PAS "important" simplement parce qu'il contient le mot "important", "urgent" ou "sécurité".
- work : emails liés au TRAVAIL PROFESSIONNEL DIRECT (collègues, clients, recruteurs, missions freelance). Un email n'est "work" que s'il implique une interaction professionnelle directe. Les newsletters/marketing d'outils pros (Dribbble, GitHub blog, Figma updates) ne sont PAS "work".
- personal : emails de proches (famille, amis), conversations PRIVÉES directes entre personnes. L'expéditeur doit être une vraie personne, pas une plateforme. Exemples : "Re: aspirateur" de "sophie Durand".
- newsletter : emails éditoriaux récurrents (actualités, digests, blogs, contenus éducatifs, mises à jour produit). Contiennent du contenu informatif et souvent un lien de désinscription. Inclut les mises à jour de fonctionnalités de services, les articles, les annonces de produit.
- promotion : offres commerciales, réductions, soldes, marketing direct, publicités de marques, invitations à acheter.
- notification : alertes AUTOMATIQUES envoyées par des plateformes ou services. Le critère clé : l'email est généré automatiquement par un système, pas écrit par un humain. Inclut : alertes de connexion, nouveaux messages sur une plateforme, likes, commentaires, demandes d'avis, réponses à des messages sur des plateformes (HomeExchange, LinkedIn, GrabCAD), alertes Dependabot, mises à jour CGV/politique, rappels automatiques, confirmations de connexion à un nouvel appareil.
- spam : courrier indésirable non sollicité, publicité agressive, arnaques commerciales.
- phishing : tentative de vol d'identifiants ou arnaque. RÈGLE ABSOLUE : un email n'est phishing QUE si l'ANALYSE_EXPÉDITEUR détecte une usurpation d'identité (le nom prétend être une marque connue MAIS le domaine email est complètement différent, ex: "PayPal" envoyé depuis ewartista.org). Si l'ANALYSE_EXPÉDITEUR indique "EXPÉDITEUR VÉRIFIÉ" ou ne détecte aucune usurpation, l'email n'est PAS du phishing, même si des URLs semblent suspectes. Des URLs inhabituelles (tracking, redirections, domaines tiers) sont NORMALES dans les emails commerciaux.
- transactional : tout email automatique déclenché par une action de l'utilisateur. Inclut : confirmations de commande, reçus de paiement, factures, billets, codes de vérification, réinitialisations de mot de passe, activations de compte, confirmations de réservation, documents contractuels, accusés de réception de réclamation.

RÈGLES DE DÉCISION :
1. L'expéditeur est une adresse noreply/notification/system d'une plateforme ? → C'est "notification" ou "transactional", JAMAIS "personal".
2. L'email est envoyé suite à une ACTION de l'utilisateur (commande, reset password, inscription, réclamation) ? → "transactional".
3. L'email est envoyé AUTOMATIQUEMENT par une plateforme SANS action de l'utilisateur (alerte, nouveau message, rappel, mise à jour CGV) ? → "notification".
4. Le contenu est un article, digest, mise à jour produit, contenu éducatif ? → "newsletter".
5. L'email propose un achat, une réduction, une offre ? → "promotion".
6. Pour "phishing" : la condition OBLIGATOIRE est l'usurpation d'identité de l'expéditeur (ANALYSE_EXPÉDITEUR). Si l'expéditeur est vérifié/légitime, NE JAMAIS classifier en phishing, même avec des URLs suspectes. Les URLs de tracking, redirections, domaines tiers sont NORMAUX dans les emails commerciaux. Classifier en phishing UNIQUEMENT quand le nom d'expéditeur prétend être une marque connue (PayPal, EDF, Ameli...) mais le domaine email est complètement différent.
7. Les emails transférés (sujet commençant par "Fwd:" ou "Tr:") par un contact personnel (gmail.com, outlook.com, etc.) contiennent naturellement des URLs d'autres services — ce n'est PAS du phishing. Classe-les selon le contenu transféré (personal, transactional, etc.).
8. Les organismes publics français (URSSAF, CAF, impôts, Ameli) utilisent légitimement plusieurs domaines associés. Par exemple, urssaf.fr peut contenir des liens vers net-entreprises.fr, letese.urssaf.fr, etc. — ce sont des services liés, PAS du phishing.
9. RAPPEL CRITIQUE — FAUX POSITIFS PHISHING : Si l'ANALYSE_EXPÉDITEUR dit "✓ EXPÉDITEUR VÉRIFIÉ", l'email est GARANTI non-phishing. Les emails légitimes contiennent SOUVENT des URLs vers des domaines tiers (tracking, réseaux sociaux, partenaires, analytics). C'est NORMAL. Ne JAMAIS classifier en phishing sur la base d'URLs seules.

EXEMPLES :
- "Réinitialisez votre mot de passe" de noreply@mcdonalds.fr → transactional (reset légitime)
- "Vérification du Compte Xiaomi" de noreply@notice.xiaomi.com → transactional (code vérification)
- "Vous avez une nouvelle demande de Priscilla" de notifications@homeexchange.com → notification (alerte plateforme)
- "RE : Alba a répondu à votre message" de notifications@homeexchange.com → notification (réponse sur plateforme)
- "Votre échange est finalisé" de notifications@homeexchange.com → transactional (confirmation)
- "Re: aspirateur" de "sophie Durand" → personal (conversation entre proches)
- "New Project Briefs" de no-reply@dribbble.com → newsletter (contenu éditorial de plateforme)
- "Important Update" de mail@fontba.se → notification (mise à jour logiciel)
- "Votre rendez-vous demain" de no-reply@doctolib.fr → transactional (rappel de réservation)
- "Donnez votre avis" de noreply@planity.com → notification (demande automatique)
- "Réclamation produit dysfonctionnel" de france@muziker.com → transactional (échange SAV)
- "Connexion nouvel appareil" de security@facebookmail.com → notification (alerte automatique)
- "[GitHub] Dependabot alerts" → notification (alerte automatique)
- "Pull request review requested" → work (contexte professionnel direct)
- "Demandez votre remboursement" de edf@espacionewen.cl → phishing (nom "EDF" mais domaine chilien sans rapport)
- "Document de votre Urssaf" de dcl.limousin@urssaf.fr avec liens vers net-entreprises.fr → notification (URSSAF légitime, domaines gouvernementaux liés)
- "Fwd: Itinéraire de Voyage" de deliere.claire@gmail.com avec liens ryanair.com → personal (email transféré par un contact)
- "Fwd: Votre réservation" de ami@outlook.com avec liens booking.com → personal (forward légitime)

Réponds UNIQUEMENT en JSON valide :
{
  "category": "...",
  "confidence": 0.0,
  "explanation": "...",
  "is_spam": false,
  "is_phishing": false,
  "phishing_reasons": []
}

Règles JSON :
- confidence : entre 0.0 et 1.0. SOIS STRICT et CONSERVATEUR. Calibration :
  * 0.90-1.00 : RÉSERVÉ aux cas TRIVIAUX sans aucune ambiguïté (ex: reçu Amazon → transactional, noreply@github.com "Your push triggered a workflow" → notification)
  * 0.75-0.89 : Confiant — signaux clairs mais pas trivial (ex: newsletter avec lien désinscription, email pro d'un collègue connu)
  * 0.55-0.74 : Probable — catégorie la plus vraisemblable mais d'autres sont possibles (ex: email commercial qui pourrait être newsletter ou promotion)
  * 0.30-0.54 : Incertain — plusieurs catégories plausibles, peu de signaux distinctifs
  * La MAJORITÉ des emails doivent avoir une confiance entre 0.55 et 0.85. Un score > 0.90 doit être RARE et réservé aux cas évidents.
- is_phishing : true UNIQUEMENT si des URLs suspectes sont détectées ou si le domaine de l'expéditeur ne correspond pas au service prétendu
- phishing_reasons : liste les raisons concrètes (URLs, domaine suspect)
- explanation : une phrase courte justifiant la catégorie"""

CLASSIFICATION_FEW_SHOT_HEADER = """
CORRECTIONS RÉCENTES (apprends de ces exemples) :"""

CLASSIFICATION_USER_TEMPLATE = """\
De : {from_name} <{from_address}>
Reply-To : {reply_to}
À : {to_addresses}
Sujet : {subject}
Date : {date}
Pièces jointes : {attachments}
{sender_analysis}{url_analysis}
Corps :
{body_excerpt}"""


RULE_INTERPRETATION_SYSTEM_PROMPT = """\
Tu es un assistant de tri d'emails. On te donne une règle en langage naturel et \
un email. Détermine si la règle s'applique à cet email.

Réponds UNIQUEMENT en JSON valide :
{
  "matches": true,
  "reason": "explication courte"
}"""

RULE_INTERPRETATION_USER_TEMPLATE = """\
RÈGLE : "{rule_text}"

EMAIL :
De : {from_name} <{from_address}>
Sujet : {subject}
Catégorie : {category}
Date : {date}
Corps (extrait) :
{body_excerpt}"""


def build_classification_prompt(
    from_name: str,
    from_address: str,
    to_addresses: str,
    subject: str,
    date: str,
    attachments: str,
    body_excerpt: str,
    few_shot_examples: str = "",
    url_analysis: str = "",
    sender_analysis: str = "",
    reply_to: str = "",
) -> tuple[str, str]:
    """Build system + user prompts for classification.

    Returns (system_prompt, user_prompt).
    """
    system = CLASSIFICATION_SYSTEM_PROMPT
    if few_shot_examples:
        system += CLASSIFICATION_FEW_SHOT_HEADER + "\n" + few_shot_examples

    # Format URL analysis section
    url_section = ""
    if url_analysis:
        url_section = f"\nANALYSE_URLS :\n{url_analysis}\n"

    # Format sender analysis section (brand impersonation check)
    sender_section = ""
    if sender_analysis:
        sender_section = f"\nANALYSE_EXPÉDITEUR :\n{sender_analysis}\n"

    user = CLASSIFICATION_USER_TEMPLATE.format(
        from_name=from_name or "?",
        from_address=from_address,
        reply_to=reply_to or "(identique à l'expéditeur)",
        to_addresses=to_addresses or "?",
        subject=subject or "(sans sujet)",
        date=date,
        attachments=attachments or "Aucune",
        sender_analysis=sender_section,
        url_analysis=url_section,
        body_excerpt=body_excerpt or "(vide)",
    )

    return system, user


def build_rule_interpretation_prompt(
    rule_text: str,
    from_name: str,
    from_address: str,
    subject: str,
    category: str,
    date: str,
    body_excerpt: str,
) -> tuple[str, str]:
    """Build system + user prompts for natural language rule interpretation.

    Returns (system_prompt, user_prompt).
    """
    user = RULE_INTERPRETATION_USER_TEMPLATE.format(
        rule_text=rule_text,
        from_name=from_name or "?",
        from_address=from_address,
        subject=subject or "(sans sujet)",
        category=category,
        date=date,
        body_excerpt=body_excerpt or "(vide)",
    )

    return RULE_INTERPRETATION_SYSTEM_PROMPT, user
