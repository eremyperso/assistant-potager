> ⚠️ **US ARCHIVÉE — REMPLACÉE, NE PAS IMPLÉMENTER TELLE QUELLE**
>
> Cette US mélangeait deux préoccupations aux cycles de vie distincts : *se connecter
> au web* et *activer le compagnon Telegram*. Elle est remplacée par :
>
> - **US-090** — [Créer son compte et se connecter via Google (OIDC)](US-090_connexion-google-oidc.md) — **livrée**
> - **US-091** — [Activer le compagnon Telegram](US-091_activer-compagnon-terrain-telegram.md)
>
> Facebook est **abandonné** (l'API Graph ne garantit jamais l'attestation de
> vérification de l'e-mail, ce qui interdit le rattachement automatique). Le document
> ci-dessous est conservé pour la trace d'analyse des trois protocoles, rien d'autre.

**ID :** US-089
**Titre :** Se connecter via un fournisseur d'identité tiers (Google, Facebook, Telegram)
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant que visiteur de la Progressive Web App
Je veux me connecter ou créer mon compte en un clic via Google, Facebook ou Telegram
Afin de ne pas avoir à gérer un mot de passe supplémentaire, et de déléguer la sécurité de mon authentification à un fournisseur spécialisé

**Contexte fonctionnel :**
L'US-044 a livré l'identité web « locale » : e-mail + mot de passe haché, vérification d'e-mail, JWT access/refresh. L'US-056 a livré l'écran de connexion refondu affichant les trois connecteurs **Google / Facebook / Telegram en état désactivé** avec la mention « Bientôt disponible » (CA5 de l'US-056). Cette US-089 lève cette réserve et branche réellement le mécanisme.

Le mécanisme retenu est la **fédération d'identité** : l'application ne voit jamais le mot de passe de l'utilisateur ; elle délègue la preuve d'identité à un fournisseur tiers, qui lui renvoie une identité vérifiée. Le point d'attention à porter dès la rédaction : **les trois fournisseurs demandés ne parlent pas le même protocole.**

