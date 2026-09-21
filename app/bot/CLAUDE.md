# app/bot — bot Telegram (package)

Lancement : `python -m app.bot` (jamais `python bot.py`, qui n'existe plus).
Décisions de domaine (menu natif US-171, dictée US-172) : `docs/domaines/commandes-bot.md`.

## Carte des modules (ordre d'import = ordre topologique, aucun cycle)

| Module | Contenu |
|---|---|
| `noyau` | logging, version (`_APP_VERSION`, `_lire_version` lit `VERSION` à la racine), claviers (`SANS_CLAVIER`), `_md`, `_send_chunked`, dates |
| `etat` | dictionnaires `_*_PENDING` et délais `_*_TIMEOUT` partagés par les flux |
| `normalisation` | `_parser_items`, `_normalize_items`, inférence action / culture / date |
| `aide` | `/help`, `/version`, `_HELP_DOMAINES` (lu par `tools/controler_aide_corpus.py`) |
| `liaison` | `/start`, `/lier`, `/delier`, `/potager`, `/rejoindre`, garde de liaison et de rôle |
| `enregistrement` | récapitulatif, boutons de confirmation, `_do_save_items`, `_parse_multi` |
| `godets` / `pertes` / `notes` | flux conversationnels dédiés |
| `interpretation` | commande dictée (US-172) : proposition, complétion, exécution par introspection |
| `questions` | `classify_intent`, `/ask` (`_ask_question`), godets, retour du jardinier |
| `saisie` | `_parse_and_save` (cœur de la saisie dictée) et les rappels qui y reviennent |
| `correction` / `deplacement` | corriger ou supprimer un événement ; déplacer une culture |
| `commandes_*` | une commande slash par domaine : parcelle, culture, calendrier, plan, stats |
| `file_gestes` | `/gestes`, la file préparée par la PWA (US-224) : niveau 1 (liste, boutons `file:`), niveau 2 (le récapitulatif d'US-021), `/start g<code>`, job horaire (relance, avertissement, purge) |
| `meteo_jobs` | `/meteo`, jobs planifiés (météo 05h, purge 04h) |
| `messages` | `handle_voice`, `handle_text` — points d'entrée des messages libres |
| `application` | `_construire_application`, enregistrement des handlers, `main()` |

## Façade `__init__.py` — à ne pas contourner

`app.bot` expose tous les noms de tous les sous-modules et **propage** toute
affectation (`monkeypatch.setattr(bot, "SessionLocal", …)`, `patch("app.bot.X")`)
vers chaque sous-module qui lie ce nom. Un test qui lit le source du bot
concatène `bot_module._SOUS_MODULES`. Ne pas ajouter d'état global dans
`__init__.py` ; ne pas importer `app.bot.<module>` depuis `app/services/`.

## Règles

- Aucune logique métier ici : un handler appelle `app/services/`, jamais `db.query` direct (test US-041).
- Une commande ajoutée : handler dans `commandes_<domaine>.py`, enregistrement dans
  `application.py`, et décision dans `app/services/menu_commandes.py` (dictable ou
  exclue), sinon `controler_parite()` fait échouer la CI.
- Toute sortie vers un modèle passe par `llm.passerelle` (audit `tools/audit_appels_llm.py`).
- Lire un module entier seulement si nécessaire : `grep -n "^async def \|^def "` d'abord.
