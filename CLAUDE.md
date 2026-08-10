# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Langue

Toujours répondre en français, quelle que soit la langue utilisée dans les messages.

## Règles d'exécution des agents (NON NÉGOCIABLES)

Ces règles s'appliquent à chaque invocation d'un agent défini dans `.github/agents/`.

1. **Lire le fichier agent avant toute action** : avant d'exécuter le rôle d'un sous-agent,
   lire intégralement son fichier `.github/agents/*.agent.md`. Ne jamais improviser de mémoire.

2. **Patch Notes Writer — checklist obligatoire** : lors de l'exécution de l'étape Documentation,
   les deux fichiers suivants DOIVENT être modifiés sans exception :
   - `PATCH_NOTES.md` — nouvelle entrée insérée EN HAUT
   - `VERSION` — numéro incrémenté selon SemVer (PATCH / MINOR / MAJOR)
   Toute exécution du Patch Notes Writer sans mise à jour de `VERSION` est une erreur.

3. **Confirmation d'étape** : après chaque étape de l'Orchestrateur, indiquer explicitement
   "Étape X terminée" avec les fichiers modifiés. Ne pas enchaîner silencieusement.

## Project Overview

**Assistant Potager** is an intelligent gardening tracker for amateur gardeners. It combines:
- A **Telegram Bot** (bot.py) for voice/text command input
- A **FastAPI REST API** (main.py) serving a Progressive Web App
- **PostgreSQL** for event storage
- **Groq LLM** (Llama 3.3-70b + Whisper) for natural language parsing and analytics

The core flow: user dictates a gardening event → Groq extracts structured JSON → normalized and stored as an `Evenement` linked to a `Parcelle`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (uses SQLite in-memory, no PostgreSQL needed)
pytest tests/
pytest tests/test_us006_renommer_parcelle.py   # single test file
pytest tests/ -k "test_name"                   # single test by name

# Apply latest database migration
psql -d potager -f migrations/migration_v12.sql
```

### Lancer le bot Telegram et l'API en local (PowerShell, Windows)

Le shell par défaut est PowerShell, pas bash — `VAR=val cmd` ne fonctionne pas, et
`uvicorn`/`python` doivent venir du venv du projet (`.venv/`), pas du PATH global.

```powershell
cd "C:\Users\eremy\OneDrive - SQLI\Documents\GitHub\assistant-potager"
.\.venv\Scripts\Activate.ps1          # active le venv pour la session courante
$env:APP_ENV = "dev"                  # reste actif pour tout le terminal, une seule fois

# Bot Telegram — pas de --reload possible, il faut arrêter (Ctrl+C) et relancer
# manuellement à chaque modification de bot.py / groq_client.py / config.py
python bot.py

# API FastAPI (http://localhost:8000) — sert aussi le frontend buildé (frontend/dist)
# --reload recharge automatiquement à chaque modification de fichier Python
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# NB: main.py n'a pas de bloc __main__ — `python main.py` ne lance rien, il faut passer par uvicorn.

# Si Activate.ps1 est bloqué par la politique d'exécution PowerShell, contourner via :
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Mettre à jour le frontend si l'interface change

Le dashboard React (`frontend/`, Vite) peut tourner de deux façons :

