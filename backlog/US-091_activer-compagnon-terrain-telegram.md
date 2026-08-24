**ID :** US-091
**Titre :** Activer son compagnon de terrain Telegram en un seul geste
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que jardinier venant de créer son compte et son premier potager
Je veux activer mon compagnon de terrain en un seul geste depuis l'application web
Afin de dicter mes observations à la voix, les mains dans la terre, et de recevoir mes rappels et alertes directement sur mon téléphone

**Contexte fonctionnel :**
Seconde moitié de l'US-089 scindée (voir US-090 pour la première). US-089 est remplacée par
US-090 + US-091 et doit être archivée avec une note de renvoi.

**Principe technique fondateur, à ne jamais perdre de vue :**
> Un bot Telegram ne peut **jamais** initier une conversation. Seule une pression sur `START`
> débloque le droit d'envoyer des messages proactifs (rappels d'arrosage, alertes gel,
> notifications de potager). Un utilisateur « connecté » par un Login Widget mais qui n'a jamais
> pressé `START` recevrait un `403 Forbidden` sur toute tentative d'envoi.
>
> L'objectif de l'onboarding n'est donc pas « récupérer le `chat_id` », c'est **obtenir la pression
> sur START**. Le deep-link `?start=<code>` est le seul mécanisme qui garantit liaison *et* canal
> de push ouvert, en un seul geste. C'est ce qui invalide le CA16 de l'US-089 initiale.

**Reframing éditorial :** Telegram n'est pas « un compte à connecter », c'est **un compagnon de
terrain à activer**. On vend la voix et les rappels, pas une application de messagerie. Ce
positionnement dépasse la copie de cette US : il mérite d'être remonté dans les principes produit.

*État du socle, vérifié dans le code au moment de la rédaction — l'essentiel du cadrage initial
existe déjà et ne doit surtout pas être réimplémenté :*
- **La table de tokens existe déjà** : `liaisons_telegram` (US-045) — code à usage unique, TTL
  10 minutes, refus des codes expirés, déjà utilisés, ou d'un chat déjà lié à un autre compte
  (`app/services/liaison_telegram.py`). Son alphabet (`23456789ABCDEFGHJKMNPQRSTUVWXYZ`, 8
  caractères) est **déjà compatible** avec la contrainte de payload Telegram (base64url, ≤ 64
  caractères). Il n'y a donc **aucune table `telegram_link_tokens` à créer**, aucun nouveau format
  de jeton, aucune migration
- **`users.potager_actif_id` existe déjà** (US-046) : aucun `ALTER TABLE` à prévoir. La sélection
  automatique quand l'utilisateur n'a qu'un seul potager, le choix explicite via `/potager`, et le
  message de blocage quand il n'a aucun potager sont **déjà implémentés**
  (`app/services/potager_actif.py::resoudre_tenant_context`, appelé à chaque message du bot)
- **`/start` est déjà exempté du garde de liaison** (`_COMMANDES_SANS_GARDE_LIAISON` dans `bot.py`) :
  le point d'accroche du deep-link existe, sans changement d'architecture
- **La déliaison existe déjà** : `/delier` côté bot et `POST /auth/lien/delier` + `DelierTelegram.jsx`
  côté PWA (US-050)
- **Le canal de push existe déjà** : `app/services/telegram_notify.envoyer_message`, utilisé par
  les notifications d'archivage de potager (US-083)
- **Le point d'entrée PWA existe déjà** mais sous une forme et un intitulé à revoir : la modale
  `LierTelegram.jsx` (menu Compte) affiche un code à recopier, sous le titre « Relier Telegram »

Le périmètre réel de cette US se réduit donc à : **le geste unique** (deep-link + QR), **l'écran
d'activation dans le parcours d'onboarding**, **la relance persistante**, **l'accueil contextualisé
du bot** et **la protection de l'endpoint de génération de code**.

**Critères d'acceptance :**

