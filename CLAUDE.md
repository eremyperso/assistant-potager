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

## Pull requests (NON NÉGOCIABLE)

Toute description de PR (quelle que soit la branche source ou cible — feature, hotfix,
release `dev` → `main`…) qui livre au moins une US DOIT se terminer par une section :

```markdown
## Jira US
**US-XXX** : PIA-YY
```

listant chaque US livrée dans la PR avec sa clé Jira correspondante — une ligne par US.

Il n'existe **aucun fichier local de correspondance** US ↔ clé Jira dans ce repo : la clé
DOIT être retrouvée en interrogeant Jira en direct via le MCP Atlassian (`searchJiraIssuesUsingJql`),
en cherchant dans le projet `PIA` les tickets dont le `summary` contient `US-XXX` (convention
de titrage des tickets : `US-XXX : <description>`). Ne jamais inventer ou deviner une clé
Jira, et ne jamais omettre cette section faute de l'avoir vérifiée.

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
psql -d potager -f migrations/migration_v42.sql

# Purge des potagers supprimés au-delà du délai de grâce de 30 jours [US-084]
# (aussi planifiée quotidiennement à 04h00 par le job_queue du bot)
python tools/purger_potagers.py --dry-run   # liste sans rien effacer
python tools/purger_potagers.py             # purge réelle, idempotente

# Import du référentiel structuré + rapport de couverture [US-166]
# Hors ligne (aucun appel réseau), idempotent, rejouable.
python tools/importer_referentiel.py data/referentiel/wikidata_familles.json
python tools/importer_referentiel.py data/referentiel/wikidata_familles.json --dry-run
python tools/importer_referentiel.py --rapport-seul        # rapport sans rien importer
python tools/importer_referentiel.py --derive-de wikidata  # que retirer avec cette source ?
python tools/importer_referentiel.py --lister-sources      # registre : licence + attribution

# Attributs agronomiques de conduite [US-161]
# Le gabarit est livré VIDE et se remplit à la main : aucun chiffre agronomique
# n'est produit par un modèle de langage. Une valeur null n'écrit rien.
python tools/importer_referentiel.py data/referentiel/attributs_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/attributs_redaction_interne.json
# Source Wind River Greens (CC BY 4.0) — attribution obligatoire à l'affichage
# L'adaptateur produit un manifeste ; l'import le joue. Aucun appel réseau.
python tools/adapter_wind_river.py                    # CSV versionnés → manifeste
# Écrit aussi wind_river_associations.json — extraction BRUTE pour US-163,
# à NE PAS passer à l'import : elle n'est pas révisée et ne s'importe pas.
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
# Provenance, version figée et périmètre : data/referentiel/wind_river_greens/SOURCE.md

# Correction depuis le bot — prime sur tout rejeu de l'import :
#   /culture attributs <culture>
#   /culture exposition <culture> <plein soleil|mi-ombre|ombre>
#   /culture eau <culture> <faible|moyen|élevé>
#   /culture profondeur <culture> <cm>
#   /culture rusticite <culture> <°C>

# Associations de cultures et rotation calculable [US-163]
# La saisie au bot reste le chemin premier (option A sur la licence — zéro
# CC-BY-SA dans le socle). Amendement du 02/09/2026 : une source déjà au socle
# en CC BY 4.0 (wind_river_greens, US-161) peut aussi alimenter la table après
# curation humaine (traduction, périmètre, doublons) — jamais brute.
#   /association lister <culture>
#   /association saisir <cultureA> <cultureB> <favorable|defavorable|neutre> <etabli|traditionnel> <motif>
# Import (même commande que les attributs de conduite — un seul manifeste) :
python tools/adapter_wind_river.py                    # régénère le manifeste, associations incluses
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json --dry-run
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
# Rotation : un conflit se calcule (evenements × culture_config × familles_botaniques),
# il ne se rédige pas — consultation seule ici, l'alerte proactive est US-167.
#   /rotation <parcelle> <culture>
# CA12 : temps de réponse à VÉRIFIER sur la production avant tout câblage
# automatique (US-167) — jamais supposé sous prétexte que les index existent.
python tools/mesurer_rotation.py <parcelle_id> <culture>

# Menu de commandes natif Telegram [US-171]
# Le menu (bouton « Menu » du client Telegram) n'est pas une liste tenue à la main :
# il se dérive des CommandHandler enregistrés dans bot._construire_application().
# Une commande ajoutée y entre au redémarrage suivant. Trois décisions, un seul
# fichier — app/services/menu_commandes.py :
#   COMMANDES_EXCLUES   ce qui n'entre pas au menu (/version, /delier, /tts)
#   ORDRE_METIER        l'ordre de lecture des lignes
#   DESCRIPTIONS        la phrase d'aide (≤ 60 caractères, lisible à 375 px)
# Le clavier de raccourcis permanent n'existe plus : bot.SANS_CLAVIER
# (ReplyKeyboardRemove) le retire activement chez les jardiniers qui l'avaient.
# Les claviers contextuels de validation, eux, sont inchangés.

