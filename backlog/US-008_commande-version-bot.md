**ID :** US-008
**Titre :** Afficher la version déployée via la commande `/version` du bot Telegram

**Story :**
En tant qu'administrateur
Je veux envoyer `/version` au bot Telegram et obtenir le numéro de version, le SHA git du commit courant et l'environnement actif
Afin de vérifier à tout moment quelle version tourne en production sans avoir besoin d'un accès SSH au serveur

**Critères d'acceptance :**
- [x] CA1 : Un fichier `VERSION` à la racine du projet contient uniquement le numéro de version sémantique (ex : `2.14.1`) et constitue la source de vérité unique pour la version
- [x] CA2 : La commande `/version` est enregistrée dans le bot (`bot.py`) et répond avec un message structuré contenant : numéro de version (lu depuis `VERSION`), SHA git court du commit courant (`git rev-parse --short HEAD`), environnement (`APP_ENV`)
- [x] CA3 : Le message de réponse est lisible sur mobile, par exemple :
  ```
  🌿 Assistant Potager
  Version : 2.14.1
  Commit  : a1b2c3d
  Env     : prod
  ```
- [x] CA4 : Si le fichier `VERSION` est absent, le bot répond `"version inconnue"` sans lever d'exception
- [x] CA5 : Si la commande `git` n'est pas disponible ou que le dépôt n'est pas un repo git, le SHA affiché est `"inconnu"` sans lever d'exception
- [x] CA6 : Le endpoint `GET /health` de l'API (`main.py`) lit la version depuis le fichier `VERSION` au lieu de la valeur codée en dur `"2.0-groq"` — le champ `"version"` de la réponse JSON reflète la valeur du fichier
- [x] CA7 : La commande `/version` apparaît dans la liste affichée par `/help`

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : bot Telegram (`bot.py`), API REST (`main.py`), configuration projet (fichier `VERSION`)
- Migration BDD requise : non
- Le fichier `VERSION` doit être versionné dans git et mis à jour à chaque release (remplace la valeur codée en dur `"2.0-groq"` dans `main.py` ligne 59)
- La lecture du SHA git peut se faire via `subprocess.run(["git", "rev-parse", "--short", "HEAD"], ...)` avec `capture_output=True` et gestion du `CalledProcessError`
- La version peut être lue au démarrage du bot (variable module-level) pour éviter une lecture fichier à chaque appel
- Dépendances : US-004 (gestion environnements dev/prod — `APP_ENV` doit être disponible)

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Feature: Commande /version dans le bot Telegram

  Scenario: Affichage nominal de la version en production
    Given le fichier VERSION contient "2.14.1"
    And le dépôt git a un commit courant avec le SHA court "a1b2c3d"
    And la variable d'environnement APP_ENV vaut "prod"
    When l'administrateur envoie la commande /version au bot
    Then le bot répond avec un message contenant "2.14.1"
    And le message contient "a1b2c3d"
    And le message contient "prod"

  Scenario: Fichier VERSION absent
    Given le fichier VERSION n'existe pas sur le serveur
    When l'administrateur envoie la commande /version au bot
    Then le bot répond sans lever d'exception
    And le message indique "version inconnue"

  Scenario: Dépôt git non disponible
    Given le fichier VERSION contient "2.14.1"
    And la commande git n'est pas disponible dans l'environnement
    When l'administrateur envoie la commande /version au bot
    Then le bot répond sans lever d'exception
    And le message contient "2.14.1"
    And le SHA affiché est "inconnu"

  Scenario: Endpoint /health reflète la version du fichier VERSION
    Given le fichier VERSION contient "2.14.1"
    When un client envoie GET /health à l'API
    Then la réponse JSON contient { "version": "2.14.1" }
    And la valeur n'est plus la chaîne codée en dur "2.0-groq"
```

**Labels GitHub :** `us`, `sprint-5`, `bot-telegram`, `ops`
