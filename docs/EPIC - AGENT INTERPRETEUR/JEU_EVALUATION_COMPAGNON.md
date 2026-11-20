# Le jeu d'évaluation du compagnon

> **Objet** : accepter ou refuser chaque lot de [ARCHITECTURE_COMPAGNON_CAPACITES.md](ARCHITECTURE_COMPAGNON_CAPACITES.md) sur des
> faits (lot 0, §7), et non sur un scénario corrigé à la main.
> **Fichier** : `tests/corpus/jeu_evaluation_compagnon.json` · **Chargeur et contrôles** : `tools/jeu_evaluation/jeu.py` ·
> **Lanceur** : `tools/evaluer_compagnon.py` (US-337) · **Stories** : US-336 (le jeu), US-337 (le lanceur, le juge, le rapport).

## 1. Ce que contient le jeu

| Élément | Valeur |
|---|---|
| Besoins | 24 : planter ou semer une culture (végétative, reproductrice semée en pleine terre, reproductrice en plants), est-ce le moment, que semer ce mois-ci, que faire au potager, arroser ou non, noter un semis / une plantation / une première récolte / une N-ième récolte / la fin de vie du pied / une perte, corriger ce qui vient d'être noté, lire son stock / son carnet / sa pépinière / ses échéances, comprendre un symptôme, trouver une fonction de l'application, cultiver une culture sans fiche, associations, gel |
| Formulations | 5 à 7 par besoin (134 cas) : `directe`, `familiere`, `incomplete`, `faute`, `deux_temps`, `culture_absente`, et `reel` pour un dialogue tiré du terrain |
| Jeux de données | `neuf` (potager de test calqué sur le potager 34) et `rempli` (potager 33, lecture seule) |
| Renouvelables | 35 % des cas, tenus à part des exemples de prompt |

Le cas n° 1 (`B01-F1`) est le dialogue réel du 14/11/2026 (`RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` §1, échanges 441
à 447) : ses 7 phrases sont rejouées telles quelles, sans jardinier simulé, avec l'attendu du tour 1 (« rien à semer ni
planter ce mois-ci, prochaine fenêtre : semis en pépinière de février à mars ; la salade n'est pas au potager »).

### Les jeux de données

* **`neuf`** — une parcelle « planche légumes », 20 m², plein sud, zone océanique, rien en stock. Il est créé par un
  **script rejouable**, jamais à la main dans `potager_test` :
  `python tools/creer_potager_test_neuf.py` (refuse toute base dont le nom ne contient pas « test » ; un second passage
  remet le potager à neuf, sans recréer le compte). Il affiche les numéros à passer au lanceur.
* **`rempli`** — le potager 33 en lecture seule (parcelles « planche principal », « serre », « tunnel »). La mesure n'y
  écrit rien : lectures dans une transaction annulée, écritures simulées au schéma du registre.

## 2. Le format

Le fichier a quatre clés racines : `version`, `jeux_de_donnees`, `configurations` et `besoins`. Chaque **besoin** porte une
fiche et des attendus par défaut ; chaque **formulation** en hérite et peut les surcharger. Le chargeur développe chaque
formulation en un **cas** autonome (`B05-F3`) et refuse toute clé inconnue.

### Un besoin

| Champ | Rôle |
|---|---|
| `id`, `libelle` | `B05`, « Savoir si c'est le moment pour une culture » |
| `categorie` | `conseil`, `ecriture`, `correction`, `lecture`, `aide` |
| `jeu_de_donnees` | `neuf` ou `rempli` |
| `culture_type` | `vegetatif`, `reproducteur_pleine_terre`, `reproducteur_plants` ou `aucune` |
| `couvre` | pour un reproducteur semé en pleine terre : `semis_initial`, `premiere_recolte`, `nieme_recolte`, `fin_de_vie` |
| `fiche` | ce que le jardinier sait et répond quand le compagnon lui pose une question : `culture`, `variete`, `parcelle`, `quantite`, `unite`, `date`, plus des faits libres (`symptome`, `cause`, `contexte`). Une valeur absente de la fiche n'est **jamais** donnée |
| `attendus` | voir ci-dessous |
| `formulations` | la liste des cas |

### Une formulation

