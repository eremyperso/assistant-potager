# CLAUDE.md

Guide pour Claude Code sur ce dépôt. Ce fichier est chargé à CHAQUE appel : il
ne porte que l'essentiel. Le détail vit dans `docs/domaines/` (lu à la demande)
et dans les `CLAUDE.md` de sous-dossiers (chargés quand on y travaille).

## Langue

Toujours répondre en français, quelle que soit la langue utilisée dans les messages.

## Efficacité de contexte (s'applique à toute session)

- **Chercher avant de lire** : `grep -n` / Glob d'abord, puis lecture des seules
  plages utiles. Ne jamais lire un fichier de plus de 300 lignes en entier sans
  raison explicite.
- **Tests ciblés** pendant le développement ; la suite complète une seule fois en
  fin de QA, en `-q`, sortie filtrée sur `FAILED|ERROR|passed|failed`.
- **Une US = une session** (`/clear` entre deux US) ; `/compact` si la session s'allonge.
- **Fiche de domaine avant le code** : la table de `docs/domaines/README.md` dit
  quelle fiche lire selon le fichier touché. Une seule fiche par US, en général.
- Les sorties volumineuses (diff complet, `git log` long, rapports HTML) restent
  dans le terminal ou un fichier, pas dans le contexte.

## Règles d'exécution des agents (NON NÉGOCIABLES)

Ces règles s'appliquent à chaque invocation d'un agent défini dans `.github/agents/`.

1. **Lire le fichier agent avant toute action** : avant d'exécuter le rôle d'un
   sous-agent, lire intégralement son fichier `.github/agents/*.agent.md`.
2. **Patch Notes Writer — checklist obligatoire** : à l'étape Documentation, les
   deux fichiers suivants DOIVENT être modifiés sans exception :
   - `PATCH_NOTES.md` — nouvelle entrée insérée EN HAUT
   - `VERSION` — numéro incrémenté selon SemVer (PATCH / MINOR / MAJOR)
3. **Confirmation d'étape** : après chaque étape de l'Orchestrateur, indiquer
   explicitement « Étape X terminée » avec les fichiers modifiés.

## Corpus de connaissance — définition de terminé (NON NÉGOCIABLE)

Règle US-099 / CA9 : une évolution fonctionnelle qui rend une fiche de
`data/connaissance/` fausse impose la mise à jour de cette fiche **dans la même
livraison**, comme une migration. Avant de livrer un changement de comportement :

