US-004 : Gestion des environnements dev et production
Titre : Séparer la configuration dev/prod avec fichiers .env dédiés

Story :
En tant que développeur
Je veux disposer de deux environnements distincts (dev local et production Scaleway)
Afin d'itérer sans risque d'impacter les utilisateurs réels

Critères d'acceptance :
- [ ] CA1 : Un fichier `.env.dev` configure le bot @AssistantPotagerDevBot (TOKEN_DEV) et une BDD PostgreSQL locale
- [ ] CA2 : Un fichier `.env.prod` configure le bot @AssistantPotagerBot (TOKEN_PROD) et la BDD PostgreSQL Scaleway
- [ ] CA3 : `config.py` charge le bon fichier `.env` selon la variable d'environnement `APP_ENV` (valeurs : `dev` | `prod`)
- [ ] CA4 : Aucun token ni mot de passe n'est hardcodé dans `config.py` ou tout autre fichier Python
- [ ] CA5 : Les fichiers `.env.*` sont listés dans `.gitignore` — seul `.env.example` est versionné

Notes techniques :
- Composants impactés : config.py, .gitignore
- Migration BDD requise : non
- Dépendances : aucune
- Sécurité : corriger la vulnérabilité OWASP A02 — credentials actuellement hardcodés dans config.py

Estimation : 2 points

Scénario Gherkin :
```gherkin
Scenario: Lancement en environnement dev
  Given la variable d'environnement APP_ENV est "dev"
  When l'application démarre
  Then config.py charge .env.dev
  And le token utilisé est TOKEN_DEV
  And la BDD cible est PostgreSQL locale

Scenario: Lancement en environnement prod
  Given la variable d'environnement APP_ENV est "prod"
  When l'application démarre
  Then config.py charge .env.prod
  And le token utilisé est TOKEN_PROD
  And la BDD cible est PostgreSQL Scaleway
```

Labels GitHub : `us`, `sprint-2`, `config`, `securite`
