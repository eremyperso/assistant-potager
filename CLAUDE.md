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