| Champ | Rôle |
|---|---|
| `genre` | `directe`, `familiere`, `incomplete`, `faute`, `deux_temps`, `culture_absente`, `reel` |
| `ouverture` | la première phrase du jardinier |
| `suite` | phrases écrites d'avance, jouées après l'ouverture (« oui », « la planche sud », « demain ») ; ensuite, le jardinier simulé répond depuis la fiche |
| `simule` | `false` : le dialogue est rejoué tel qu'écrit, sans jardinier simulé (dialogue réel) ; vrai par défaut |
| `tours_max` | nombre de tours du jardinier au plus (4 par défaut) |
| `renouvelable` | vrai : le cas est tenu à part des exemples de prompt (voir §4) |
| `source` | d'où vient le cas (rapport, corpus de terrain) |
| `fiche`, `attendus` | surcharges de celles du besoin ; `couverture_absente` est un raccourci d'attendu |
| `attendus_tours` | attendus d'un tour précis (`{"1": {…}}`), par exemple le texte attendu au tour 1 |

### Les attendus

| Champ | Contrôle |
|---|---|
| `bonne_reponse` | ce qu'est une bonne réponse ou une bonne proposition (lu par le juge) |
| `ne_jamais_redemander` | valeurs de la fiche qu'on ne demande plus une fois dites (`culture`, `parcelle`, `quantite`, `date`…) — par le code |
| `ecritures_interdites` | types de geste interdits (`perte`, `recolte`…), ou `["*"]` : aucune écriture — par le code |
| `passages_hors_culture_interdits` | aucun passage d'une autre culture montré comme réponse — par le code |
| `cultures_admises` | cultures autres que la fiche qu'une bonne réponse peut citer (`["*"]` : que semer ce mois-ci…) |
| `couverture_absente` | la culture n'a pas de fiche agronomique : la réponse doit le dire au jardinier |
| `valeur_par_defaut` | `permise` ou `aucune`, voir §3 |
| `textes_attendus` | groupes d'alternatives : chaque groupe doit être couvert par une expression du texte lu |
| `textes_interdits` | expressions qu'aucun texte lu ne doit contenir (« perte de stock » pour une récolte) |
| `outils_attendus` | groupes d'outils : chaque groupe voit au moins un de ses outils appelé (`["meteo", "voir_meteo"]`) ; `lire:parcelles` = l'outil `lire` avec `quoi=parcelles`. Noté à part : « données lues » (informatif) — par le code |
| `parcelle_requise` | types de geste jamais proposés sans parcelle (`["plantation"]`) : le compagnon la demande. Manquement = critère « Écriture sûre » — par le code |