*Écran d'activation*
- [ ] CA1 : Une étape d'activation dédiée, plein écran, est présentée **à l'issue du parcours d'onboarding du premier potager (US-058)** et non avant sa création : un compte sans potager ne peut rien dicter (US-046 / CA5), lui proposer d'activer le compagnon avant d'avoir un potager mènerait à un bot qui refuse tout
- [ ] CA2 : Le titre est « Activez votre compagnon de terrain » — **jamais** « Connecter Telegram ». Le sous-titre vend l'usage : notes vocales depuis le potager, rappels d'arrosage et alertes reçus sur le téléphone. Le mot « Telegram » n'apparaît qu'en réassurance basse (« Gratuit, via Telegram. Aucun mot de passe à créer. »)
- [ ] CA3 : Le bouton principal « Ouvrir mon compagnon » ouvre le deep-link `https://<bot>?start=<code>`, où `<code>` est un code de liaison US-045 fraîchement généré
- [ ] CA4 : Un **QR code est affiché en parallèle** du bouton, visible sans interaction supplémentaire (pas derrière un onglet ni un dépliant) — c'est le seul chemin praticable depuis un poste de bureau sans Telegram installé, où le clic sur le deep-link échoue silencieusement
- [ ] CA5 : Le code reste affiché en clair, en repli, avec le rappel de `/lier CODE` — non-régression du parcours US-045 pour qui a déjà le bot ouvert
- [ ] CA6 : Un bouton secondaire « Plus tard », visuellement discret, permet de rejoindre le tableau de bord : l'activation n'est **jamais** bloquante
- [ ] CA7 : Le compte à rebours de validité (10 minutes) et la régénération du code fonctionnent comme dans la modale existante ; un code expiré à l'écran n'envoie jamais l'utilisateur vers un deep-link mort

*Côté bot — accueil et liaison*
- [ ] CA8 : `/start <code>` lie le chat au compte, marque le code comme utilisé, et applique **exactement** les mêmes refus que `/lier` : code inconnu, code expiré, code déjà utilisé, chat déjà lié à un autre compte (US-045 / CA3, CA4, CA5). Aucun comportement de sécurité nouveau ni assoupli
- [ ] CA9 : Un chat déjà lié au compte A qui presse un deep-link généré depuis le compte B est **refusé** avec un message qui indique la marche à suivre — délier d'abord depuis la PWA (US-050). Le cas légitime du changement de téléphone reste faisable en deux gestes
- [ ] CA10 : Le message de bienvenue qui suit une liaison réussie est **contextualisé** : prénom de l'utilisateur, nom du potager actif, et une invitation à dicter. Le potager est résolu par le mécanisme existant d'US-046, sans logique de sélection nouvelle
- [ ] CA11 : Si l'utilisateur n'appartient à aucun potager au moment de la liaison, le bot le lie quand même et affiche le message d'absence de potager existant (US-046 / CA5) qui l'oriente vers la création — aucun blocage, aucune erreur
- [ ] CA12 : `/start` **sans** payload depuis un chat non lié conserve le message d'onboarding existant, enrichi du nouveau geste (« générez votre lien d'activation depuis l'application ») — c'est le cas de l'utilisateur qui trouve le bot par la recherche Telegram. Non-régression : `/start` reste hors garde de liaison, sans quoi l'onboarding devient impossible
- [ ] CA13 : Immédiatement après une liaison réussie, un envoi proactif via `telegram_notify.envoyer_message` aboutit — c'est la preuve que le rail de push est ouvert, et le test qui distingue ce mécanisme d'un simple Login Widget

