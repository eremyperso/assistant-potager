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

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : PWA (nouveaux écrans inscription/connexion) + API (nouveaux endpoints `/auth/*` + garde sur les endpoints existants)
- Migration BDD requise : **oui** — ajout des colonnes de credentials sur la table `users` créée en US-040 (`mot_de_passe_hash`, éventuellement `email_verifie`), migration numérotée (vérifier le dernier numéro au moment de l'implémentation)
- Dépendances : US-040 (table `users`), US-041 (couche services — `TenantContext` doit pouvoir être construit depuis un `user_id` authentifié plutôt qu'en dur)
- Zéro impact tokens Groq
- Invariants projet : migration en fichier séparé idempotent avec rollback documenté ; secrets via variables d'environnement uniquement

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveau module `services/auth.py` (ou `app/auth/`), nouveaux endpoints dans `main.py`, migration SQL, dépendances `passlib`, `python-jose` (ou équivalent) à ajouter à `requirements.txt`
- Hors périmètre explicite de cette US : OAuth Google, réinitialisation de mot de passe par e-mail (sous-US ultérieure si l'envoi d'e-mail transactionnel n'est pas encore en place), vérification d'e-mail à l'inscription
- Le `TenantContext` (introduit en US-041) doit être construit à partir du `user_id` extrait du JWT — cette US ne construit pas encore le `potager_id` du contexte (potager actif géré en US-046) ; prévoir une valeur temporaire ou un état "sans potager actif" en sortie de login tant que US-046 n'est pas livrée
- Coordonner précisément le front (appel `/auth/*`, stockage du token, intercepteur de refresh) et le back dans la même US pour éviter une PWA qui casse en production

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Inscription réussie
  Given aucun compte n'existe pour l'e-mail "jardinier@example.com"
  When l'utilisateur s'inscrit avec cet e-mail et un mot de passe valide
  Then un compte est créé
  And le mot de passe n'est jamais stocké en clair

Scénario: Connexion réussie
  Given un compte existant avec e-mail et mot de passe
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

**Labels GitHub :** `us`, `sprint-identite-acces`, `api`, `security`, `multi-tenant`, `pwa`