```powershell
# Mode dev — hot reload instantané, pointe sur l'API via frontend/.env.local (VITE_API_URL)
cd frontend
npm install        # une seule fois / après changement de dépendances
npm run dev        # http://localhost:3000

# Mode "comme en prod" — l'API FastAPI sert le build statique
cd frontend
npm run build       # génère frontend/dist
# puis (re)démarrer l'API pour qu'elle serve le nouveau build :
cd ..
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

`main.py` sert `frontend/dist` en priorité (fallback sur `static/` si le build React est absent) —
toute modification de l'UI nécessite un `npm run build` avant de se refléter via l'API,
le mode `npm run dev` (port 3000) suffit pour itérer rapidement sans rebuild.

### Redéployer l'environnement dev local (pull + deps + migrations)

```powershell
.\update_dev.ps1
.\update_dev.ps1 -SkipPull   # depuis un hook git
.\update_dev.ps1 -Force      # tout rejouer
```

## Environment Setup

Copy `.env.example` to `.env.dev` and fill in:
- `APP_ENV` — `dev` or `prod`
- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `DATABASE_URL` — PostgreSQL connection string

Config is loaded from `.env.{APP_ENV}` via `config.py`.

## Architecture

### Entry Points

**bot.py** — Telegram bot. Handles voice notes (transcribed via Whisper) and text commands. Runs a daily 5am job to fetch weather via Open-Meteo.

#### Telegram Bot — Commandes slash

| Commande | Paramètres | Description |
|----------|------------|-------------|
| `/start` | — | Menu principal + compteur d'événements |
| `/help` | `[parcelle\|semis\|godet\|recolte\|stock\|stats]` | Aide générale ou ciblée par mot-clé |
| `/version` | — | Affiche la version de l'app (`bot.py:458`) |
| `/stats` | — | Statistiques saison (végétatif vs reproducteur) |
| `/stats <culture>` | `<culture>` | Détail par variété pour une culture donnée |
| `/stats <culture> <date>` | `[culture] [JJ/MM/AAAA\|AAAA-MM-JJ]` | Stats à une date de référence (`bot.py:3191`) |
| `/historique` | — | 10 derniers événements |
| `/ask` | `[question en langage naturel]` | Question analytique (ou saisie interactive si sans arg) |
| `/corriger` | — | Lancer le flux de correction d'un événement existant |
| `/plan` | — | Plan d'occupation global du potager |
| `/plan <parcelle>` | `<nom_parcelle>` | Plan filtré sur une parcelle spécifique |
| `/plan <date>` | `[JJ/MM/AAAA\|AAAA-MM-JJ]` | État du potager à une date de référence (`bot.py:2677`) |
| `/parcelle ajouter <nom> [exposition] [superficie]` | `<nom> [exposition] [superficie_m2]` | Créer une parcelle (détection de doublons) |
| `/parcelle modifier <nom> clé=valeur …` | `<nom> exposition=X superficie=X ordre=X` | Modifier les métadonnées |
| `/parcelle renommer <ancien> <nouveau>` | `<ancien_nom> <nouveau_nom>` | Renommer (propagation sur tout l'historique) |
| `/parcelle lister` | — | Lister toutes les parcelles actives |
| `/parcelles` | — | Alias de `/parcelle lister` (`bot.py:4665`) |
| `/vendre <culture> [variété] <quantité>` | `<culture> [variété] <quantité>` | Enregistrer une vente de plants pépinière (`bot.py:4585`) |
| `/meteo` | — | Déclencher la météo manuellement (job auto à 05h00) |
| `/tts` | — | Afficher l'état de la synthèse vocale |
| `/tts_on` | — | Activer les réponses vocales |
| `/tts_off` | — | Désactiver les réponses vocales |

#### Clavier inline (boutons persistants)

Menu principal : `🎤 Nouvelle action vocale` · `🔍 Interroger` · `📋 Historique` · `📊 Stats` · `✏️ Corriger`

Après enregistrement : `➕ Autre action` · `🔍 Interroger mes données` · `📋 Historique` · `🏠 Menu principal`

#### Callbacks inline (patterns, `bot.py:4670`)

| Pattern | Déclencheur |
|---------|-------------|
| `godet_*` | Sélection de variété lors d'une mise en godet |
| `recolte_*` | Sélection de variété lors d'une récolte |
| `vendu_*` | Sélection de variété lors d'une vente |
| `perte_*` | Confirmation de perte |
| `action_*` | Confirmation d'une action enregistrée |
| `parcelle_suppr_*` | Confirmation de suppression de parcelle |

#### Intents vocaux reconnus (classification Groq)

`ACTION` · `INTERROGER` · `STATS` · `HISTORIQUE` · `PLAN` · `CORRIGER` · `SUPPRIMER` · `MENU` · `NOUVELLE`

#### Messages non-slash (handlers, `bot.py:4686`)

| Type | Pipeline |
|------|----------|
| **Message vocal** | Transcription Whisper → classification intent → action correspondante |
| **Message texte libre** | Même pipeline que vocal (classification intent → action) |

#### Flux de correction conversationnel (`/corriger`)

1. Décrire l'événement à retrouver (ou taper `1` pour le dernier)
2. Sélectionner parmi les candidats trouvés
3. Dicter la correction en langage naturel
4. Confirmer le résumé des modifications

**main.py** — FastAPI server. Key endpoints: `POST /parse`, `POST /ask`, `GET /stats`, `GET /historique`, `GET /cultures`. Serves PWA static files.

### Core Modules

| Module | Role |
|--------|------|
| `database/models.py` | SQLAlchemy models: `Evenement`, `Parcelle`, `CultureConfig` |
| `llm/groq_client.py` | `parse_commande()`, `repondre_question()`, `extract_intent()` |
| `utils/stock.py` | `calcul_stock_cultures()` — vegetative vs reproducteur crop logic |
| `utils/parcelles.py` | Plot management, `normalize_parcelle_name()`, occupancy calc |
| `utils/actions.py` | `normalize_action()`, `ACTION_MAP` keyword→canonical mapping |
| `utils/date_utils.py` | `parse_date()` — ISO strings to datetime |
| `utils/tts.py` | `send_voice_reply()`, TTS on/off state persisted in `utils/.tts_state.json` |
| `utils/meteo.py` | Weather fetch from Open-Meteo (free, no API key) |

### Data Model

**Parcelles** — garden plots with a normalized name (`nom_normalise`: lowercase, no accents, no spaces/dashes). Soft-deleted via `actif` flag.

**Evenements** — gardening events (plantings, harvests, losses, waterings, etc.) always linked to a `Parcelle` via `parcelle_id` (NOT NULL since migration v12). Key fields: `type_action`, `culture`, `variete`, `quantite`, `unite`, `date`, `type_organe_recolte`.

**CultureConfig** — crop metadata, especially `type_organe_recolte`:
- `végétatif` (lettuce, carrot, radish): harvest destroys the plant → stock decreases on harvest
- `reproducteur` (tomato, zucchini, pepper): harvest is independent → stock only decreases on loss

### Canonical Action Names

`recolte`, `semis`, `plantation`, `arrosage`, `desherbage`, `taille`, `paillage`, `tuteurage`, `fertilisation`, `observation`, `perte`, `mise_en_godet`

## Database Migrations

Manual SQL files in `migrations/`, numbered sequentially (v2 → v12). Apply in order on a fresh DB. Latest: `migration_v12.sql` — removes the denormalized `evenements.parcelle` text column; `parcelle_id` is now NOT NULL with FK.

## Testing

Tests are in `tests/`. `conftest.py` sets `APP_ENV=test` and `DATABASE_URL=sqlite:///:memory:`, so PostgreSQL is not required. Each test clears DB state via fixtures.