*Relance et état dans la PWA*
- [ ] CA14 : Tant que le compte n'est pas lié, un bandeau persistant en tête du tableau de bord propose l'activation avec un CTA direct ; il disparaît dès la liaison effectuée (l'état est déjà exposé par `GET /auth/me`)
- [ ] CA15 : L'état « compagnon actif » et l'action de désactivation sont accessibles depuis le menu Compte ; les intitulés existants sont réécrits selon le reframing du CA2
- [ ] CA16 : Toute fonctionnalité vocale future non disponible sans compagnon se présente grisée avec le CTA d'activation, jamais masquée ni en erreur

*Sécurité et journalisation*
- [ ] CA17 : `POST /auth/lien/generer-code` est protégé par une limitation de débit (5 générations par heure et par compte). L'endpoint n'en a **aucune** aujourd'hui, alors que `/auth/login` et `/auth/register` en ont une (US-044 / CA8) — et le deep-link va en multiplier les appels
- [ ] CA18 : Chaque liaison réussie est journalisée (identifiant de compte, identifiant de chat, horodatage) pour l'auditabilité ; le code de liaison lui-même n'est **jamais** écrit dans les logs
- [ ] CA19 : Le Login Widget Telegram reste **hors périmètre** : le connecteur Telegram de l'écran de connexion demeure désactivé. Ouvrir un second chemin d'identité (« se reconnecter via Telegram ») créerait un compte concurrent sans e-mail, sans canal de récupération, pour un gain nul — l'utilisateur lié se reconnecte par e-mail ou par Google (US-090)
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran d'activation, du QR code et du bandeau de relance correspond visuellement à la maquette de référence à 375px / 768px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (onboarding US-058, tableau de bord, menu Compte) + interaction Telegram (`/start`) + API (protection de l'endpoint existant)
- Migration BDD requise : **non**. C'est la correction la plus importante par rapport au cadrage initial, qui prévoyait une table `telegram_link_tokens` et une colonne `potager_actif_id` : les deux existent déjà (US-045, US-046)
- **Arbitrage tranché — TTL du code :** on conserve les **10 minutes** d'US-045 plutôt que de passer à 15. Un même code sert désormais au deep-link, au QR et à la saisie manuelle ; disposer de trois chemins pour le consommer ne justifie pas d'allonger sa durée de vie
- **Arbitrage tranché — re-liaison depuis un autre compte Telegram :** refus explicite avec renvoi vers la déliaison (CA9), et non écrasement silencieux. C'est déjà le comportement livré par US-045 / CA5 : cette US n'a qu'à ne pas le contourner
- **Arbitrage tranché — emplacement du potager actif :** aucune décision à prendre, `users.potager_actif_id` est déjà la source de vérité unique, lue à chaque message par le bot comme par la PWA
- **Arbitrage tranché — nettoyage des codes expirés :** au fil de l'eau, à la lecture, comme aujourd'hui. Aucun job planifié à ajouter pour si peu (le seul job périodique du projet, la purge des potagers supprimés d'US-084, porte sur un tout autre volume d'enjeu)
- Dépendances : **US-045** (livrée — mécanisme de code réutilisé tel quel), **US-046** (livrée — potager actif), **US-050** (livrée — déliaison), **US-058** (livrée — onboarding, hôte de la nouvelle étape), **US-044** (livrée). **US-090** n'est pas bloquante mais logique : le parcours « je crée mon compte avec Google, puis j'active mon compagnon » doit s'enchaîner sans couture
- Interaction avec **US-087** (`/rejoindre` par code d'invitation) et **US-088** (visibilité des changements de potager actif dans le bot), toutes deux non livrées : aucune n'est un prérequis. US-088 raffinera l'accueil du bot une fois livrée ; le cadrage initial les tenait pour bloquantes en s'appuyant sur la numérotation `US-15x` du document de conception, qui ne correspond pas à celle des fichiers `backlog/` (US-151 y désigne la création d'un potager additionnel, soit US-081, déjà livrée)
- Zéro token Groq : le traitement de `/start <code>` est une lecture en base, sans transcription ni classification
- Nouvelle dépendance frontend : une bibliothèque de génération de QR code — aucune n'est présente aujourd'hui dans `frontend/package.json`. Le QR doit être **produit dans le navigateur**, sans appel à un service tiers : le code de liaison ne doit jamais transiter par un serveur externe
- Configuration : le nom du bot doit devenir une variable d'environnement exposée au frontend pour construire le deep-link. `PWA_URL` et `FRONTEND_URL` existent déjà dans `config.py`, mais pas l'identifiant du bot

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `bot.py` (`cmd_start` — lecture du payload `context.args`, et message d'accueil), `main.py` (limitation de débit sur `/auth/lien/generer-code`), `config.py` (nom du bot), `frontend/src/views/Onboarding.jsx` (nouvelle étape finale), `frontend/src/components/LierTelegram.jsx` (deep-link + QR + réécriture éditoriale), tableau de bord (bandeau), `frontend/src/components/AccountMenu.jsx` (intitulés)
- `app/services/liaison_telegram.py` n'a pas à changer : `lier_chat_id` et ses exceptions couvrent déjà tous les cas de refus du CA8
- Ordre critique des flux Telegram (invariant projet) : `/start` est déjà enregistré hors garde de liaison via `_enregistrer_commande` — ne pas l'y faire entrer, et ne pas dupliquer la logique de garde à l'intérieur du handler
- Échapper les caractères Markdown du prénom et du nom de potager dans le message d'accueil (non-régression US-007)
- Le message d'accueil doit être statique côté formulation (aucun appel LLM), seules les valeurs étant interpolées
- Un deep-link consommé deux fois (lien partagé, historique de conversation) doit produire le message de code déjà utilisé, pas une seconde liaison

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Activation en un geste depuis le mobile
  Given un jardinier qui vient de créer son compte et son premier potager "Jardin de Vitry"
  When il touche "Ouvrir mon compagnon" à l'étape d'activation
  Then Telegram s'ouvre sur le bot avec le code de liaison en payload
  And la pression sur START lie son chat à son compte
  And le bot l'accueille en nommant "Jardin de Vitry"
  And un message proactif envoyé juste après lui parvient sans erreur

Scénario: Activation depuis un poste de bureau
  Given un jardinier sur ordinateur, sans Telegram installé
  When il atteint l'étape d'activation
  Then un QR code est visible en même temps que le bouton
  And le scan depuis son téléphone aboutit à la même liaison

Scénario: Report de l'activation
  Given un jardinier à l'étape d'activation
  When il choisit "Plus tard"
  Then il accède normalement à son tableau de bord
  And un bandeau lui propose d'activer son compagnon tant qu'il ne l'a pas fait

Scénario: Lien d'activation expiré
  Given un lien d'activation généré il y a plus de 10 minutes
  When le jardinier l'ouvre dans Telegram
  Then le bot refuse la liaison et l'invite à générer un nouveau lien depuis l'application

Scénario: Lien d'activation déjà utilisé
  Given un lien d'activation déjà consommé
  When quelqu'un l'ouvre à nouveau
  Then le bot refuse la liaison avec un message explicite
  And aucune seconde liaison n'est créée

Scénario: Arrivée directe sur le bot sans passer par l'application
  Given un visiteur qui a trouvé le bot par la recherche Telegram
  When il presse START sans aucun code
  Then le bot lui explique comment créer son compte puis générer son lien d'activation
  And aucune donnée n'est enregistrée

Scénario: Chat déjà lié à un autre compte
  Given un chat Telegram déjà lié au compte A
  When ce chat ouvre un lien d'activation généré depuis le compte B
  Then la liaison est refusée
  And le message indique de délier d'abord depuis l'application

Scénario: Activation sans potager
  Given un compte lié à aucun potager
  When son propriétaire active son compagnon
  Then la liaison réussit
  And le bot lui indique qu'il n'a pas encore de potager et comment en créer ou en rejoindre un

Scénario: Génération de liens en rafale
  Given un compte ayant déjà généré cinq liens d'activation dans l'heure
  When il en demande un sixième
  Then la demande est refusée avec un message explicite
  And les liens déjà générés restent utilisables jusqu'à leur expiration
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `telegram`, `pwa`, `onboarding`, `security`
