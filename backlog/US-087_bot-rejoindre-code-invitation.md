**ID :** US-087
**Titre :** Rejoindre un potager depuis Telegram avec un code d'invitation
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier invité à rejoindre le potager de quelqu'un
Je veux saisir mon code d'invitation directement dans Telegram
Afin de rejoindre le jardin sans ouvrir l'application web, là où j'ai reçu le code et où je vais de toute façon saisir mes événements

**Contexte fonctionnel :**
`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §4.2, §6.3 et §7.2 (numéro provisoire US-156), arbitrage
tranché au point ouvert §8.5 : **indispensable**. Le code d'invitation (8 caractères, table
`invitations`, US-048) circule par un canal externe — SMS, e-mail, oral, message Telegram. Aujourd'hui,
il ne peut être saisi que dans la PWA (`PotagerSelector`), ce qui impose un détour à quelqu'un dont le
premier contact concret avec l'application est souvent le bot.

Le bot reste par ailleurs **volontairement aveugle** au reste du cycle de vie : pas de `/creer`, pas
de `/archiver`, pas de `/supprimer` (§4.2 — actions rares, à champs multiples ou sensibles, réservées
à la PWA). `/rejoindre` est la seule exception, parce que c'est une action à un seul argument court.

La logique métier existe déjà intégralement : `accepter_invitation()` (`app/services/potagers.py`)
valide le code, gère l'expiration, la réutilisation et le cas « déjà membre ». Cette US n'ajoute
qu'une porte d'entrée Telegram.

**Critères d'acceptance :**
- [ ] CA1 : Nouvelle commande `/rejoindre <code>` enregistrée par le point d'enregistrement unique des
      commandes du bot, soumise au garde de liaison standard (US-045) : un chat non lié à un compte web
      est renvoyé vers le parcours de liaison, jamais rattaché à un potager
- [ ] CA2 : `/rejoindre` sans argument répond par un message d'aide court expliquant le format attendu
      et où trouver le code (« ton hôte le génère depuis l'application web »)
- [ ] CA3 : Un code valide rattache l'utilisateur au potager avec le rôle prévu par l'invitation, en
      réutilisant `accepter_invitation()` **sans dupliquer aucune règle de validation**
- [ ] CA4 : Le message de confirmation nomme le potager rejoint et le rôle obtenu, en français courant
      (« Tu as rejoint *Jardin des Lilas* en tant qu'éditeur »)
- [ ] CA5 : Chaque cas d'échec a son propre message, sans jargon ni trace technique : code inconnu,
      code expiré, code déjà utilisé, utilisateur déjà membre de ce potager
- [ ] CA6 : Si l'utilisateur n'avait **aucun** potager actif, le potager rejoint le devient
      immédiatement et le bot l'annonce ; s'il en avait déjà un, le potager actif **n'est pas modifié**
      — le bot indique alors comment basculer avec `/potager` (cohérent avec US-046 : aucune bascule silencieuse)
- [ ] CA7 : Le code est accepté quelle que soit sa casse et malgré des espaces parasites en début ou
      fin de saisie
- [ ] CA8 : Le ou les owners du potager ayant un compte Telegram lié sont informés de l'arrivée du
      nouveau membre
- [ ] CA9 : Zéro appel Groq : la commande est traitée en amont de toute classification d'intention,
      elle ne consomme aucun token
- [ ] CA10 : L'aide du bot (`/help`) mentionne `/rejoindre` dans la même section que `/potager` et `/lier`

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-045 (liaison Telegram et garde de commande), US-048 (`accepter_invitation`, codes d'invitation), US-046 (`/potager`, potager actif)
- Hors périmètre explicite : génération d'un code depuis le bot — les codes restent affichés uniquement dans la PWA (canal de copie fiable, §4.2)
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `bot.py` (nouvelle commande + enregistrement, message d'aide), aucune modification de `app/services/potagers.py` attendue au-delà de la réutilisation
- Respecter l'ordre critique des flux Telegram : la commande passe par le mécanisme de `CommandHandler`, elle n'interfère pas avec les priorités de `handle_text`/`handle_voice`
- Échapper les caractères Markdown du nom de potager dans les réponses (non-régression US-007)
- Ne pas journaliser le code d'invitation en clair au-delà de ce que fait déjà la couche services

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Rejoindre un potager depuis Telegram
  Given un utilisateur dont le compte Telegram est lié à son compte web
  And un code d'invitation valide "K7P2M9QX" pour le potager "Jardin des Lilas" avec le rôle éditeur
  When il envoie "/rejoindre K7P2M9QX"
  Then il devient membre de "Jardin des Lilas" avec le rôle éditeur
  And le bot le lui confirme en nommant le potager et le rôle

Scénario: Premier potager rejoint
  Given un utilisateur lié mais membre d'aucun potager
  When il rejoint un potager avec un code valide
  Then ce potager devient son potager actif
  And le bot lui indique qu'il peut désormais saisir ses événements

Scénario: Utilisateur ayant déjà un potager actif
  Given un utilisateur dont le potager actif est "Jardin de Vitry"
  When il rejoint "Jardin des Lilas" avec un code valide
  Then son potager actif reste "Jardin de Vitry"
  And le bot lui rappelle qu'il peut basculer avec /potager

Scénario: Code expiré
  Given un code d'invitation dont la date d'expiration est dépassée
  When l'utilisateur envoie "/rejoindre" avec ce code
  Then le bot répond que le code a expiré et qu'il faut en demander un nouveau
  And aucune appartenance n'est créée

Scénario: Chat non lié
  Given un chat Telegram non lié à un compte web
  When il envoie "/rejoindre K7P2M9QX"
  Then le bot le renvoie vers le parcours de liaison sans rattacher aucun potager

Scénario: Commande sans argument
  Given un utilisateur lié
  When il envoie "/rejoindre"
  Then le bot explique le format attendu et où obtenir un code
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `bot`
