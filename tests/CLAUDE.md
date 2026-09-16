# tests — pytest, SQLite en mémoire, aucun PostgreSQL requis

`conftest.py` fixe `APP_ENV=test` et `DATABASE_URL=sqlite:///:memory:` avant tout
import. Un fichier par US : `test_usNNN_<composant>.py`. Corpus de mesure dans
`tests/corpus/`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_usNNN_x.py -q      # ciblé, à chaque itération
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short            # complet, une fois en fin de QA
```

## Économie de contexte

- Lancer les tests CIBLÉS pendant le développement ; la suite complète (≈ 3 000
  tests, ~70 s) une seule fois en fin de QA, avec `-q` et sans `-v`.
- Filtrer la sortie : `2>&1 | grep -E "^(FAILED|ERROR)|passed|failed"`.
- Ne pas produire `rapport_tests.html` ni `htmlcov/` sauf demande (ignorés par git).

## Tests sur le bot (`app/bot/`)

- Importer par `from app import bot as bot_module` ; patcher par
  `monkeypatch.setattr(bot_module, "SessionLocal", …)` ou `patch("app.bot.X")` :
  la façade propage aux sous-modules.
- Lire le source du bot : concaténer `bot_module._SOUS_MODULES`, jamais
  `inspect.getsource(bot_module)` (ce serait la façade).
- L'API se patche sur `app.api.main.<nom>` ; la configuration sur `app.config.<nom>`.

## Tests structurels

Certains tests lisent des fichiers du dépôt (scripts de déploiement, workflows,
services systemd, absence de `db.query` direct hors services) : déplacer un
fichier impose de mettre à jour leur chemin dans le même commit.
