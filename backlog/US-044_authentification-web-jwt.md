**ID :** US-044
**Titre :** Authentifier les utilisateurs de la PWA par e-mail / mot de passe (JWT)
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur de la Progressive Web App
Je veux créer un compte et me connecter avec un e-mail et un mot de passe
Afin que mes données de potager ne soient accessibles qu'à moi et aux personnes que j'autorise

**Contexte fonctionnel :**
Aujourd'hui, la PWA appelle l'API FastAPI sans aucune authentification : tout appelant peut lire/écrire les données de n'importe quel potager. Cette US introduit l'identité web (distincte du bot Telegram, traité en US-045) : inscription, connexion, et un jeton JWT vérifié sur tous les endpoints métier. C'est le point d'entrée obligatoire de l'ÉPIC 2 — sans lui, aucune notion de rôle (US-047) ni de potager actif (US-046) n'a de support.

**Critères d'acceptance :**
- [ ] CA1 : Un utilisateur peut s'inscrire via `POST /auth/register` avec e-mail + mot de passe ; le mot de passe est haché (argon2 ou bcrypt via `passlib`), jamais stocké ni loggé en clair
- [ ] CA2 : Un utilisateur inscrit peut se connecter via `POST /auth/login` et reçoit un access token JWT (durée de vie 15 min) et un refresh token (durée de vie 30 jours)
- [ ] CA3 : `POST /auth/refresh` permet d'obtenir un nouvel access token à partir d'un refresh token valide, sans redemander le mot de passe
- [ ] CA4 : Une dépendance FastAPI `get_current_user` est appliquée à **tous** les endpoints métier existants (`/parse`, `/ask`, `/stats`, `/historique`, `/cultures`, etc.) — un appel sans token valide renvoie `401`
- [ ] CA5 : Un token expiré renvoie `401` de façon explicite (code d'erreur distinct d'un token absent, pour permettre au front de déclencher le refresh automatiquement)
- [ ] CA6 : Le secret de signature JWT (`JWT_SECRET`) est lu depuis une variable d'environnement (`.env.dev` / `.env.prod`), jamais codé en dur ni versionné
- [ ] CA7 : Une tentative de réutilisation d'un e-mail déjà inscrit sur `/auth/register` renvoie une erreur explicite (409), sans révéler si l'e-mail existe déjà de façon exploitable pour de l'énumération de comptes
- [ ] CA8 : Un rate-limit basique est actif sur `/auth/login` et `/auth/register` (ex. N tentatives/minute par IP) pour limiter le brute-force
- [ ] CA9 : À l'inscription, un e-mail de vérification est envoyé contenant un lien/token unique (aléatoire, non devinable, stocké **haché** en base) valable 24h ; le mot de passe et le token ne sont jamais loggés en clair
- [ ] CA10 : `POST /auth/verify-email` (ou `GET` avec token en query) valide le token, marque `email_verifie = true` et invalide le token (usage unique) ; un token déjà utilisé, invalide ou expiré renvoie une erreur explicite sans révéler d'information exploitable
- [ ] CA11 : Tant que `email_verifie = false`, `POST /auth/login` renvoie `403` avec un code d'erreur distinct (`EMAIL_NOT_VERIFIED`) plutôt qu'un token — le front peut ainsi proposer un renvoi d'e-mail plutôt qu'un message générique
- [ ] CA12 : `POST /auth/resend-verification` permet de renvoyer un nouvel e-mail de vérification (invalide l'ancien token), avec son propre rate-limit (anti-spam d'envoi d'e-mails) et une réponse identique que le compte existe ou non (anti-énumération, cohérent avec CA7)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (nouveaux écrans inscription/connexion/vérification d'e-mail) + API (nouveaux endpoints `/auth/*` + garde sur les endpoints existants)
- Migration BDD requise : **oui** — ajout des colonnes de credentials sur la table `users` créée en US-040 (`mot_de_passe_hash`, `email_verifie` boolean défaut `false`) + table (ou colonnes) pour les tokens de vérification (`token_hash`, `expire_le`, `utilise_le`), migration numérotée (vérifier le dernier numéro au moment de l'implémentation)
- Dépendances : US-040 (table `users`), US-041 (couche services — `TenantContext` doit pouvoir être construit depuis un `user_id` authentifié plutôt qu'en dur), **service d'envoi d'e-mail transactionnel : Brevo** (choisi — société française, hébergement UE natif cohérent RGPD, offre gratuite 300 mails/jour à vie, largement suffisante pour ce volume) — compte et clé API à créer, à provisionner via variables d'environnement (`.env.dev` / `.env.prod`). **Ne pas auto-héberger de SMTP sortant sur le VPS Hetzner** : le port 25 y est bloqué par défaut (déblocage sur ticket, au cas par cas, seulement après ~1 mois d'ancienneté), et les plages d'IP Hetzner sont fréquemment blacklistées par les grands webmails (Gmail/Outlook), ce qui ferait échouer la délivrabilité des e-mails de vérification. Brevo est appelé exclusivement via son API HTTPS (aucun SMTP sortant depuis le VPS)
- Zéro impact tokens Groq
- Invariants projet : migration en fichier séparé idempotent avec rollback documenté ; secrets via variables d'environnement uniquement ; le token de vérification n'est **jamais** stocké en clair (même logique que le mot de passe : hash en base, valeur brute uniquement dans l'e-mail envoyé)

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveau module `services/auth.py` (ou `app/auth/`), nouveau module `services/email.py` (envoi transactionnel via API Brevo + templating du mail de vérification), nouveaux endpoints dans `main.py` (`/auth/verify-email`, `/auth/resend-verification`), migration SQL, dépendances `passlib`, `python-jose` (ou équivalent) à ajouter à `requirements.txt`, plus `httpx` pour appeler l'API HTTPS Brevo (endpoint `https://api.brevo.com/v3/smtp/email`, auth par header `api-key`) — pas de SDK dédié nécessaire, pas de SMTP sortant auto-hébergé (cf. note dépendances)
- Variables d'environnement à ajouter : `BREVO_API_KEY`, `EMAIL_FROM` (ex. `noreply@assistant-potager.fr` — nécessite validation du domaine expéditeur côté Brevo), `EMAIL_FROM_NOM`, `FRONTEND_URL` (pour construire le lien de vérification envoyé dans le mail)
- Génération du token de vérification : valeur aléatoire cryptographiquement sûre (`secrets.token_urlsafe`), jamais l'ID utilisateur ou une valeur devinable ; seul le hash est stocké, comparaison en temps constant
- Hors périmètre explicite de cette US : OAuth Google, réinitialisation de mot de passe par e-mail (sous-US ultérieure — réutilisera l'infra d'envoi d'e-mail mise en place ici)
- Le `TenantContext` (introduit en US-041) doit être construit à partir du `user_id` extrait du JWT — cette US ne construit pas encore le `potager_id` du contexte (potager actif géré en US-046) ; prévoir une valeur temporaire ou un état "sans potager actif" en sortie de login tant que US-046 n'est pas livrée
- Coordonner précisément le front (appel `/auth/*`, stockage du token, intercepteur de refresh, écran "vérifiez votre e-mail" + bouton renvoi) et le back dans la même US pour éviter une PWA qui casse en production
- Prévoir un mode dégradé en environnement dev/test si `BREVO_API_KEY` n'est pas configurée (ex. log du lien de vérification dans la console au lieu d'un envoi réel via Brevo), pour ne pas bloquer les tests automatisés ni le développement local

**Estimation :** 11 points

**Scénario Gherkin :**
```gherkin
Scénario: Inscription réussie
  Given aucun compte n'existe pour l'e-mail "jardinier@example.com"
  When l'utilisateur s'inscrit avec cet e-mail et un mot de passe valide
  Then un compte est créé avec email_verifie = false
  And le mot de passe n'est jamais stocké en clair
  And un e-mail contenant un lien de vérification unique est envoyé à "jardinier@example.com"

Scénario: Connexion refusée tant que l'e-mail n'est pas vérifié
  Given un compte existant avec email_verifie = false
  When l'utilisateur se connecte avec les identifiants corrects
  Then la réponse est 403 avec le code "EMAIL_NOT_VERIFIED"
  And aucun token n'est délivré

Scénario: Vérification d'e-mail réussie
  Given un compte avec email_verifie = false et un token de vérification valide et non expiré
  When l'utilisateur ouvre le lien de vérification reçu par e-mail
  Then le compte passe à email_verifie = true
  And le token ne peut plus être réutilisé

Scénario: Token de vérification expiré
  Given un compte avec email_verifie = false et un token de vérification expiré (> 24h)
  When l'utilisateur ouvre le lien de vérification
  Then la réponse indique explicitement que le lien a expiré
  And l'utilisateur peut demander un renvoi via /auth/resend-verification

Scénario: Connexion réussie
  Given un compte existant avec e-mail et mot de passe, et email_verifie = true
  When l'utilisateur se connecte avec les identifiants corrects
  Then il reçoit un access token et un refresh token

Scénario: Accès refusé sans token
  Given aucun token n'est fourni
  When un appel est fait à un endpoint métier protégé (ex. /historique)
  Then la réponse est 401

Scénario: Token expiré puis rafraîchi
  Given un access token expiré et un refresh token valide
  When l'utilisateur appelle un endpoint protégé avec le token expiré
  Then la réponse est 401
  When l'utilisateur appelle /auth/refresh avec le refresh token
  Then il reçoit un nouvel access token valide

Scénario: Double inscription refusée
  Given un compte existe déjà pour "jardinier@example.com"
  When une nouvelle inscription est tentée avec le même e-mail
  Then la réponse est 409 sans détail exploitable pour énumérer les comptes
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `api`, `security`, `multi-tenant`, `pwa`, `email`
