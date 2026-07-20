**ID :** US-045
**Titre :** Lier un chat Telegram à un compte web par code à usage unique
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur ayant créé un compte sur la PWA
Je veux rattacher mon compte Telegram à ce compte web via un code à usage unique
Afin que mes messages vocaux et texte envoyés au bot soient rattachés à mon identité et à mes potagers, et non traités anonymement

**Contexte fonctionnel :**
Depuis US-044, la PWA a une identité (e-mail/mot de passe). Le bot Telegram, lui, n'identifie encore ses interlocuteurs que par `chat_id` sans lien avec un compte. Cette US crée le pont : un code court généré côté web est saisi côté Telegram pour lier `telegram_chat_id` à un `user_id`. Une fois cette US livrée, le bot doit refuser tout message provenant d'un `chat_id` non lié — condition nécessaire avant d'activer les rôles (US-047), sans quoi un chat non identifié pourrait continuer à écrire des données sans propriétaire clair.

**⚠️ Révision post-QA (constat terrain) :** une première implémentation n'avait posé le garde de liaison que sur `handle_voice`/`handle_text` (messages vocaux et texte libre). Or les commandes slash existantes (`/plan`, `/stats`, `/historique`, `/parcelle lister`, etc.) restaient accessibles sans aucune liaison — un chat jamais lié pouvait consulter toutes les parcelles/données via `/parcelle lister` sans jamais passer par le garde. CA6 et CA7 ci-dessous ont été reformulés pour fermer explicitement ce trou : **tout** point d'entrée Telegram métier est concerné, pas seulement le vocal/texte libre.

