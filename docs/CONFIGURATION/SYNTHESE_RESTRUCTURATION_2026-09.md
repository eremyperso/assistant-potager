# Synthèse — restructuration du dépôt et optimisation du contexte (16/09/2026)

Livraison réalisée en réponse au constat de consommation de jetons
(`Contexte-Token-Optimisation-Claude.md`). Quatre chantiers, aucun commit :
tout est dans l'arbre de travail de la branche `epic-8-confiance-personnalisation-calendrier`.

## Résultat des tests

| | Avant | Après |
|---|---|---|
| Réussis | 3 009 | 3 037 |
| Échecs + erreurs | 58 | 53 |
| Nouveaux échecs | | 0 |

Les 53 échecs restants existaient déjà avant intervention (US-140 en repli
SQLite, `test_bot` stats, smoke test du workflow dans `test_us005`, etc.).
Cinq tests de `test_us005_deploiement.py` (unité systemd) sont passés au vert.

## 1. `CLAUDE.md` allégé

Le fichier racine passe de 733 lignes (≈ 20 000 jetons) à 145 lignes
(≈ 2 400 jetons). Rien n'est perdu, le contenu est redistribué :

- `docs/domaines/` : six fiches de conception (référentiel des cultures,
  pré-diagnostic, calendrier cultural, commandes du bot, socle de connaissance,
  migrations) et un `README.md` « je touche à ceci, donc je lis cette fiche ».
- `CLAUDE.md` de sous-dossiers, chargés seulement quand on y travaille :
  `app/bot/`, `app/services/`, `data/`, `frontend/`, `tests/`.
- Section « Efficacité de contexte » en tête du fichier racine.

## 2. `bot.py` découpé en package `app/bot/`

22 modules par domaine, générés par analyse AST, sans cycle d'import :
noyau, état, normalisation, aide, liaison, enregistrement, godets, pertes,
notes, saisie, questions, interprétation, correction, déplacement, cinq
modules de commandes, météo et jobs, messages, application.
Lancement : `python -m app.bot`.

Point clé : 38 fichiers de tests posent des monkeypatch directement sur le
module `bot` (209 fois sur `SessionLocal`). Plutôt que de réécrire ces tests,
`app/bot/__init__.py` est une **façade** qui expose tous les noms et propage
chaque affectation d'attribut vers les sous-modules concernés. Un test qui lit
le source du bot concatène `bot_module._SOUS_MODULES`.

## 3. Consignes d'efficacité dans les agents

Section « Efficacité de contexte » ajoutée à Developer, QA, Orchestrateur,
Analyste-Incident et Patch Notes Writer : chercher avant de lire, lecture par
plages, tests ciblés puis suite complète une seule fois en `-q`, diffs par
fichier, une seule fiche de domaine par US. La structure projet du Developer,
obsolète, est réécrite.

## 4. Arborescence et déploiement

- `main.py` → `app/api/main.py` (`uvicorn app.api.main:app`) ;
  `config.py` → `app/config.py` (le `.env.{APP_ENV}` est cherché dans le
  répertoire courant, puis à la racine du dépôt).
- `update_dev.ps1` et `deploy.sh` → `scripts/` ; `test_jira_*.py` →
  `tools/verifier_jira_*.py`.
- Supprimés : `bot.py`, `bot_meteo_patch.py`, `config.py.example`, `.coverage` ;
  `rapport_tests.html` et `htmlcov/` désormais ignorés par git.
- Déploiement : les quatre unités systemd de `infra/` pointent sur
  `python -m app.bot` et `uvicorn app.api.main:app` ; elles sont réinstallées
  par les workflows à chaque déploiement. Hook `post-merge`, `scripts/deploy.sh`
  (aligné sur `potager-prod` / `potager-prod-bot`), README, SETUP et RUNBOOK
  mis à jour.
- `VERSION` : 3.67.0, entrée ajoutée en tête de `PATCH_NOTES.md`.

## Points d'attention avant de commiter

- Le travail US-177 non commité est mêlé à cette restructuration dans le même
  arbre de travail ; séparer en deux commits demande un tri manuel.
- `llm/`, `database/` et `utils/` restent à la racine (non déplacés sous `app/`
  pour limiter le risque) : suite possible.
- `tools/audit_appels_llm.py` signale `tools/mesurer_modeles_llm.py` (appel
  Groq direct) : état antérieur, non traité.
- Sur les serveurs, rien à faire : le prochain déploiement réinstalle les
  unités systemd. Surveiller le premier redémarrage du bot dev.

## Fichiers de référence

- Bilan des tests avant/après : scratchpad de la session (`baseline.txt`, `apres4.txt`).
- Générateur du découpage (AST) : scratchpad `decouper_bot.py` — usage unique, non versionné.
