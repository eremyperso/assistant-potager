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

**bot.py** — Telegram bot. Handles voice notes (transcribed via Whisper) and text commands. Key handlers: `/parse` (log event), `/ask` (analytics question), `/stats`, `/plan`, `/parcelle`. Runs a daily 5am job to fetch weather via Open-Meteo.

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