**Critères d'acceptance :**
- [x] CA1 : La PWA (utilisateur connecté) peut générer un code court (6 à 8 caractères, alphanumérique non ambigu), affiché à l'écran avec un TTL de 10 minutes
- [x] CA2 : Dans Telegram, la commande `/lier <code>` (et la détection du code seul envoyé en message texte) valide le code et écrit `users.telegram_chat_id` pour le compte correspondant
- [x] CA3 : Un code expiré (> 10 min) est refusé avec un message explicite invitant à en régénérer un depuis la PWA
- [x] CA4 : Un code déjà utilisé est refusé avec un message explicite (usage unique strict)
- [x] CA5 : Un `chat_id` ne peut être lié qu'à un seul compte à la fois ; une tentative de liaison d'un `chat_id` déjà lié à un autre compte est refusée avec message explicite (proposer une procédure de déliaison, hors périmètre technique de cette US si elle nécessite une action de support)
- [x] CA6 *(révisé)* : Toute interaction reçue d'un `chat_id` non lié à un compte — message vocal, message texte libre, **ou commande slash métier** (`/plan`, `/stats`, `/historique`, `/ask`, `/parcelle`, `/parcelles`, `/vendre`, `/corriger`, `/note`, `/meteo`, `/tts`, `/tts_on`, `/tts_off`, `/version`, et toute future commande métier) — déclenche un message d'onboarding (lien vers l'inscription web + explication de la commande `/lier`) et **n'entraîne aucun appel Groq ni aucune lecture/écriture de données métier** (parcelles, événements, stats). Seules `/start`, `/help` et `/lier` restent accessibles sans liaison (nécessaires à l'onboarding lui-même)
- [x] CA7 *(révisé)* : Le garde de vérification de liaison est positionné en tout premier, avant toute autre logique, sur **chacun** des points d'entrée listés en CA6 (priorité 0, avant les priorités 1 à 5 existantes de `handle_voice`/`handle_text`, et avant le corps de chaque handler de commande slash métier). L'implémentation doit garantir qu'aucune commande métier existante ni future ne puisse être ajoutée sans passer par ce garde (ex. wrapper/décorateur centralisé plutôt que copier-coller la vérification dans chaque fonction, pour éviter tout oubli)
- [x] CA8 : Une fois lié, le bot répond normalement à toutes les interactions du `chat_id` (vocal, texte, commandes), avec le `user_id` correspondant disponible pour construire le `TenantContext`
- [x] CA9 *(nouveau)* : Non-régression — `/start`, `/help` et `/lier` restent utilisables sans liaison depuis un chat non lié (sinon l'onboarding devient impossible)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (nouvelle commande `/lier`, garde global) + PWA (écran de génération de code)
- Migration BDD requise : **oui** — table ou colonnes pour les codes de liaison (`liaisons_telegram` : code, user_id, cree_le, expire_le, utilise_le), numéro de migration à vérifier au moment de l'implémentation
- Dépendances : US-040 (colonne `users.telegram_chat_id` déjà prévue au socle tenant), US-044 (identité web nécessaire pour générer un code depuis un compte authentifié)
- Impact tokens : **positif** — élimine les appels Groq déclenchés par des chats non identifiés (CA6)
- Invariants projet : logging structuré conservé ; ordre critique des flux Telegram (cf. invariant #6 du backlog) impacté — le garde de liaison doit s'insérer AVANT les modes `corr_*` / `ask` / NAV existants, à documenter précisément dans l'implémentation
- **Retour d'expérience QA à intégrer impérativement :** lister explicitement, dans l'implémentation, TOUS les `CommandHandler` enregistrés dans `bot.py::main()` au moment du développement, et confirmer un par un lesquels sont couverts par le garde (tous, sauf `/start`, `/help`, `/lier`) — un test automatisé doit vérifier cette couverture de façon exhaustive plutôt que cas par cas, pour qu'un futur ajout de commande ne puisse pas silencieusement échapper au garde

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `bot.py` (nouvelle commande `/lier`, garde en tête de `handle_voice`/`handle_text` ET de chaque commande slash métier, ou mécanisme centralisé équivalent — ex. wrapper appliqué à l'enregistrement des `CommandHandler` dans `main()`), nouveau service `services/liaison_telegram.py`, endpoint PWA `POST /auth/lien/generer-code`, migration SQL
- Le message d'onboarding envoyé à un chat non lié doit être statique (pas d'appel LLM) pour respecter CA6
- Prévoir l'échappement MarkdownV2 (invariant #7 du backlog) si le message d'onboarding contient des caractères spéciaux (ex. underscore dans une URL)
- Documenter explicitement dans l'US d'implémentation la liste complète des points d'entrée Telegram concernés par le garde (voix, texte libre, et **toutes** les commandes slash métier existantes — cf. CA6) pour éviter un oubli partiel ; recommandé : un test qui introspecte les handlers enregistrés plutôt qu'une liste statique risquant de devenir obsolète
- **Précision d'architecture — ne pas confondre deux identifiants distincts :** le bot Telegram (`@AssistantPotagerBot`, son token) est **unique et global** — tous les utilisateurs parlent au même backend `bot.py`. Le `chat_id`, lui, est **unique par utilisateur Telegram** (attribué par Telegram, pas par nous) et sert d'identifiant **stable et permanent** une fois lié — ce n'est pas un jeton de session ni un tunnel réseau. Après liaison, aucune ré-authentification n'est requise à chaque message : seul le `SELECT` `chat_id → user_id` est refait à chaque requête. La seule notion qui varie d'un message à l'autre est le **potager actif** (`users.potager_actif_id`, US-046), pas l'identité elle-même

**Estimation :** 8 points *(révisé de 5 à 8 — extension du garde à l'ensemble des commandes slash métier, plus la garantie de non-oubli pour les commandes futures)*

**Scénario Gherkin :**
```gherkin
Scénario: Liaison réussie
  Given un utilisateur connecté sur la PWA génère un code
  When il envoie "/lier <code>" au bot dans les 10 minutes
  Then son chat_id est lié à son compte
  And les messages suivants de ce chat sont traités normalement

Scénario: Code expiré
  Given un code généré il y a plus de 10 minutes
  When l'utilisateur envoie "/lier <code>" au bot
  Then la liaison est refusée avec un message explicite

Scénario: Code déjà utilisé
  Given un code déjà consommé par une liaison précédente
  When un autre utilisateur envoie "/lier <code>"
  Then la liaison est refusée avec un message explicite

Scénario: Chat_id déjà lié à un autre compte
  Given un chat_id déjà lié au compte A
  When une liaison est tentée vers le compte B avec ce même chat_id
  Then la liaison est refusée avec un message explicite

Scénario: Message d'un chat non lié
  Given un chat_id qui n'a jamais été lié à un compte
  When ce chat envoie un message vocal ou texte au bot
  Then aucun appel Groq n'est déclenché
  And le bot répond avec un message d'onboarding vers l'inscription web

Scénario: Commande slash métier depuis un chat non lié (révisé)
  Given un chat_id qui n'a jamais été lié à un compte
  When ce chat envoie "/parcelle lister" (ou toute autre commande métier : /plan, /stats, /historique...)
  Then aucune donnée de parcelle ou d'événement n'est renvoyée
  And le bot répond avec le même message d'onboarding que pour un message vocal/texte

Scénario: Commandes d'onboarding accessibles sans liaison (non-régression)
  Given un chat_id qui n'a jamais été lié à un compte
  When ce chat envoie "/start", "/help" ou "/lier"
  Then le bot répond normalement à ces trois commandes
```

**Labels GitHub :** `us`, `sprint-identite-acces`, `telegram`, `security`, `multi-tenant`