# Socle de connaissance — étage 2 de la cascade [US-098]
# ⚠️ Procédure complète (rédaction des fiches, licences, mesure, mise en prod
# dans le bon ordre) : docs/RUNBOOK_ALIMENTATION_SOCLE_CONNAISSANCE.md
# La base est l'INDEX, le dépôt est la SOURCE : rien ne s'édite en base, une
# fiche se corrige dans data/connaissance/ puis se réingère. Le dossier est
# livré VIDE — le contenu arrive avec US-099, US-140 et US-141, et tant qu'il
# est vide l'étage est inerte (la cascade se comporte comme avant l'US).
psql -d potager -f migrations/migration_v42.sql
python tools/ingerer_connaissance.py --dry-run    # rapport seul, aucune écriture
python tools/ingerer_connaissance.py             # idempotent : même empreinte = rien réécrit
python tools/ingerer_connaissance.py --strict    # échoue sur un fragment non autonome (CA12)
python tools/ingerer_connaissance.py --elaguer   # retire aussi les fiches supprimées du dépôt
# ⚠️ RLS (migration_v42) : une fiche GLOBALE ne s'écrit qu'avec le rôle
# propriétaire de la base, jamais app_user — même règle que importer_referentiel.
#
# CA13 : la mesure conditionne l'activation en production, elle ne se suppose pas.
# Le score n'est PAS sur la même échelle en SQLite (repli de test, couverture de
# termes) et en PostgreSQL (ts_rank_cd) : RAG_SEUIL_CONFIANCE doit être
# réétalonné contre la production AVANT d'y ingérer un corpus.
python tools/mesurer_corpus_savoir.py --ingerer --detail
# Interrupteurs (config.py, variables d'environnement, sans redéploiement) :
#   RAG_ACTIF=0            coupe l'étage du savoir
#   RAG_SEUIL_CONFIANCE    au-dessus : réponse servie telle quelle, à coût nul
#   RAG_MAX_PASSAGES       nombre de passages retenus (3 = cible du CA13)
# Ce que la base ne sait pas répondre — c'est cela qui dit quoi écrire ensuite :
#   GET /admin/savoir/lacunes   (réservé à ADMIN_EMAIL)
#
# Format de fiche : une fiche = un couple culture × thème (tomate-problemes.md).
# La recherche est LEXICALE — un lemme absent de l'index est un rapprochement
# impossible, quelle que soit la qualité du texte. D'où la ligne qui décide de
# tout, dans CHAQUE section (jamais dans l'en-tête) :
#   **On parle aussi de :** cul noir ; nécrose apicale ; manque de calcium
# Les deux registres, celui du jardinier ET celui de l'agronome. Mesuré sur 24
# fiches et 19 questions réelles, contre PostgreSQL : 17/19 en tête, 19/19 dans
# les trois premiers. Ne jamais répéter le nom de la culture dans cette ligne :
# le titre du document le porte déjà sur TOUS les fragments de la fiche, et
# `ts_rank_cd` compte les occurrences — la section vole alors le classement à
# ses voisines. L'ingestion retire d'elle-même les lexèmes déjà présents.
# `index_terms:` au niveau du DOCUMENT n'est pas indexé (il dilue : 15/19) —
# c'est un index de relecture, il reste dans le fichier.
# Ce que l'ingestion retire avant d'indexer, sans rien supprimer du .md :
# le `# H1` de tête, la section `## Sources et licence`, et les lignes
# `**Intention :**` / `**Organes concernés :**` / `**On parle aussi de :**`.
# Un `**Attention :**` — clé inconnue — reste du contenu : on ne retire que ce
# qu'on sait nommer. Gabarit complet : data/connaissance/README.md
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



## Database Migrations

Manual SQL files in `migrations/`, numbered sequentially (v2 → v42), each with its `rollback_vN.sql` since v16. Apply in order on a fresh DB. Latest: `migration_v42.sql` [US-098] — creates `knowledge_documents` / `knowledge_chunks` (full-text GIN index, RLS on both tables), adds `score_savoir` / `issue_savoir` to `routage_logs`, and creates the `french_sans_accent` text search configuration (`french` + `unaccent`). That configuration is not a refinement: `french` alone lemmatises but does NOT strip accents, so « récolter » and « recolter » are two unrelated lexemes, and a gardener typing without accents — the norm on mobile — misses every accented term in the corpus. The migration verifies it (`to_tsvector('french_sans_accent', 'récolter recolter')` must yield a single lexeme). It must stay identical to `app/services/connaissance.CONFIG_FTS`, which serves both the write and the query side.

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