| Fournisseur | Protocole réel | Ce qu'il renvoie |
|---|---|---|
| Google | **OpenID Connect** (OIDC, sur-couche d'OAuth 2.0) | `id_token` JWT signé, avec `sub` stable, `email`, `email_verified`, `name` |
| Facebook | **OAuth 2.0** (+ appel Graph API pour le profil) — pas d'OIDC standard côté web | jeton d'accès, puis `id` + `email` (non garanti : l'utilisateur peut le refuser, ou son compte peut être rattaché à un numéro de téléphone) |
| Telegram | **Ni OAuth 2.0 ni OIDC** — mécanisme propriétaire « Telegram Login Widget » : le widget renvoie un payload signé en HMAC-SHA256 avec le token du bot | `id` (= `chat_id` en conversation privée), `first_name`, `username`, `photo_url`, `auth_date`, `hash` — **jamais d'e-mail** |

L'US doit donc introduire une **abstraction interne « fournisseur d'identité »** qui accueille aussi bien un client OIDC standard qu'un connecteur propriétaire, plutôt que de s'appuyer sur une bibliothèque OIDC générique qui ne saurait pas traiter Telegram.

Deux conséquences fonctionnelles structurantes :
1. **Telegram ne fournit pas d'e-mail** — donc pas de rattachement automatique à un compte existant, et pas de canal de récupération de compte. Cette US doit articuler explicitement « Continuer avec Telegram » avec l'US-045 (liaison d'un chat Telegram à un compte web par code à usage unique), sous peine de créer deux chemins concurrents produisant deux comptes distincts pour le même jardinier.
2. Un compte peut désormais exister **sans mot de passe**. L'US-044 (login), l'US-057 (mot de passe oublié) et les écrans de paramètres du compte doivent traiter ce cas sans message d'erreur trompeur.

**Critères d'acceptance :**

*Socle — modèle et flux commun*
- [ ] CA1 : Une table `identites_federees` associe un `user_id` à un couple (`fournisseur`, `sujet_externe`), avec contrainte d'unicité sur (`fournisseur`, `sujet_externe`) ; un même utilisateur peut cumuler plusieurs fournisseurs, un même compte tiers ne peut être rattaché qu'à un seul utilisateur
- [ ] CA2 : Le flux OAuth/OIDC est de type **Authorization Code avec PKCE**, l'échange du code contre les jetons se faisant **côté serveur** (le `client_secret` n'est jamais exposé au navigateur) ; les flux implicites sont explicitement exclus
- [ ] CA3 : À l'issue d'une fédération réussie, l'application émet **ses propres jetons US-044** (access token 15 min + refresh token 30 jours) ; les jetons du fournisseur tiers ne sont ni persistés ni réutilisés pour appeler l'API métier
- [ ] CA4 : Un paramètre `state` aléatoire non devinable est généré à l'initiation du flux et vérifié au retour (anti-CSRF) ; pour Google, un `nonce` est également émis et vérifié dans l'`id_token`
- [ ] CA5 : L'`id_token` Google est validé côté serveur (signature via les clés publiques JWKS du fournisseur, `iss`, `aud`, `exp`) — une simple lecture non vérifiée du JWT est un échec du CA
- [ ] CA6 : Les `redirect_uri` acceptées sont limitées à une liste blanche issue de la configuration d'environnement ; toute autre valeur est rejetée
- [ ] CA7 : Les identifiants de chaque fournisseur (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, `FACEBOOK_APP_ID`/`FACEBOOK_APP_SECRET`, le token du bot Telegram déjà existant) sont lus depuis les variables d'environnement, jamais codés en dur ni versionnés
- [ ] CA8 : Un fournisseur dont les identifiants ne sont pas configurés dans l'environnement courant n'est **pas** proposé à l'écran (le connecteur est masqué, pas affiché en erreur) — permet de livrer les trois fournisseurs progressivement et de travailler en local sans compte Facebook

*Création de compte et rattachement (account linking)*
- [ ] CA9 : Première connexion via un fournisseur, aucun compte existant pour cet e-mail → un compte est créé avec le nom et l'e-mail fournis, `mot_de_passe_hash` à NULL, et l'utilisateur entre directement dans le parcours applicatif (onboarding premier potager, US-058)
- [ ] CA10 : Si le fournisseur atteste que l'e-mail est **vérifié** (`email_verified: true` chez Google) et qu'un compte local existe déjà avec ce même e-mail, l'identité fédérée est rattachée à ce compte existant — l'utilisateur retrouve son potager, aucun compte doublon n'est créé
- [ ] CA11 : Si le fournisseur ne garantit **pas** la vérification de l'e-mail (cas Facebook), le rattachement automatique à un compte local existant est **refusé** ; l'utilisateur est invité à se connecter d'abord par son mot de passe puis à rattacher le fournisseur depuis les paramètres de son compte (protection contre la prise de contrôle de compte par pré-inscription)
- [ ] CA12 : Un compte créé via un fournisseur qui atteste un e-mail vérifié est marqué `email_verifie = true` sans envoyer d'e-mail de vérification (l'étape US-044 CA9/CA11 est court-circuitée à bon droit) ; si l'e-mail n'est pas attesté vérifié, le compte reste `email_verifie = false` et le parcours de vérification US-044 s'applique
- [ ] CA13 : Si le fournisseur ne renvoie aucune adresse e-mail (cas Telegram, ou refus de la permission `email` chez Facebook), le compte est créé sans e-mail et l'application propose — sans bloquer l'usage — de renseigner une adresse depuis les paramètres du compte, en expliquant qu'elle sert à la récupération de compte

*Cas Telegram — articulation avec l'US-045*
- [ ] CA14 : Le payload renvoyé par le Telegram Login Widget est validé côté serveur : recalcul du `hash` HMAC-SHA256 à partir du token du bot et comparaison en temps constant, plus rejet d'un `auth_date` de plus de 24 h (rejeu)
- [ ] CA15 : Si l'`id` Telegram reçu correspond déjà à un `users.telegram_chat_id` lié via l'US-045, « Continuer avec Telegram » **connecte ce compte existant** — aucun compte doublon n'est créé
- [ ] CA16 : Si l'`id` Telegram n'est rattaché à aucun compte, un compte est créé et `users.telegram_chat_id` est renseigné dans le même mouvement — le bot Telegram est donc immédiatement utilisable pour cet utilisateur, sans passer par la commande `/lier`. L'US-045 reste le chemin de rattachement pour un compte web créé autrement (e-mail, Google, Facebook)
- [ ] CA17 : Une tentative de connexion Telegram dont l'`id` est déjà lié à un **autre** compte est refusée avec un message explicite, cohérent avec l'US-045 CA5

*Gestion des méthodes de connexion depuis le compte*
- [ ] CA18 : L'écran de compte (US-055) liste les méthodes de connexion actives (mot de passe, Google, Facebook, Telegram) et permet d'en ajouter une en la rattachant au compte connecté
- [ ] CA19 : Une méthode de connexion peut être dissociée, **sauf s'il s'agit de la dernière** : la dissociation est alors refusée avec un message expliquant qu'il faut d'abord définir un mot de passe ou rattacher un autre fournisseur (interdiction de se verrouiller hors de son propre compte). La dissociation de Telegram reste cohérente avec l'US-050
- [ ] CA20 : Un compte sans mot de passe qui utilise « Mot de passe oublié ? » (US-057) reçoit une réponse adaptée l'orientant vers son fournisseur, ou lui permettant de **définir** un mot de passe pour la première fois — jamais un message laissant croire à un compte inexistant

*Interface et journalisation*
- [ ] CA21 : Sur l'écran de connexion (US-056), les connecteurs disponibles passent d'un état désactivé « Bientôt disponible » à un état actif ; la mention est retirée et le clic déclenche le flux du fournisseur
- [ ] CA22 : Un échec ou un abandon côté fournisseur (refus de consentement, fenêtre fermée, erreur réseau) ramène l'utilisateur sur l'écran de connexion avec un message compréhensible et sans état incohérent — jamais une page blanche ou une erreur technique brute
- [ ] CA23 : Les jetons, codes d'autorisation, `client_secret` et payloads signés ne sont **jamais** écrits dans les logs, même en niveau DEBUG ; les événements d'authentification fédérée (succès, échec, rattachement, dissociation) sont journalisés avec le `user_id` et le fournisseur uniquement
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'écran de connexion avec connecteurs actifs, et de l'écran de gestion des méthodes de connexion, correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (écran de connexion US-056, écran compte US-055) + API (nouveaux endpoints `/auth/oauth/*`) + bot Telegram (aucun changement de comportement, mais un compte peut désormais naître avec `telegram_chat_id` déjà renseigné)
- Migration BDD requise : **oui** — nouvelle table `identites_federees` (`id`, `user_id` FK, `fournisseur`, `sujet_externe`, `email_fournisseur`, `cree_le`, `derniere_connexion_le`, unicité sur `fournisseur` + `sujet_externe`) **et** passage de `users.mot_de_passe_hash` en NULLABLE, plus `users.email` NULLABLE si le cas Telegram sans e-mail est retenu (CA13) — vérifier le dernier numéro de migration au moment de l'implémentation, fichier idempotent avec rollback documenté
- Dépendances : **US-044** (socle JWT, table `users`, e-mail de vérification — cette US en est le prolongement direct), **US-045** (liaison Telegram, à ne pas dupliquer : cf. CA15/CA16), **US-056** (écran de connexion et connecteurs déjà dessinés en état désactivé), US-055 (menu compte, hôte de la gestion des méthodes de connexion), US-057 (mot de passe oublié, cf. CA20), US-050 (dissociation Telegram, cf. CA19), US-058 (onboarding premier potager, cf. CA9)
- Zéro impact tokens Groq
- Prérequis externes à provisionner avant implémentation : projet Google Cloud + écran de consentement OAuth et URI de redirection déclarées ; application Facebook créée et passée en mode « Live » avec Facebook Login configuré ; côté Telegram, association du domaine au bot via `/setdomain` auprès de `@BotFather` (le Login Widget ne fonctionne que sur un domaine déclaré, en HTTPS)
- Invariants projet : secrets via variables d'environnement uniquement ; aucune donnée d'authentification en clair dans les logs ; l'application ne stocke aucun jeton d'accès tiers puisqu'elle n'appelle aucune API du fournisseur au-delà de la récupération du profil initial (minimisation RGPD : seuls `sujet_externe`, e-mail et nom sont conservés)
- **Découpage possible si l'US est jugée trop lourde pour un seul lot :** (a) socle fédération + Google, (b) Facebook, (c) Telegram + articulation US-045, (d) gestion des méthodes de connexion depuis le compte. Le socle (a) porte à lui seul les CA1 à CA12 et conditionne les autres

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveau module `services/federation_identite.py` (abstraction « fournisseur » + un connecteur par fournisseur), extension de `services/auth.py` (émission des jetons applicatifs après fédération), nouveaux endpoints dans `main.py` (`GET /auth/oauth/{fournisseur}/start`, `GET /auth/oauth/{fournisseur}/callback`, `POST /auth/telegram/callback`, `GET|POST|DELETE /auth/methodes`), migration SQL, front `frontend/src/views/Auth.jsx` et écran compte
- Le connecteur Telegram n'est **pas** un client OAuth : ne pas tenter de le faire entrer dans une bibliothèque OIDC générique. L'abstraction commune doit se situer au niveau « produire une identité vérifiée (fournisseur, sujet, e-mail éventuel, e-mail vérifié oui/non, nom) », pas au niveau du protocole
- Les clés publiques JWKS de Google sont à mettre en cache avec respect des en-têtes de cache, pas à retélécharger à chaque connexion
- Le `state` et le `code_verifier` PKCE doivent être stockés côté serveur (ou dans un cookie signé `HttpOnly` + `SameSite`), pas dans le `localStorage`
- Prévoir un mode dégradé en dev/test cohérent avec le CA8 : sans identifiants configurés, les connecteurs disparaissent de l'écran et les tests automatisés s'appuient sur des connecteurs simulés, sans appel réseau sortant
- Attention à l'ordre d'écriture en base dans le cas Telegram (CA16) : création du `user` et écriture de `telegram_chat_id` doivent être atomiques, sinon un compte orphelin non liable peut subsister

**Estimation :** 13 points

**Scénario Gherkin :**
```gherkin
Scénario: Première connexion Google, aucun compte existant
  Given aucun compte n'existe pour "jardinier@gmail.com"
  When le visiteur clique sur "Continuer avec Google" et consent au partage de son profil
  Then un compte est créé avec email_verifie = true et sans mot de passe
  And aucun e-mail de vérification n'est envoyé
  And l'utilisateur entre dans le parcours d'onboarding du premier potager

Scénario: Rattachement automatique sur e-mail vérifié
  Given un compte local existe pour "jardinier@gmail.com" avec un mot de passe
  When ce jardinier se connecte via Google avec la même adresse attestée vérifiée
  Then l'identité Google est rattachée au compte existant
  And il retrouve ses potagers, sans compte doublon

Scénario: Rattachement automatique refusé sur e-mail non attesté
  Given un compte local existe pour "jardinier@example.com"
  When un visiteur se connecte via Facebook avec cette même adresse non attestée vérifiée
  Then aucun rattachement automatique n'a lieu
  And il lui est demandé de se connecter par mot de passe puis de rattacher Facebook depuis son compte

Scénario: Connexion Telegram d'un chat déjà lié
  Given un compte web dont le telegram_chat_id a été lié via /lier (US-045)
  When ce jardinier clique sur "Continuer avec Telegram" depuis l'écran de connexion
  Then il est connecté sur ce compte existant
  And aucun compte doublon n'est créé

Scénario: Première connexion Telegram, compte inexistant
  Given un id Telegram rattaché à aucun compte
  When le visiteur se connecte via le widget Telegram
  Then un compte est créé sans adresse e-mail, avec telegram_chat_id renseigné
  And le bot Telegram est immédiatement utilisable sans passer par /lier
  And l'application propose de renseigner une adresse e-mail de récupération, sans bloquer l'usage

Scénario: Payload Telegram falsifié
  Given un appel au callback Telegram dont le hash ne correspond pas au calcul HMAC-SHA256
  When le serveur valide le payload
  Then l'authentification est refusée
  And aucun compte n'est créé ni connecté

Scénario: Dissociation de la dernière méthode de connexion
  Given un compte dont Google est la seule méthode de connexion
  When l'utilisateur tente de dissocier Google depuis son compte
  Then l'opération est refusée avec un message l'invitant à définir d'abord un mot de passe

Scénario: Mot de passe oublié sur un compte sans mot de passe
  Given un compte créé uniquement via Google
  When l'utilisateur demande une réinitialisation de mot de passe
  Then la réponse l'oriente vers la connexion Google ou vers la définition d'un premier mot de passe
  And ne laisse jamais penser que le compte n'existe pas

Scénario: Abandon du consentement chez le fournisseur
  Given un visiteur ayant lancé la connexion Facebook
  When il refuse le consentement ou ferme la fenêtre
  Then il revient sur l'écran de connexion avec un message compréhensible
  And aucun compte n'est créé
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `api`, `security`, `pwa`, `auth`, `oauth`, `telegram`
