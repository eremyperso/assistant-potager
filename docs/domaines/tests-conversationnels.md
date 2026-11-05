# Tests conversationnels sur Telegram (US-288)

Jouer des dialogues écrits en Markdown depuis un **vrai compte Telegram** devant un **bot de test**
branché sur le **vrai modèle**, vérifier les réponses et ce qui est écrit en base, produire un rapport.
Complète, sans le remplacer, `tools/evaluer_dialogues.py` (US-256) : celui-ci rejoue la cascade
d'interprétation **en processus**, avec un potager fictif et sans Telegram ; `tests_conv/` traverse
aussi les handlers, les boutons inline, les états en attente et la base.

## Pièces

| Pièce | Rôle |
|---|---|
| `tests_conv/scenarios/*.md` | un fichier = un scénario (format en tête de `harness/parser.py`) |
| `tests_conv/harness/parser.py` | Markdown → `Scenario`, erreurs avec fichier et ligne |
| `tests_conv/harness/driver.py` | pilote Telethon : envoi, clic de bouton, fin de réponse par quiescence, `FloodWait`, coupures réseau |
| `tests_conv/harness/base.py` | lit la base de test (événements, actions, outils, jetons), sème les parcelles, crée le compte de test |
| `tests_conv/harness/assertions.py` | vérifications déterministes (texte, boutons, écritures, outils, latence) |
| `tests_conv/harness/runner.py` | remise à zéro, passages, verdict par scénario |
| `tests_conv/harness/report.py` | `rapport.json`, `rapport.html`, `junit.xml` dans `rapports_conv/<horodatage>/` |
| `app/services/mode_test.py`, `app/bot/mode_test.py` | `/reset_test` : vide le potager de test et les états en attente du bot |

## Décisions

* **`/reset_test` n'existe qu'en `APP_ENV=test`**, et refuse de tourner si la base n'a pas « test » dans son nom.
  Le harnais est un autre processus : il ne peut pas vider les dictionnaires `_*_PENDING` de `app/bot/etat.py`,
  d'où une commande du bot plutôt qu'un simple `DELETE`.
* **Pas de journal JSON dédié** : l'instrumentation est la base elle-même — `echanges_conversation.outils`,
  `actions_menees`, `evenements`, `conso_tokens`.
* **Verdict** : un passage réussit sans vérification bloquante en échec ; un scénario est `ÉCHEC` sous son
  `seuil`, `À SURVEILLER` entre le seuil et 100 %. Une puce `- ? …` est informative.
* **Le juge LLM n'est pas branché** (phase 2). La puce `- juge: …` se parse et ressort « non évaluée ».
  Il devra être un modèle autre que celui de l'agent.
* **`run` sans `--go` n'appelle rien** : il annonce le nombre de messages, donc d'appels au modèle.
* Les scénarios ne contiennent que des données **fictives** : les transcriptions finissent dans les rapports.

## Mise en place (une fois)

1. BotFather : créer un bot de test, noter token et nom d'utilisateur.
2. Un compte Telegram dédié (numéro distinct) ; `api_id` et `api_hash` sur my.telegram.org.
3. Base PostgreSQL `potager_test`, migrations jouées.
4. `.env.test` : voir la section « Mode test conversationnel » de `.env.example`.
5. `pip install -r requirements-conv.txt`
6. `python -m tests_conv session` (interactif) → coller `TELEGRAM_TEST_SESSION` dans `.env.test`.
7. Lancer le bot de test : `$env:APP_ENV="test"; python -m app.bot` (un seul processus par token).
8. `python -m tests_conv seed` : crée le compte, le potager et la liaison du chat de test.

## Utilisation

```powershell
python -m tests_conv validate                       # parse les scénarios, aucun appel
python -m tests_conv run --id SC-000 --go           # fumée : /help
python -m tests_conv run --tag critique --go
python -m tests_conv run --id SC-010 --passages 5 --go
```

Codes de sortie : 0 aucun échec, 1 au moins un `ÉCHEC`, 2 campagne impossible ou non confirmée.

## Ce qui rend cette fiche fausse

Un nouveau genre de vérification (`CLES` dans `parser.py` et `assertions.evaluer`), une table ajoutée à
`TABLES_CONSERVEES`, un changement des libellés de boutons de confirmation (les scénarios les citent),
l'ajout d'un état en attente hors du suffixe `_PENDING` (la remise à zéro ne le verrait pas).

## Limites connues

* Le pilote Telethon n'est testé que contre un vrai bot : `tests/test_us288_*` couvre le reste.
* Un compte utilisateur piloté par script reste soumis aux limites de débit de Telegram : pas de parallélisme.
* Le harnais lit la base : il suppose que le bot de test et lui partagent le même `DATABASE_URL`.