User story tests follow the pattern `test_us*.py` and cover specific features end-to-end. The `tests/` directory has 13+ test files covering actions, API, bot, Groq mocks, and each user story.

## Language & Conventions

- **French throughout**: comments, variable names, LLM prompts, user-facing strings
- **Logging**: centralized logger `log = logging.getLogger("potager")`
- **Docstrings**: reference user stories as `[US-001]`, etc.
- **Type hints**: Python 3.9+ syntax (`dict[str, X]`, `list[X]`)
- Parcelle name normalization: `strip().lower()` + `unidecode()` + remove spaces/dashes

## Responsive frontend — partage breakpoints Tailwind / container queries (NON NÉGOCIABLE)

Règle décidée lors de la refonte UI 2026 (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md`) — s'applique à tout code React ajouté ou modifié dans `frontend/` :

- **Breakpoints Tailwind (`md:`, `lg:`…)** : réservés exclusivement à la structure de page
  globale — afficher/masquer la bottom tab bar, basculer entre layout mobile et layout
  desktop avec sidebar. C'est la seule couche qui répond légitimement à « quelle est la
  taille de l'écran ? ».
- **Container queries (`@container`)** : règle par défaut pour tout composant réutilisable
  (`ParcelleCard`, `ObservationIcon`, panneaux, listes…). Dès qu'un composant est destiné à
  apparaître dans plus d'un contexte de layout, il naît avec `container-type: inline-size`
  sur son wrapper, point final — pas de discussion au cas par cas pendant le développement
  des US.

## External Dependencies

- **FFmpeg**: required for MP3→OGG/Opus conversion (Telegram voice replies); gracefully degraded if missing
- **Open-Meteo**: weather API (free, no key)
- **Groq**: LLM API — models configured in `.env` as `GROQ_MODEL` and `GROQ_WHISPER_MODEL`

## Roadmap v2.0 — Fix hallucinations mode interrogation

### Mission
Implémenter le fix critique hallucinations mode interrogation en 20h (10 jours).

### Documentation disponible

Tous les docs sont dans `docs/` :
- `docs/00_INDEX_NAVIGATION.md` — guide de navigation
- `docs/RESUME_EXECUTIF_1PAGE.md` — synthèse 5 min
- `docs/SCHEMAS_ARCHITECTURE_ASCII.md` — diagrammes avant/après + TEST MATRIX
- `docs/PLAN_IMPLEMENTATION_20h.md` — code exact à implémenter (référence quotidienne)
- `docs/AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` — contexte complet

### Quick Start

1. Lire `docs/RESUME_EXECUTIF_1PAGE.md` (5 min)
2. Implémenter `docs/PLAN_IMPLEMENTATION_20h.md` → section Jour 1–2
3. Tester via `docs/SCHEMAS_ARCHITECTURE_ASCII.md` → TEST MATRIX

### Bug critique

`classify_intent()` (bot.py ~l.730) classifie mal les questions en ACTION → `_parse_and_save()` est appelée sur une question → Groq hallucine un JSON avec `culture` seule → la garde-fou passe → fausse entrée sauvegardée en base (3–5/jour). Coût additionnel : ~5000 tokens/question (frôle quota 100k/jour).

### Impact attendu

- 0 fausses entrées (avant : 3–5/jour)
- -56% tokens Groq (avant : ~94k/jour, après : ~41k/jour)
- Effort : 20h (10 jours × 2h)

### Fichiers à modifier / créer

| Fichier | Action | Changement |
|---------|--------|-----------|
| `bot.py` ~l.730 | MODIFIER | Enrichir `_CLASSIFY_PROMPT` (30+ exemples questions) |
| `bot.py` ~l.1283 | MODIFIER | Refactorer `_ask_question()` → ne plus appeler `parse_commande()` |
| `llm/groq_client.py` ~l.44 | MODIFIER | Ajouter `extract_intent_query()` (~100 tokens) |
| `utils/validation.py` | CRÉER | `validate_parsed_action()` — whitelist + règles strictes |
| `llm/sql_agent.py` | CRÉER | `build_sql_query()` + `query_agent_answer()` — Python pur, zéro Groq |
| `tests/test_validation.py` | CRÉER | Tests unitaires validation |

> Lire `docs/PLAN_IMPLEMENTATION_20h.md` section du jour avant de coder — le code exact y est, zéro ambiguïté.

## Base de données — Serveur Scaleway

PostgreSQL hébergé sur un VPS Scaleway. Deux bases en production :

| Base | Owner | Usage |
|------|-------|-------|
| `potager_dev` | `potager_user` | Environnement de développement |
| `potager_prod` | `potager_user` | Environnement de production |

### Accès local via tunnel SSH

```powershell
# Ouvrir le tunnel (laisser tourner)
ssh -L 5433:localhost:5432 root@<IP_SERVEUR> -N
```

Puis dans pgAdmin (ou tout client PostgreSQL) :
- Host : `localhost`
- Port : `5433`
- Username : `potager_user`
- DB dev : `potager_dev` / DB prod : `potager_prod`

### Serveur Hetzner (`162.55.57.49`) — accès direct sans tunnel

PostgreSQL 14 (cluster `main`), mêmes bases/owner que ci-dessus. Accès direct configuré
depuis pgAdmin, restreint à l'IP fixe du poste client (whitelist, pas d'ouverture publique).

Conf côté serveur (déjà appliquée, à reproduire si le serveur est réinstallé) :

1. `/etc/postgresql/14/main/postgresql.conf` :
   ```
   listen_addresses = '*'
   ssl = on
   ```
2. `/etc/postgresql/14/main/pg_hba.conf` (ligne ajoutée en bas) :
   ```
   host    potager_dev,potager_prod    potager_user    <IP_CLIENTE>/32    scram-sha-256
   ```
3. `systemctl restart postgresql`
4. Hetzner Cloud Firewall (`potager-firewall`, console web, pas depuis le serveur) :
   règle inbound TCP port `5432`, source = `<IP_CLIENTE>/32` (jamais `0.0.0.0/0`)

⚠️ Si l'IP publique du poste client change, il faut mettre à jour à la fois la ligne
`pg_hba.conf` et la règle du firewall Hetzner, sinon la connexion est refusée.

pgAdmin (sans tunnel) : Host `162.55.57.49`, Port `5432`, Username `potager_user`,
SSL mode `Require`.

### Rôle applicatif `app_user` — Row-Level Security (US-043)

Depuis `migration_v18.sql`, un rôle PostgreSQL non-superuser `app_user` protège
`evenements`, `parcelles`, `culture_config` par Row-Level Security (défense en
profondeur, indépendante du scoping applicatif `ctx.potager_id` de US-042).

- `potager_user` (owner des tables) reste le rôle des migrations/`pg_dump` —
  RLS ne s'applique jamais à lui (comportement standard PostgreSQL).
- **`DATABASE_URL` (`.env.dev` / `.env.prod`) doit pointer vers `app_user`**
  pour que la protection RLS soit effective côté bot/API — tant que
  l'application se connecte avec `potager_user`, RLS reste inactif pour elle.
- `database/db.py` arme le GUC de session `app.potager_id` (via `SET LOCAL`)
  à partir du `TenantContext` courant — voir `bot.py::_arm_tenant_context`
  (handler Telegram, groupe -1) et `main.py::_tenant_context_middleware`
  (middleware FastAPI). Toute session DB sans ce GUC positionné échoue en
  fail-fast dès qu'elle touche une table protégée (`current_setting`
  lève une erreur explicite) — jamais un simple zéro ligne silencieux.
- Jobs de fond hors dispatch Telegram/HTTP (ex. `job_meteo_quotidienne`)
  doivent positionner `app.potager_id` eux-mêmes via
  `database.db.tenant_scope(potager_id)` avant toute requête.
- Rollback : `migrations/rollback_v18.sql` (supprime policies, désactive RLS,
  supprime `app_user` — remettre `DATABASE_URL` sur `potager_user` si besoin).

## Vérification d'e-mail (US-044) — Brevo, ImprovMX, Scaleway DNS

Chaîne de services impliquée dans l'inscription web (`POST /auth/register` →
mail de vérification → `GET /auth/verify-email`). Documentée ici pour pouvoir
tout reconfigurer à l'identique en cas de perte totale d'accès à ces comptes
tiers — les secrets eux-mêmes (clé API Brevo) ne sont **jamais** dans ce
fichier, uniquement dans `.env.dev` / `.env.prod` (non versionnés).

### Vue d'ensemble de l'architecture

```
Utilisateur → PWA → API FastAPI (serveur Hetzner)
                        │
                        │ POST https://api.brevo.com/v3/smtp/email
                        ▼
                     Brevo (envoi du mail de vérification)
                        │
                        ▼
              noreply@potager.eremy.fr (adresse expéditrice)
                        │  redirection (pas de vraie boîte mail)
                        ▼
                  ImprovMX → boîte Gmail personnelle
                  (sert uniquement à recevoir le mail de
                   confirmation d'expéditeur envoyé par Brevo)

DNS de eremy.fr → géré chez Scaleway (Domains & Web Hosting > Domains & DNS)
Serveur applicatif (bot + API + PWA) → hébergé chez Hetzner (VPS Cloud)
```

Point clé : **le domaine `eremy.fr` est enregistré et son DNS géré chez
Scaleway**, alors que le serveur applicatif tourne chez **Hetzner** — deux
hébergeurs distincts. L'enregistrement DNS `A` de `potager.eremy.fr` pointe
vers le serveur Hetzner (site + API) ; les enregistrements `MX`/`TXT` ajoutés
pour ImprovMX coexistent avec lui sans conflit.

### Pourquoi Brevo plutôt qu'un SMTP auto-hébergé

Hetzner bloque le port 25 sortant par défaut sur ses VPS Cloud (anti-spam ;
déblocage possible sur ticket après ~1 mois d'ancienneté, au cas par cas) et
ses plages d'IP sont fréquemment blacklistées par les grands webmails — la
délivrabilité y serait mauvaise même débloqué. Brevo (société française,
hébergement UE, 300 mails/jour gratuits à vie) est donc appelé exclusivement
via son API HTTPS (`app/services/email.py`), jamais via SMTP sortant depuis
le VPS.

### Reconfiguration de zéro (perte totale d'accès)

1. **Compte Brevo** (brevo.com, gratuit, sans CB) :
   - Créer le compte, confirmer l'e-mail
   - **SMTP & API → API Keys** : générer une clé API par environnement
     (`assistant-potager-dev`, `assistant-potager-prod`) — le quota gratuit
     de 300 mails/jour est partagé entre toutes les clés d'un même compte
   - **Expéditeurs, domaine, IP → Expéditeurs → Ajouter un expéditeur** :
     `noreply@potager.eremy.fr`, nom affiché `Assistant Potager`
   - Sur la popup "Authentifier votre domaine maintenant ?" → **"Reporter à
     plus tard"** (l'authentification complète du domaine — SPF/DKIM via
     enregistrements DNS individuels, jamais la délégation NS qui casserait
     le site web — est une amélioration de délivrabilité optionnelle, pas un
     prérequis)
   - Cliquer le lien de confirmation reçu sur `noreply@potager.eremy.fr`
     (voir étape ImprovMX ci-dessous pour pouvoir le recevoir)

2. **Compte ImprovMX** (improvmx.com, gratuit) — redirection de mail, sans
   héberger de vraie boîte :
   - **Add domain** → `potager.eremy.fr`
   - Récupérer les enregistrements `MX` (x2, priorités 10/20) et `TXT` (SPF)
     affichés par ImprovMX
   - Les ajouter dans la zone DNS Scaleway (voir étape 3), avec `Name` =
     `potager` (pas le domaine complet — Scaleway complète avec `.eremy.fr`)
   - Configurer l'alias `noreply` (ou `*`) → adresse Gmail personnelle de
     réception

3. **Zone DNS Scaleway** (console.scaleway.com → Domains & Web Hosting →
   Domains & DNS → `eremy.fr` → onglet **DNS Zones**) :
   - Ajouter les enregistrements MX/TXT d'ImprovMX (étape 2) sur le nom
     `potager`, **sans toucher** à l'enregistrement `A` existant qui pointe
     `potager.eremy.fr` vers le serveur Hetzner
   - Le domaine lui-même (registrar + zone DNS) reste chez Scaleway même si
     rien d'autre n'y est hébergé — ne pas chercher ce domaine côté Hetzner

4. **Variables d'environnement** à renseigner dans `.env.dev` / `.env.prod`
   (jamais commitées, cf. `.gitignore`) :
   ```
   BREVO_API_KEY=<clé générée à l'étape 1, une par environnement>
   EMAIL_FROM=noreply@potager.eremy.fr
   EMAIL_FROM_NOM=Assistant Potager
   FRONTEND_URL=<URL de la PWA — http://localhost:3000 en dev>
   ```
   `BREVO_API_KEY` vide → mode dégradé (`app/services/email.py` logue le
   lien de vérification au lieu d'appeler l'API), utilisable sans aucun des
   comptes ci-dessus tant qu'un envoi réel n'est pas nécessaire.

5. **Migration BDD** : `migrations/migration_v24.sql` (colonnes
   `verification_token_*` sur `users`) doit être rejouée si la base est
   reconstruite de zéro — `update_dev.ps1` s'en charge automatiquement en dev.

## Déploiement & Docker

### ⚠️ IMPORTANT — Protocole de déploiement

**JAMAIS** faire `pg_dump > file.sql` + import manuel. Cela crée des problèmes d'encodage (UTF-8 vs WIN1252) et de collation imprévisibles.

### ✅ Solution recommandée : Docker Compose

**TODO** — À mettre en place ASAP avant le prochain déploiement :

1. Créer `Dockerfile` (Python + dépendances)
2. Créer `docker-compose.yml` (API + PostgreSQL)
3. Utiliser **scripts de migration versionnés** (Alembic), pas de dumps manuels
4. Toutes les config via variables d'env (`.env.local`, `.env.prod`)

**Bénéfices** :
- ✅ Encodage UTF-8 natif (Linux)
- ✅ Marche identique Windows/Mac/Linux
- ✅ Zéro soucis de collation
- ✅ Redéploiement = `docker-compose up`
- ✅ Pas de stato "c'était bon sur ma machine"

**Effort estimé** : 4h (une seule fois)

**Retour sur investissement** : éviter 10h+ de galère lors du prochain déploiement
