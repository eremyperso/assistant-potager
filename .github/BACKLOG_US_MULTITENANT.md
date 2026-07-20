# 🌿 Assistant Potager — Backlog US Multi-tenant & Sécurisation

> **Document de référence pour Claude Code et l'agent de rédaction d'US.**
> Objectif : solution 100 % multi-utilisateurs, sécurisée, prête à commercialisation.
> Source : `REFLEXION_STRATEGIQUE_multi_utilisateurs.md` (§4 bloquants, §5 architecture cible, §7 trajectoire).
> Convention : chaque US ci-dessous est à décliner au format `US-XXX` habituel (critères d'acceptance + Gherkin) par l'agent US, puis implémentée par l'agent d'implémentation.
> Règle d'or transverse : **aucune US ne casse l'installation actuelle**. Les données existantes deviennent le potager #1.

---

## 0. Vue d'ensemble — ordre et dépendances

```
ÉPIC 1 — SOCLE TENANT          ÉPIC 2 — IDENTITÉ & ACCÈS      ÉPIC 3 — FIABILITÉ & COÛT      ÉPIC 4 — COMMERCIALISATION
US-100 Modèle multi-tenant ──► US-110 Auth web (JWT)      ──► US-120 État Redis          ──► US-130 Postgres managé
US-101 Couche services     ──► US-111 Liaison Telegram    ──► US-121 LLM à étages        ──► US-131 Observabilité
US-102 Scoping requêtes    ──► US-112 Potager actif       ──► US-122 RAG scopé /ask      ──► US-132 RGPD
US-103 RLS PostgreSQL      ──► US-113 Rôles & permissions ──► US-123 Quotas par tenant   ──► US-133 Stripe / freemium
                               US-114 Invitations         ──► US-124 Jobs par potager
                                                              US-125 Alembic + CI/CD
```

**Chemin critique :** `US-100 → US-101 → US-102 → US-103 → US-110 → US-111 → US-113`.
Tout le reste peut être parallélisé une fois son épic amont livré.

**Chantier parallèle (hors périmètre de ce backlog, à ne pas oublier) :** la base de connaissance *fiches cultures* (`US_Base_fiches_cultures`), qui conditionne la valeur produit de l'offre payante. À mener en parallèle des épics 1–2, car sans elle on commercialise « un carnet multi-utilisateurs », facilement copiable.

---

## ÉPIC 1 — Socle multi-tenant (Phase 0–1 de la trajectoire)

### US-100 — Modèle multi-tenant (users / potagers / membres)

- **Contexte :** aucune notion de tenant aujourd'hui ; tables globales. Bloquant #1.
- **Objectif :** créer le socle de données du tenant **potager** (pas l'utilisateur — 500 users / 100 potagers ≈ 5 personnes/jardin, les jardins sont partagés).
- **Périmètre :**
  - Tables `users (id, email, telegram_chat_id UNIQUE NULL, cree_le)`, `potagers (id, nom, latitude, longitude, proprietaire_id FK users, cree_le)`, `potager_membres (user_id, potager_id, role CHECK IN ('owner','editor','lecteur'), PRIMARY KEY (user_id, potager_id))`.
  - Ajout `potager_id INTEGER NULL REFERENCES potagers(id)` sur **toutes** les tables métier : `evenements`, `parcelles`, `culture_config`, et toute table dérivée.
  - Backfill : création du user #1 (Emmanuel, chat_id actuel), du potager #1 (localisation actuelle), rattachement owner, `UPDATE ... SET potager_id = 1` sur toutes les lignes existantes.
  - Index : `CREATE INDEX ... ON evenements (potager_id, date DESC)` (et équivalent sur les autres tables).
- **Hors périmètre :** aucun changement de comportement du bot ; les colonnes restent nullables à ce stade.
- **Migration :** `migration_v5.sql` complet, rejouable (idempotent : `IF NOT EXISTS`), exécutable via `psql`.
- **Critères d'acceptance clés :** bot et PWA fonctionnent à l'identique après migration ; `SELECT count(*) FROM evenements WHERE potager_id IS NULL` = 0 après backfill ; rollback documenté.
- **Impact tokens :** nul. **Risques :** oubli d'une table dérivée → inventorier via `information_schema` dans l'US.

### US-101 — Couche `services/` partagée bot ⇄ PWA

- **Contexte :** logique métier éclatée entre `bot.py` (~1300 lignes) et `main.py`. Si l'isolation est codée deux fois, elle sera fausse une fois.
- **Objectif :** extraire la logique métier dans `app/services/` ; chaque fonction de service prend **obligatoirement** un contexte `TenantContext(user_id, potager_id, role)`. Bot et FastAPI deviennent des clients minces.
- **Périmètre :** modules suggérés : `services/evenements.py` (CRUD + corrections), `services/stats.py`, `services/stock.py`, `services/plan.py`, `services/questions.py` (`_ask_question`). Signature type : `def enregistrer_evenement(ctx: TenantContext, data: EvenementIn) -> Evenement`.
- **Hors périmètre :** pas encore de vérification des rôles (US-113) ; `ctx` peut être construit avec le potager #1 en dur pendant la transition.
- **Critères d'acceptance clés :** aucun `db.query(Evenement)` ne subsiste dans `bot.py` / `main.py` ; comportement identique (tests de non-régression sur les 12 actions canoniques + flux `corr_*` + mode `ask`) ; logging structuré `HH:MM:SS │ LEVEL │ emoji` conservé.
- **Risques / effets de bord :** refactor massif → découper en sous-US par module ; attention aux états `ctx.user_data` (Telegram) qui ne migrent PAS dans services (ils restent côté client bot jusqu'à US-120). SQLAlchemy 2.0 : `db.get()`, jamais `db.query().get()`.

### US-102 — Scoping systématique par `potager_id` (dont refonte `_ask_question`)

- **Contexte :** `_ask_question()` charge tout l'historique sans filtre (~5 000 tokens) : fuite inter-potagers + explosion de coût + débordement de contexte. Limiter à 100 événements ne suffit pas : il faut **scoper avant de limiter**.
- **Objectif :** toute requête de la couche services filtre par `ctx.potager_id`. Zéro requête non scopée dans le code applicatif.
- **Périmètre :**
  - Filtre `potager_id` dans tous les services (lecture, écriture, correction, suppression, stats, stock, plan, rotation).
  - `_ask_question` : scope potager + fenêtre temporelle (défaut 12 mois) + limite (100 événements max) ; sérialisation compacte.
  - `potager_id` devient `NOT NULL` sur toutes les tables métier (`migration_v6.sql`).
- **Critères d'acceptance clés (Gherkin type) :** *Étant donné* deux potagers A et B avec des événements, *quand* un membre de A demande stats/historique/question, *alors* aucune donnée de B n'apparaît. Test automatisé d'isolation obligatoire.
- **Impact tokens :** `_ask_question` passe de ~5 000 à < 1 500 tokens/appel (à mesurer et logger).
- **Risques :** requêtes brutes SQL éventuelles (stats) à auditer une par une.

### US-103 — Row-Level Security PostgreSQL (défense en profondeur)

- **Contexte :** même avec le scoping applicatif, un bug suffit pour fuir. Ceinture + bretelles.
- **Objectif :** policies RLS garantissant qu'aucune requête ne sort du potager courant, même en cas de bug applicatif.
- **Périmètre :**
  - Rôle applicatif Postgres non-superuser (RLS ne s'applique pas au owner de table → créer `app_user`).
  - `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + policy `USING (potager_id = current_setting('app.potager_id')::int)` sur chaque table métier.
  - Dans `db.py` : à l'ouverture de session, `SET LOCAL app.potager_id = :pid` (event SQLAlchemy `after_begin` ou context manager de session tenant-aware).
- **Migration :** `migration_v7.sql` (policies) + modification `database/db.py`.
- **Critères d'acceptance clés :** une requête volontairement non scopée (test dédié) retourne 0 ligne d'un autre potager ; les migrations/backups (rôle admin) restent possibles.
- **Risques :** oubli du `SET` → requêtes qui retournent 0 ligne partout (échec silencieux) : prévoir un fail-fast si `app.potager_id` absent ; jobs de fond (US-124) devront itérer en posant le setting par potager.

---

## ÉPIC 2 — Identité & accès (Phase 2–3)

### US-110 — Authentification web (inscription + login JWT)

- **Objectif :** identité e-mail/mot de passe pour la PWA ; tous les endpoints FastAPI protégés.
- **Périmètre :** hash mot de passe (argon2 ou bcrypt via `passlib`) ; JWT access (15 min) + refresh (30 j) ; endpoints `/auth/register`, `/auth/login`, `/auth/refresh` ; dépendance FastAPI `get_current_user` appliquée à **tous** les endpoints métier ; construction du `TenantContext` depuis le JWT. Rate-limit basique sur `/auth/*`.
- **Hors périmètre :** OAuth Google (évolution ultérieure), reset mot de passe par e-mail (peut être une sous-US si l'envoi d'e-mail n'est pas encore disponible).
- **Critères d'acceptance clés :** endpoint sans token → 401 ; token expiré → 401 + refresh fonctionne ; mot de passe jamais loggé ni stocké en clair ; secrets (JWT_SECRET) via variables d'environnement, pas dans `config.py` versionné.
- **Risques :** la PWA actuelle appelle l'API sans auth → coordonner front/back dans la même US.

### US-111 — Liaison Telegram ⇄ compte web par code à usage unique

- **Objectif :** rattacher un `chat_id` Telegram à un compte web. Un compte = un web + un Telegram liés.
- **Périmètre :** génération d'un code court (6–8 caractères, TTL 10 min, usage unique) côté web ; commande `/lier <code>` (et détection du code en message texte) côté bot ; écriture `users.telegram_chat_id` ; le bot **refuse tout message d'un `chat_id` non lié** (message d'onboarding avec lien vers l'inscription).
- **Critères d'acceptance clés :** code expiré/déjà utilisé → refus explicite ; un `chat_id` ne peut être lié qu'à un seul compte ; un chat inconnu ne peut déclencher **aucun** appel Groq (économie + sécurité).
- **Effets de bord :** `handle_voice`/`handle_text` doivent vérifier la liaison **avant** toute transcription Whisper — placer le garde en tout premier dans le flux (avant les priorités 1–5).

### US-112 — Sélection du potager actif

- **Objectif :** un utilisateur peut appartenir à plusieurs potagers → notion de potager actif, stocké par utilisateur, côté web et Telegram.
- **Périmètre :** colonne `users.potager_actif_id` (ou table de préférences) ; commande `/potager` avec boutons inline listant les potagers du membre ; sélecteur équivalent dans la PWA ; le `TenantContext` est construit depuis le potager actif ; si un seul potager → sélection automatique silencieuse.
- **Critères d'acceptance clés :** après changement de potager actif, toutes les saisies/questions portent sur le nouveau potager ; utilisateur sans potager → invité à en créer un (lien avec US-114).
- **Migration :** incluse dans `migration_v8.sql` avec US-111 si livrées ensemble.

### US-113 — Rôles & permissions (owner / editor / lecteur)

- **Objectif :** contrôle d'accès par rôle, écrit **une seule fois** dans la couche services.
- **Périmètre :** matrice : `lecteur` = consultation (stats, historique, questions) ; `editor` = + saisie/correction/suppression d'événements ; `owner` = + gestion des membres, paramètres du potager, suppression du potager. Décorateur ou garde `require_role(ctx, 'editor')` dans chaque service d'écriture. Messages d'erreur clairs côté bot et PWA (« Tu es lecteur sur ce potager »).
- **Critères d'acceptance clés (Gherkin type) :** *Étant donné* un lecteur, *quand* il dicte « j'ai récolté 2 kg de tomates », *alors* rien n'est enregistré et un message d'explication est renvoyé (et l'appel de parsing LLM n'a **pas lieu** — vérifier le rôle avant `parse_actions`).
- **Impact tokens :** positif (blocage avant appel LLM pour les lecteurs).

### US-114 — Invitations & onboarding self-service

- **Objectif :** plus aucune opération manuelle pour créer un utilisateur ou un potager.
- **Périmètre :** création de potager depuis la PWA (nom + localisation — la géolocalisation alimente la météo par potager, US-124) ; invitation de membre par e-mail ou lien/code d'invitation avec rôle proposé ; acceptation → insertion dans `potager_membres` ; parcours complet documenté : inscription → création/adhésion potager → liaison Telegram → première saisie.
- **Critères d'acceptance clés :** un nouvel utilisateur atteint sa première saisie vocale sans aucune intervention de l'administrateur ; l'owner peut retirer un membre ; un membre retiré perd l'accès immédiatement (invalidation du potager actif).

---

## ÉPIC 3 — Fiabilité & maîtrise du coût (Phase 4) — *condition de survie économique*

### US-120 — État conversationnel persistant (Redis)

- **Contexte :** flux `corr_*` et mode `ask` en RAM (`ctx.user_data`) → perdus au redémarrage, non partageables, non scalables.
- **Objectif :** état des conversations dans Redis, clé `state:{user_id}`, TTL (ex. 15 min), sérialisation JSON.
- **Périmètre :** wrapper `ConversationState` (get/set/clear) remplaçant les accès `ctx.user_data` pour les modes ; docker-compose ajoute Redis ; fallback dégradé si Redis indisponible (mode sans état + log ERROR).
- **Critères d'acceptance clés :** redémarrage du bot en plein flux `corr_select` → le flux reprend ; TTL expiré → retour au menu proprement.
- **Risques / effets de bord :** c'est LE refactor sensible sur les états — tester les 5 priorités de `handle_text` et le bypass vocal ; conserver l'ordre critique (modes corr > ask > NAV > question > action).

### US-121 — LLM à étages + parsing déterministe + cache

- **Contexte :** goulot n°1 du projet = tokens Groq, pas l'infra.
- **Objectif :** réduire drastiquement le coût par message.
- **Périmètre :**
  1. `classify_intent()` → `llama-3.1-8b-instant` (~×9 d'économie), 70B réservé au parsing structuré.
  2. Parseur déterministe (regex/grammaire) **avant** tout appel LLM pour les formes fréquentes (« récolté 2 kg de tomates », « semé 3 rangs de carottes parcelle nord ») → zéro token sur ces cas ; le LLM devient le fallback.
  3. Cache de classification (Redis, clé = hash du texte normalisé, TTL 24 h) pour les phrases courtes identiques.
  4. Log du nombre de tokens consommés par appel (colonne ou log structuré) pour mesurer.
- **Critères d'acceptance clés :** jeu de tests de non-régression sur un corpus de phrases réelles (extraites de `texte_original`) : le parseur déterministe couvre ≥ 50 % des saisies sans dégrader la précision ; taux d'erreur d'intent mesuré avant/après bascule 8B.
- **Impact tokens :** cible 🔶 : coût moyen/message divisé par 5 à 10. **Risques :** le 8B classe moins bien → garder un fallback 70B si confiance faible ; ne pas oublier `.replace()` (jamais `.format()`) dans les prompts.

### US-122 — RAG scopé et pré-agrégé pour les questions (`/ask`)

- **Contexte :** complément de US-102 : après le scoping, optimiser la *qualité/coût* des réponses.
- **Objectif :** ne jamais envoyer de lignes brutes massives au LLM ; pré-agréger en SQL, nourrir le LLM avec des résumés.
- **Périmètre :** classification légère de la question (culture ? période ? type de question ?) ; requêtes SQL d'agrégation ciblées (totaux par culture/mois, dernières occurrences) ; contexte final < 1 000 tokens ; fenêtre temporelle adaptative selon la question.
- **Critères d'acceptance clés :** corpus de questions réelles → réponses correctes avec contexte < 1 000 tokens ; aucune donnée hors `potager_id`.
- **Impact tokens :** ~5 000 → < 1 500 par question (mesuré).

### US-123 — Quotas tokens & rate-limiting par tenant

- **Contexte :** quota Groq global partagé = non viable ; le prix de l'offre doit couvrir le coût réel/user/mois.
- **Objectif :** comptabiliser et plafonner la consommation par potager.
- **Périmètre :** table `conso_tokens (potager_id, date, appel_type, modele, tokens_in, tokens_out)` alimentée par un wrapper unique autour du client Groq ; budget quotidien/mensuel par potager (colonne `potagers.plan` : free/payant) ; dépassement → message clair + blocage des appels LLM (les fonctions déterministes restent disponibles) ; rate-limit par user (ex. N messages/minute) ; endpoint/commande de consultation de conso.
- **Critères d'acceptance clés :** potager au quota → saisies simples via parseur déterministe encore possibles, questions LLM bloquées avec message d'upgrade ; tableau de conso par potager consultable (base du pricing).
- **Dépendances :** US-121 (wrapper Groq unique).

### US-124 — Jobs de fond par potager (météo, sauvegardes, alertes)

- **Contexte :** météo mono-localisation, job global 5h, aucune sauvegarde automatique.
- **Objectif :** ordonnanceur qui itère sur les potagers.
- **Périmètre :** APScheduler (Celery/RQ seulement si ça grossit) ; job météo par `(lat, lon)` distinct avec cache `(lat, lon, jour)` et batching Open-Meteo ; alertes gel/canicule envoyées aux membres du potager concerné via Telegram ; job de sauvegarde quotidien (`pg_dump` + rétention 30 j) tant que US-130 n'est pas livrée ; chaque job pose `app.potager_id` (compatibilité RLS, cf. US-103).
- **Critères d'acceptance clés :** 2 potagers à localisations différentes reçoivent des météos différentes ; échec d'un job pour un potager n'interrompt pas les autres (isolation d'erreurs + log).

### US-125 — Migrations Alembic + CI/CD

- **Contexte :** migrations jouées à la main → intenable en prod multi-tenant vivante.
- **Objectif :** migrations versionnées et déploiement reproductible.
- **Périmètre :** init Alembic + reprise de l'état actuel comme révision de base (les `migration_vX.sql` historiques restent en archive) ; docker-compose (FastAPI + bot + Redis) ; GitHub Actions : tests → build → déploiement Scaleway → `alembic upgrade head` → restart services ; secrets en variables d'environnement/GitHub Secrets.
- **Critères d'acceptance clés :** un `git push` sur `main` déploie sans intervention manuelle et sans coupure perceptible ; rollback de migration documenté et testé.

---

## ÉPIC 4 — Commercialisation (Phase 5)

### US-130 — PostgreSQL managé + sauvegardes automatiques

- **Périmètre :** migration vers Postgres managé Scaleway (sauvegardes auto, PITR) ; bascule `DATABASE_URL` ; répétition générale de la migration sur une copie ; fenêtre de coupure planifiée et courte.
- **Critères d'acceptance clés :** restauration testée réellement (pas seulement des backups qui existent) ; latence applicative inchangée.

### US-131 — Observabilité

- **Périmètre :** Sentry (bot + API) ; logs centralisés ; métriques : messages/jour, erreurs, latence Groq, **tokens par tenant** (réutilise US-123) ; alerte si taux d'erreur anormal ou quota Groq global proche de la limite.
- **Critères d'acceptance clés :** une exception non gérée en prod apparaît dans Sentry avec contexte (user_id, potager_id — sans données personnelles sensibles).

### US-132 — RGPD & conformité

- **Contexte :** pré-requis légal de commercialisation dès qu'il y a des données de tiers.
- **Périmètre :** export des données du compte (JSON/CSV) ; suppression de compte (et anonymisation des événements d'un potager partagé : l'événement reste, l'auteur est anonymisé) ; consentement à l'inscription ; CGU + politique de confidentialité + mentions légales ; registre des traitements (document) ; TTL sur les fichiers audio temporaires (les vocaux ne sont pas conservés après transcription).
- **Critères d'acceptance clés :** suppression de compte → plus aucune donnée personnelle en base (vérification par requête) ; export complet en < 1 min.
- **Risques :** cas du dernier owner d'un potager qui supprime son compte → règle à définir dans l'US (transfert ou suppression du potager).

### US-133 — Facturation Stripe (freemium)

- **Périmètre :** plans free (quota tokens limité, 1 potager) / payant (quotas supérieurs, potagers multiples, fonctions premium — ex. prévision de récolte, diagnostic photo) ; Stripe Checkout + webhooks (paiement, échec, résiliation) ; `potagers.plan` piloté par l'abonnement ; page de gestion d'abonnement.
- **Critères d'acceptance clés :** cycle complet testé en mode test Stripe : souscription → upgrade quota effectif → résiliation → retour au plan free en fin de période.
- **Dépendances :** US-123 (quotas), US-132 (CGU obligatoires avant encaissement). **Pré-requis business :** mesurer 1 mois de conso réelle (US-123) pour fixer un prix couvrant le coût Groq/user/mois.

---

## Annexes pour l'agent US

### Ordre de livraison recommandé (sprints indicatifs)

| Sprint | US | Livrable vérifiable |
|--------|----|---------------------|
| 1 | US-100 | Schéma tenant + backfill, app inchangée |
| 2–3 | US-101 | Couche services, non-régression complète |
| 4 | US-102 | Isolation applicative + `_ask_question` scopé |
| 5 | US-103 | RLS actif, test de fuite automatisé |
| 6 | US-110, US-111 | Login web + liaison Telegram, bot fermé aux inconnus |
| 7 | US-112, US-113 | Potager actif + rôles |
| 8 | US-114 | Onboarding self-service de bout en bout |
| 9 | US-121 | LLM à étages + parseur déterministe (peut démarrer dès sprint 2 en parallèle) |
| 10 | US-120, US-122 | Redis + RAG scopé |
| 11 | US-123, US-124 | Quotas tenant + jobs par potager |
| 12 | US-125 | Alembic + CI/CD |
| 13+ | US-130 → US-133 | Prod managée, observabilité, RGPD, Stripe |

### Invariants à rappeler dans chaque US (règles de travail)

1. Migration SQL toujours en fichier `migration_vX.sql` séparé (puis Alembic à partir de US-125), idempotente, avec rollback documenté.
2. SQLAlchemy 2.0 : `db.get()`, jamais `db.query().get()`.
3. Prompts Groq : `.replace()` sur les variables, jamais `.format()`.
4. Logging structuré `HH:MM:SS │ LEVEL │ emoji MESSAGE` conservé partout.
5. Tout nouvel appel Groq : impact tokens chiffré et loggé.
6. Ordre critique des flux de conversation (modes `corr_*` > mode `ask` > NAV > `_is_question` > action) préservé ; tout refactor liste les effets de bord sur `ctx.user_data` / `ConversationState`.
7. Échappement MarkdownV2 (underscores des parcelles, issue #21) dans toute nouvelle sortie bot.
8. Compatible SentinelOne : polling Telegram côté dev local, pas de tunnel entrant.

### Définition of Done commune

- Tests de non-régression sur les 12 actions canoniques + flux correction + mode ask.
- Test d'isolation inter-potagers (à partir de US-102) exécuté dans la CI.
- `PATCH_NOTES.md` mis à jour.
- Documentation de la migration et du rollback.
