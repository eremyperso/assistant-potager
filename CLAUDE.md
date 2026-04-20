# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Langue

Toujours répondre en français, quelle que soit la langue utilisée dans les messages.

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

# Start Telegram bot
python bot.py

# Start FastAPI server (http://localhost:8000)
python main.py

# Apply latest database migration
psql -d potager -f migrations/migration_v12.sql

# Redéployer l'environnement dev local (pull + deps + migrations)
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

| Commande | Description |
|----------|-------------|
| `/start` | Menu principal + compteur d'événements |
| `/help` | Aide générale |
| `/help parcelle` | Aide ciblée — mots-clés : `parcelle`, `semis`, `godet`, `recolte`, `stock`, `stats` |
| `/stats` | Statistiques saison (végétatif vs reproducteur) |
| `/stats <culture>` | Détail par variété pour une culture donnée |
| `/historique` | 10 derniers événements |
| `/ask <question>` | Question analytique en langage naturel (ou `/ask` seul puis saisie) |
| `/corriger` | Lancer le flux de correction d'un événement existant |
| `/plan` | Plan d'occupation global du potager |
| `/plan <parcelle>` | Plan détaillé d'une parcelle spécifique |
| `/parcelle ajouter <nom> [exposition] [superficie]` | Créer une parcelle (détection de doublons) |
| `/parcelle modifier <nom> clé=valeur …` | Modifier les métadonnées (`exposition`, `superficie`, `ordre`) |
| `/parcelle renommer <ancien> <nouveau>` | Renommer (propagation sur tout l'historique) |
| `/parcelle lister` | Lister toutes les parcelles |
| `/parcelles` | Alias de `/parcelle lister` |
| `/meteo` | Récupérer et afficher la météo manuellement (job auto à 05h00) |
| `/tts` | Afficher l'état de la synthèse vocale |
| `/tts_on` | Activer les réponses vocales |
| `/tts_off` | Désactiver les réponses vocales |

#### Clavier inline (boutons persistants)

Menu principal : `🎤 Nouvelle action vocale` · `🔍 Interroger` · `📋 Historique` · `📊 Stats` · `✏️ Corriger`

Après enregistrement : `➕ Autre action` · `🔍 Interroger mes données` · `📋 Historique` · `🏠 Menu principal`

#### Intents vocaux reconnus (classification Groq)

`ACTION` · `INTERROGER` · `STATS` · `HISTORIQUE` · `PLAN` · `CORRIGER` · `SUPPRIMER` · `MENU` · `NOUVELLE`

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