1. lire la table « ce qui rend une fiche fausse » de `data/connaissance/doc_app/README.md`
   (elle se lit à l'envers : *je touche à ceci, donc je relis cette fiche*) ;
2. corriger la ou les fiches dans le même commit ;
3. `pytest tests/test_us099_corpus_fonctionnement.py` doit rester vert.

Le corpus agronomique (`data/connaissance/agronomie/`, US-140) a sa propre table
dans son `README.md` ; ce qui le périme est un **retour de terrain**, et
`pytest tests/test_us140_corpus_agronomique.py` doit rester vert.

## Pull requests (NON NÉGOCIABLE)

Toute description de PR qui livre au moins une US DOIT se terminer par :

```markdown
## Jira US
**US-XXX** : PIA-YY
```

une ligne par US livrée. Il n'existe aucun fichier local de correspondance : la
clé se retrouve en interrogeant Jira via le MCP Atlassian
(`searchJiraIssuesUsingJql`, projet `PIA`, `summary` contenant `US-XXX`).
Ne jamais inventer une clé, ne jamais omettre la section.

## Vue d'ensemble

**Assistant Potager** : carnet de potager intelligent pour jardiniers amateurs.
Un bot Telegram (voix / texte) et une API FastAPI servant une PWA React, sur
PostgreSQL, avec Groq (LLM + Whisper) pour l'analyse du langage. Flux central :
le jardinier dicte un geste → JSON structuré → `Evenement` rattaché à une `Parcelle`.

```
app/
  bot/          bot Telegram, un module par domaine   → python -m app.bot
  api/main.py   API FastAPI                            → uvicorn app.api.main:app
  services/     couche métier partagée (seule à toucher la base)
  config.py     configuration lue depuis .env.{APP_ENV} (racine du dépôt)
database/       modèles SQLAlchemy, session, tenant_scope
llm/            passerelle Groq, routeur règles-first, parseur déterministe, RAG
utils/          utilitaires (actions, dates, météo, TTS, stock)
data/           référentiel structuré (JSON) et corpus de connaissance (Markdown)
migrations/     SQL manuel, v2 → v48, rollback_vN.sql depuis v16
tests/          pytest, SQLite en mémoire
tools/          import, ingestion, mesures, purge, suivi Jira
scripts/        update_dev.ps1 (env dev), deploy.sh (repli manuel)
infra/          unités systemd ; .github/workflows/ : déploiement dev et prod
frontend/       dashboard React (Vite) ; static/ : ancienne PWA de repli
docs/domaines/  notes de conception par domaine — à lire avant de modifier un module
```

## Commandes de base

```powershell
.\.venv\Scripts\Activate.ps1          # venv du projet (PowerShell est le shell par défaut)
$env:APP_ENV = "dev"

python -m app.bot                                              # bot Telegram (pas de --reload)
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload   # API + frontend buildé
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --port 8000 --reload   # si Activate.ps1 est bloqué

pytest tests/                                     # suite complète (SQLite, sans PostgreSQL)
pytest tests/test_us006_renommer_parcelle.py      # un fichier
pytest tests/ -k "nom_du_test"                    # un test

psql -d potager -f migrations/migration_v48.sql   # dernière migration
.\scripts\update_dev.ps1                          # pull + deps + migrations + corpus ; -SkipPull, -Force
```

`VAR=val cmd` ne fonctionne pas en PowerShell ; `python` et `uvicorn` viennent du
venv, pas du PATH global. Frontend : voir `frontend/CLAUDE.md`.

## Environnement

Copier `.env.example` en `.env.dev` (ou `.env.prod`) à la racine : `APP_ENV`,
`TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `DATABASE_URL`, `JWT_SECRET`. `app/config.py`
charge `.env.{APP_ENV}` depuis le répertoire courant, sinon depuis la racine.
Les réglages sans redéploiement (`RAG_*`, `PREDIAGNOSTIC_*`, `CALENDRIER_ZONE_DEFAUT`,
modèles Groq par type d'appel) y sont documentés en commentaire.

## Déploiement

Prod : push sur `main` → `.github/workflows/deploy.yml` (Scaleway, `/opt/potager-prod`,
services `potager-prod` et `potager-prod-bot`). Dev distant : push sur `dev` →
`deploy-dev.yml` (`/opt/potager-dev`, port 8001). Les unités systemd de `infra/`
sont réinstallées à chaque déploiement : un changement de point d'entrée se fait
là, et se vérifie par `tests/test_us005_deploiement.py`. Runbook :
`docs/RUNBOOK/RUNBOOK_DEPLOIEMENT_PRODUCTION.md`.

## Conventions

- **Français partout** : commentaires, noms, prompts, messages utilisateur.
- Logger centralisé `log = logging.getLogger("potager")` ; docstrings référencent
  l'US `[US-001]` ; type hints Python 3.9+ (`dict[str, X]`).
- Normalisation d'un nom de parcelle : `strip().lower()` + `unidecode()` + retrait
  des espaces et tirets.
- Aucune logique métier dans les handlers (bot ou API) ; aucun `db.query` direct
  hors `app/services/` (test US-041) ; tout appel modèle via `llm.passerelle`.
- Frontend : breakpoints Tailwind pour la page, container queries pour les
  composants (règle non négociable, détail dans `frontend/CLAUDE.md`).

## Dépendances externes

FFmpeg (voix Telegram, dégradé si absent), Open-Meteo (météo, sans clé), Groq
(`GROQ_MODEL`, `GROQ_WHISPER_MODEL` dans `.env`).