**Chiffres sourcés (tous les cas).** Un chiffre avec unité (« 5 °C », « 10 cm », « 7 à 10 jours ») vient d'un résultat
d'outil ou d'une phrase du jardinier ; sinon le critère « Rien d'inventé » tombe. Quand un outil appelé n'a pas laissé
son résultat dans la trace (ou l'a laissé tronqué), le chiffre est compté « indéterminé » et ne fait pas échouer le cas.
Source : références humaines du 18/11/2026 (`docs/EPIC 20 - COMPAGNON CLIENT DES CAPACITES/REFERENCE_HUMAINE_B01.md`).

**Attendus datés.** Les attendus de saison (B01, B04, B05, B06) valent pour une mesure jouée en novembre, en zone
océanique. Le test miroir (même phrase en mai : autre réponse) attend une capacité qui reçoit la date (US-339) : la
chaîne actuelle lit l'horloge réelle.

## 3. Valeur par défaut, relance, valeur inventée

Trois choses se ressemblent et s'opposent (CA7). Les attendus et les contrôles les distinguent :

| | Exemple | Verdict | Qui le contrôle |
|---|---|---|---|
| **Proposer une valeur par défaut** que le jardinier accepte | « 10 plants, ça te va ? » dans le texte | **Permis** (`valeur_par_defaut: permise`) | rien à contrôler |
| **Reposer** à chaque tour la même question restée sans réponse | « Combien de plants ? » au tour 3, au tour 4, au tour 5 | **Fautif** (défaut relevé sur Claude + MCP le 14/11) | le code, compté à part : `questions_repetees` |
| Mettre une valeur **non dite** dans une proposition d'écriture | `proposer_geste(quantite=10)` alors que « 10 » n'a pas été dit ni accepté | **Interdit** : critère « Rien d'inventé », 100 % | le code |

Une valeur avancée par le compagnon puis acceptée d'un « oui » est dite ; la même valeur mise dans la proposition avant cet
accord est inventée.

## 4. Renouvellement

Un tiers des cas au moins est `renouvelable`. Ces cas servent à **mesurer**, jamais à **régler** :

* aucune de leurs phrases ne figure dans un exemple de prompt (agent actuel, boucle à capacités, descriptions du catalogue et du
  registre). Le contrôle est automatique : `tools/jeu_evaluation/jeu.py::controler_renouvelables`, lancé par le lanceur avant
  tout passage et par `tests/test_us336_jeu_evaluation.py` ;
* un exemple de prompt qui reprend une phrase d'un cas renouvelable (au moins deux mots) fait échouer ce contrôle : on change
  l'exemple, jamais le cas ;
* à chaque mesure d'un lot, **un tiers des cas renouvelables est remplacé** par de nouvelles formulations du même besoin
  (même fiche, mêmes attendus), de sorte que le jeu ne devienne pas lui-même la cible du réglage (risque du §8 de
  l'architecture). Les cas retirés rejoignent les cas non renouvelables, qui peuvent, eux, servir d'exemples.

## 5. Les quatre configurations de référence du 14/11

Le jeu les décrit (clé `configurations`) avec leurs résultats du 14/11 comme premiers points. Le lanceur les rejoue sur le
**même potager** (`--moteur actuel`, `capacites`, `claude_mcp`).

| # | Configuration | Moteur du lanceur | Verdict de saison au tour 1 | Intention gardée au tour 7 | Jetons d'entrée sur 7 tours |
|---|---|---|---|---|---|
| A | Small 4, chaîne actuelle | `actuel` | non | non (perdue au tour 2) | 108 894 (61 % en cache) |
| B | Large 3, chaîne actuelle | `actuel` avec `--modele mistral/mistral-large-2512` | non | non | ≈ 158 000 |
| C | Small 4 + capacités + historique | `capacites` | non (« indéterminé ») | oui | 51 211 (86 % en cache) |
| D | Claude + MCP | `claude_mcp` | oui | oui | n/a (autre potager le 14/11) |

Limite de la reprise : le prototype de C n'a jamais été versé au dépôt ; le moteur `capacites` le reconstruit d'après le rapport
(les 9 lectures du registre MCP, `proposer_geste` simulé, historique complet, prompt générique d'une quinzaine de lignes), et
son prompt est donc une reconstitution. Voir `docs/domaines/evaluation-compagnon.md`.

## 6. Exemple commenté

```json
{
  "id": "B05",                                   // identifiant du besoin ; ses cas sont B05-F1, B05-F2…
  "libelle": "Savoir si c'est le moment pour une culture",
  "categorie": "conseil",
  "jeu_de_donnees": "neuf",                      // potager neuf : une parcelle, rien en stock
  "culture_type": "vegetatif",
  "fiche": {"culture": "radis", "date": "ce mois-ci"},        // le jardinier simulé ne dit rien d'autre
  "attendus": {
    "bonne_reponse": "Rend un verdict de saison net pour le radis…",   // lu par le juge
    "ne_jamais_redemander": ["culture"],         // une fois « radis » dit, aucune question sur la culture
    "ecritures_interdites": ["*"],               // une question de saison n'écrit rien
    "passages_hors_culture_interdits": true      // aucun passage sur une autre culture
  },
  "formulations": [
    {"genre": "directe", "ouverture": "Est-ce que c'est le moment de semer des radis ?"},
    {"genre": "faute", "ouverture": "est ce que c'est la saison pour les radi ?"},
    {"genre": "deux_temps", "renouvelable": true,    // hors des exemples de prompt
     "ouverture": "c'est le moment pour semer ?", "suite": ["des radis"]},
    {"genre": "culture_absente",                   // surcharge : une culture sans fiche
     "ouverture": "est-ce le moment de semer du cerfeuil tubéreux ?",
     "fiche": {"culture": "cerfeuil tubéreux"}, "couverture_absente": true}
  ]
}
```

## 7. Comment le jeu se contrôle

`python tools/evaluer_compagnon.py --dry-run` refuse de partir si le jeu ne tient pas les critères d'US-336 : 20 besoins au
moins, 5 formulations chacun, le dialogue du 14/11 en cas n° 1, un jeu de données par cas, les écritures d'un reproducteur
semé en pleine terre (semis, première récolte, N-ième récolte, fin de vie, jamais une perte), 3 cas sans fiche, un tiers
renouvelable hors des prompts, les quatre configurations. Les mêmes contrôles sont dans `tests/test_us336_jeu_evaluation.py`.
