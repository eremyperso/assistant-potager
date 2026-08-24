**ID :** US-090
**Titre :** Créer son compte et se connecter via Google (OpenID Connect)
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que visiteur de la Progressive Web App
Je veux créer mon compte ou me connecter en un clic avec mon compte Google
Afin de ne pas avoir à inventer et retenir un mot de passe de plus, et d'entrer dans l'application sans attendre un e-mail de vérification

**Contexte fonctionnel :**
Cette US est la **première moitié de l'US-089**, scindée en deux (voir US-091 pour la seconde).
L'US-089 mélangeait deux préoccupations qui n'ont ni le même cycle de vie ni le même rôle
fonctionnel : *se connecter au web* d'un côté, *activer le compagnon Telegram* de l'autre.
Le déclencheur de la scission est un constat technique : le Telegram Login Widget **ne débloque
pas** l'envoi de messages proactifs par le bot — seul un geste `START` le fait. Telegram n'est
donc pas un fournisseur d'identité concurrent de Google, c'est un canal à activer. US-089 est
remplacée par US-090 + US-091 et doit être archivée avec une note de renvoi.

**Facebook est abandonné**, définitivement et pas seulement reporté : l'API Graph ne garantit
jamais l'attestation de vérification de l'e-mail, ce qui interdit tout rattachement automatique à
un compte existant (c'était le CA11 de l'US-089) et impose un parcours de repli dégradé pour un
gain d'acquisition très incertain sur la cible « jardiniers amateurs France ». Le connecteur
disparaît donc de l'écran de connexion, ce qui constitue un **écart assumé avec la maquette 2026**
(`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.7, trois connecteurs dessinés).

*État du socle, vérifié dans le code au moment de la rédaction — plusieurs prérequis supposés
manquants sont en réalité déjà là :*
- `users.mot_de_passe_hash` est **déjà nullable** (`database/models.py`, US-044) — aucune migration
  n'est nécessaire pour accueillir un compte sans mot de passe
- `users.email` est **déjà nullable et unique** (US-040)
- la vérification d'e-mail passe par l'API Brevo (`app/services/email.py`, US-044) — c'est bien ce
  parcours-là qui est court-circuité pour un compte Google
- l'écran `frontend/src/views/Auth.jsx` affiche déjà les trois connecteurs en état désactivé avec
  la mention « Bientôt disponible » (US-056 / CA5)

**Critères d'acceptance :**

*Écran et parcours*
- [ ] CA1 : Le bouton « Continuer avec Google » est **actif** sur les deux onglets de l'écran d'authentification (connexion et inscription) ; la mention « Bientôt disponible » disparaît pour ce connecteur
- [ ] CA2 : Le connecteur **Facebook est retiré** de l'écran (pas désactivé, retiré) ; le connecteur Telegram reste désactivé et relève d'US-091 — la mention « Bientôt disponible » ne subsiste que pour lui
- [ ] CA3 : Un échec ou un abandon côté Google (refus de consentement, fenêtre fermée, erreur réseau, accès révoqué depuis le compte Google) ramène l'utilisateur sur l'écran de connexion avec un message compréhensible, aucun compte créé, aucun état de session incohérent — jamais de page blanche ni d'erreur technique brute
- [ ] CA4 : Si les identifiants Google ne sont pas configurés dans l'environnement courant, le bouton n'est **pas affiché** (masqué, pas en erreur) — le développement local et les tests fonctionnent sans compte Google

*Sécurité du flux*
- [ ] CA5 : Le flux est un **Authorization Code avec PKCE** ; l'échange du code contre les jetons se fait **côté serveur**, le `client_secret` n'est jamais exposé au navigateur ; les flux implicites sont exclus
- [ ] CA6 : Un `state` aléatoire non devinable et un `nonce` sont émis à l'initiation et vérifiés au retour (anti-CSRF, anti-rejeu) ; `state` et `code_verifier` sont conservés côté serveur ou dans un cookie signé `HttpOnly` + `SameSite`, **jamais** dans le `localStorage`
- [ ] CA7 : L'`id_token` est validé côté serveur — signature via les clés publiques JWKS de Google, `iss`, `aud`, `exp`, `nonce` ; une simple lecture non vérifiée du JWT est un échec de ce CA
- [ ] CA8 : Les `redirect_uri` acceptées proviennent d'une liste blanche de configuration d'environnement ; toute autre valeur est rejetée
- [ ] CA9 : Les identifiants `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` sont lus depuis les variables d'environnement, jamais codés en dur ni versionnés
- [ ] CA10 : À l'issue d'une fédération réussie, l'application émet **ses propres jetons US-044** (access 15 min + refresh 30 jours) ; aucun jeton Google n'est persisté, aucun *offline access* n'est demandé, et les scopes se limitent à `openid email profile`

*Compte, création et rattachement*
- [ ] CA11 : Première connexion Google sans compte existant pour cet e-mail → un compte est créé avec le nom et l'e-mail renvoyés, `mot_de_passe_hash` à NULL, `email_verifie = true`, **aucun e-mail Brevo envoyé**, et l'utilisateur entre directement dans le parcours d'onboarding du premier potager (US-058)
- [ ] CA12 : Si un compte local existe déjà avec cet e-mail **et** que Google atteste `email_verified = true`, l'identité Google est rattachée automatiquement à ce compte : l'utilisateur retrouve ses potagers, aucun doublon n'est créé, aucun écran de confirmation intermédiaire n'est imposé
- [ ] CA13 : Si Google renvoie `email_verified = false` (cas rare, comptes Workspace mal configurés), le rattachement automatique est **refusé** ; s'il s'agit d'une création, le compte reste `email_verifie = false` et le parcours de vérification Brevo d'US-044 s'applique normalement
- [ ] CA14 : L'identifiant Google (`sub`) est stocké dans une colonne **unique** de `users` — un même compte Google ne peut être rattaché qu'à un seul utilisateur
- [ ] CA15 : Il n'existe **pas** de colonne mono-valuée du type `auth_provider` : après un rattachement (CA12), le compte possède *deux* méthodes de connexion simultanées. Les méthodes actives se déduisent des colonnes existantes (`mot_de_passe_hash`, l'identifiant Google, `telegram_chat_id`) ; le fournisseur utilisé est une propriété de *l'événement de connexion*, journalisée, pas une propriété de l'utilisateur
- [ ] CA16 : Un utilisateur possédant à la fois un compte e-mail et un compte Google **sur deux adresses différentes** ne peut pas les fusionner : la tentative aboutit à deux comptes distincts et un message d'aide explicite ; la fusion manuelle est hors périmètre v1
- [ ] CA17 : Un compte sans mot de passe qui passe par « Mot de passe oublié ? » (US-057) reçoit une réponse adaptée — l'orientant vers la connexion Google, ou lui permettant de **définir** un premier mot de passe — et jamais un message laissant croire que le compte n'existe pas
- [ ] CA18 : La déconnexion invalide les jetons applicatifs sans révoquer quoi que ce soit côté Google (comportement standard attendu)

*Journalisation et conformité*
- [ ] CA19 : Codes d'autorisation, `id_token`, `client_secret` et `code_verifier` ne sont **jamais** écrits dans les logs, même en niveau DEBUG ; chaque événement d'authentification (succès, échec, rattachement) est journalisé avec `user_id` et fournisseur uniquement
- [ ] CA20 : Le texte de consentement de l'écran d'inscription mentionne explicitement le recours à Google comme fournisseur d'identité et la nature des données récupérées (identifiant technique, e-mail, nom). La politique de confidentialité elle-même **n'existe pas encore** — les liens de `Auth.jsx` pointent sur `#` — la rédaction du paragraphe correspondant est donc produite par cette US et **rattachée à US-132 (RGPD & conformité)** pour intégration ; cette dépendance documentaire ne bloque pas la livraison
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran de connexion et d'inscription avec le connecteur Google actif et Facebook retiré correspond visuellement à la maquette de référence à 375px / 768px / desktop, l'écart « deux connecteurs au lieu de trois » étant assumé et documenté

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (écran d'authentification US-056) + API (nouveaux endpoints `/auth/oauth/google/*`)
- Migration BDD requise : **oui, minime** — une seule colonne à ajouter sur `users` : l'identifiant Google (`sub` OIDC), texte, nullable, **unique**. `mot_de_passe_hash` et `email` sont déjà nullables (US-040/US-044), contrairement à ce que supposait le cadrage initial. Dernière migration appliquée : `migration_v29.sql` → prévoir `migration_v30.sql` **et** `rollback_v30.sql` (convention du dépôt depuis v16)
- **Arbitrage tranché — stockage de l'identité fédérée :** colonne dédiée sur `users` plutôt que table `identites_federees` (option retenue par l'US-089 initiale). Un seul fournisseur est prévu à court terme, Telegram vit déjà dans sa propre colonne `telegram_chat_id`, et le passage ultérieur à une table dédiée reste non cassant. La complexité d'une jointure supplémentaire à chaque login n'est pas justifiée aujourd'hui
- **Arbitrage tranché — e-mail déjà existant :** fusion automatique et silencieuse (CA12), à la stricte condition que Google atteste la vérification de l'e-mail. C'est précisément l'attestation `email_verified` qui rend l'écran de confirmation superflu : exiger le mot de passe dans ce cas ajouterait de la friction sur un parcours qui doit être joyeux, sans gain de sécurité réel
- Dépendances : **US-044** (socle JWT, table `users`, vérification Brevo — cette US en est le prolongement direct), US-056 (écran de connexion, connecteurs déjà dessinés), US-057 (mot de passe oublié, cf. CA17), US-058 (onboarding premier potager, cf. CA11). **Aucune dépendance bloquante** : tout le socle est livré
- Zéro impact tokens Groq
- Prérequis externe à provisionner avant implémentation : projet Google Cloud, écran de consentement OAuth configuré, et URI de redirection déclarées **par environnement**
- **Corrections apportées au cadrage initial :** (a) l'URI de redirection de développement n'est pas `http://localhost:5173/...` — le frontend Vite de ce projet tourne sur le port **3000**, et surtout la redirection doit pointer sur l'**API** (`localhost:8000`) puisque l'échange du code se fait côté serveur (CA5) ; (b) le numéro de migration n'est pas `v5` mais `v30` ; (c) la vérification d'e-mail correspond à US-044 dans ce dépôt, la numérotation `US-1xx` étant celle du document `docs/BACKLOG_US_MULTITENANT.md`, pas celle des fichiers `backlog/`
- **Sur l'ordre de livraison :** livrer cette US **avant** US-091. Le compte doit exister pour qu'un lien d'activation Telegram puisse être émis

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveau module `app/services/oauth_google.py`, extension d'`app/services/auth.py` (émission des jetons applicatifs après fédération), nouveaux endpoints dans `main.py` (`GET /auth/oauth/google/start`, `GET /auth/oauth/google/callback`), `database/models.py`, `migrations/migration_v30.sql` + `rollback_v30.sql`, `frontend/src/views/Auth.jsx` (`OAuthRow`, `PROVIDERS`)
- Les clés publiques JWKS de Google sont à mettre en cache en respectant les en-têtes de cache, pas à retélécharger à chaque connexion
- Le mode dégradé du CA4 doit être exploitable en test : les tests automatisés s'appuient sur un connecteur simulé, sans aucun appel réseau sortant (`tests/conftest.py` fixe déjà `APP_ENV=test` et SQLite en mémoire)
- La création du compte et l'écriture de l'identifiant Google doivent être atomiques : un compte créé sans son `sub` serait inconnectable au coup suivant et bloquerait l'adresse e-mail
- Rotation des secrets : documenter la procédure dans `docs/SETUP.md` au même endroit que les autres secrets d'environnement

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Première connexion Google, aucun compte existant
  Given aucun compte n'existe pour "jardinier@gmail.com"
  When le visiteur clique sur "Continuer avec Google" et consent au partage de son profil
  Then un compte est créé avec email_verifie = true et sans mot de passe
  And aucun e-mail de vérification Brevo n'est envoyé
  And l'utilisateur entre dans le parcours d'onboarding du premier potager

Scénario: Rattachement automatique sur e-mail vérifié
  Given un compte local existe pour "jardinier@gmail.com" avec un mot de passe
  When ce jardinier se connecte via Google avec la même adresse attestée vérifiée
  Then l'identité Google est rattachée au compte existant
  And il retrouve ses potagers, sans compte doublon
  And il peut toujours se connecter avec son mot de passe

Scénario: E-mail Google non attesté vérifié
  Given un compte local existe pour "jardinier@exemple.fr"
  When un visiteur se connecte via Google avec cette adresse et email_verified = false
  Then aucun rattachement automatique n'a lieu
  And un message explique la démarche à suivre

Scénario: Accès révoqué depuis le compte Google
  Given un utilisateur ayant révoqué l'accès de l'application depuis son compte Google
  When il clique sur "Continuer avec Google"
  Then il revient sur l'écran de connexion avec un message clair
  And aucune erreur technique brute ne lui est présentée

Scénario: Mot de passe oublié sur un compte sans mot de passe
  Given un compte créé uniquement via Google
  When l'utilisateur demande une réinitialisation de mot de passe
  Then la réponse l'oriente vers la connexion Google ou vers la définition d'un premier mot de passe
  And ne laisse jamais penser que le compte n'existe pas

Scénario: Identifiants Google non configurés
  Given un environnement sans GOOGLE_CLIENT_ID
  When un visiteur ouvre l'écran de connexion
  Then le bouton "Continuer avec Google" n'est pas affiché
  And la connexion par e-mail et mot de passe fonctionne normalement

Scénario: Deux comptes sur deux adresses différentes
  Given un compte e-mail "jardinier@exemple.fr" et un compte Google "jardinier@gmail.com"
  When l'utilisateur cherche à réunir les deux
  Then un message explique que la fusion n'est pas disponible
  And les deux comptes restent distincts et fonctionnels
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `api`, `security`, `pwa`, `auth`, `oauth`
