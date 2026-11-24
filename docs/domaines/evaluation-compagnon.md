# Évaluation du compagnon (jeu, lanceur, juge, rapport)

Lot 0 de `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_COMPAGNON_CAPACITES.md` (§7) : chaque lot de la nouvelle architecture
s'accepte ou se refuse sur le **même jeu**, avec la chaîne actuelle comme témoin. Complète `tools/evaluer_dialogues.py`
(US-256, cascade en plusieurs tours, sans jardinier simulé) et `tests_conv/` (US-288, Telegram réel).

## Pièces

| Pièce | Rôle |
|---|---|
| `tests/corpus/jeu_evaluation_compagnon.json` | le jeu : 24 besoins × 5 à 7 formulations (134 cas), deux jeux de données, les quatre configurations du 14/11. Format : `docs/EPIC - AGENT INTERPRETEUR/JEU_EVALUATION_COMPAGNON.md` |
| `tools/jeu_evaluation/jeu.py` | chargeur strict (toute clé inconnue est refusée), `controler_exigences` (US-336), `controler_renouvelables` |
| `tools/jeu_evaluation/utilisateur.py` | le jardinier simulé : répond depuis la fiche de besoin, `verifier_reponse` refuse tout chiffre hors fiche |
| `tools/jeu_evaluation/controles.py` | les critères à 100 % et les attendus textuels, par le code, sans modèle |
| `tools/jeu_evaluation/juge.py` | « utile » et « aboutit » par un modèle plus fort, grille écrite ; échantillon à relire |
| `tools/jeu_evaluation/moteurs.py` | `actuel`, `capacites` (prototype C, référence de G0), `claude_mcp`, `boucle` (la boucle de production d'US-342 et son fil, US-343) ; `RegistreMesure` (lectures annulées, écritures simulées) |
| `tools/jeu_evaluation/campagne.py` | un dialogue, un passage, `Mesure` (ce que lit le rapport), écriture des traces |
| `tools/jeu_evaluation/rapport.py` | critère par critère, dispersion, comparaison avant / après, régressions bloquantes |
| `tools/evaluer_compagnon.py` | le lanceur en ligne de commande |
| `tools/creer_potager_test_neuf.py` | le potager neuf du jeu (rejouable, refusé hors base de test) |

## Décisions

* **Le jardinier simulé est du code, pas un modèle.** Il compose ses réponses de morceaux de la fiche ; aucune quantité ne peut
  sortir de nulle part, et la dispersion mesurée vient du compagnon seul.
* **Un critère à 100 % ne passe jamais par le juge** : intention gardée, rien d'inventé, écriture sûre, hors-sujet. Le juge ne note
  que « utile au premier tour » et « aboutit ».
* **Une valeur « dite »** est une valeur écrite par le jardinier (avec tolérance au pluriel et à la faute de frappe) ou avancée par le
  compagnon puis acceptée d'un « oui ». Une valeur par défaut dans le TEXTE est permise ; dans une PROPOSITION d'écriture, non dite,
  elle est inventée. Une parcelle lue dans le plan n'est pas inventée.
* **Régression bloquante** : un cas qui tenait sur le moteur témoin et qui, sur le moteur mesuré, échoue sur un critère à 100 %.
  Un échec déjà présent chez le témoin reste bloquant (« déjà en échec avant ») : §7.3, un lot qui dégrade un critère à 100 % ne passe pas.
* **Chaque cas est joué au moins 3 fois par moteur** ; un critère à 100 % doit tenir sur tous les passages, et le rapport donne la
  dispersion par passage.
* **Rien n'est écrit dans le potager** : les lectures du registre MCP s'exécutent dans une session dont `commit` est remplacé par
  `rollback` ; `proposer_geste` est simulé au schéma du registre ; `confirmer_proposition` ne note que l'exécution qui aurait eu
  lieu. Seules les lignes `conso_tokens` de la passerelle sont créées, avec `MISTRAL_API_KEY_MESURE`.
* **Aucun appel sans accord** : le lanceur annonce le volume d'appels, les jetons et le coût estimé, et ne part qu'avec
  `--accord <volume annoncé>` (ou « accord » tapé à l'invite d'un terminal). `--simule` joue sans modèle : le rapport porte alors
  « SIMULATION — CE N'EST PAS UNE MESURE » et la ligne de base n'est jamais versée.
* **Le moteur `capacites` est une reconstitution du prototype du 14/11** (configuration C) : le prototype d'environ 150 lignes n'a
  jamais été versé au dépôt, et son prompt n'a pas été conservé. Le moteur reprend la description du rapport (9 lectures du registre,
  `proposer_geste` simulé, historique complet avec résultats d'outils, `tool_choice="auto"`, 6 étapes au plus, prompt générique d'une
  quinzaine de lignes sans mot de scénario). Sa première mesure fera foi, pas la ressemblance avec le prototype.
* **Le moteur `boucle` est le code de production** (US-342) : `boucle.jouer_tour`, `fil.construire`, prompt et outils de la
  boucle, type d'appel `compagnon` (le lanceur y pose `--modele`). Seuls les bords changent : `RegistreMesure(noms=…)` (lectures
  annulées, `proposer_geste` simulé, toute autre écriture refusée au démarrage), fil en mémoire, horloge d'une minute par tour,
  confirmation au bouton (`mode_confirmation="bouton"`). Le moteur `capacites` reste le prototype C, pour comparer.
* **Le juge est Large 3** (`mistral-large-2512`), à une température faible non nulle : Large 3 refuse le glouton sans `top_p`
  (US-350). Large 4 rend un `content` en liste que la passerelle ne lit pas encore (US-350).
* **La configuration D** (`claude_mcp`) utilise le SDK `anthropic` (non installé par défaut : `pip install anthropic`) et sa propre
  clé, `ANTHROPIC_API_KEY_MESURE`. Elle joue sur le même potager que les autres, avec le même registre de capacités.

## Utilisation

```powershell
$env:APP_ENV="test"; python tools/creer_potager_test_neuf.py                   # une fois : le potager neuf
python tools/evaluer_compagnon.py --dry-run --moteur actuel,capacites          # plan, volume, coût : 0 appel
python tools/evaluer_compagnon.py --simule --moteur capacites --limite 5       # essai sans modèle
python tools/evaluer_compagnon.py --moteur actuel,capacites --potager-neuf N --utilisateur-neuf M --accord <volume>
python tools/evaluer_compagnon.py --comparer avant/resultats_actuel.json apres/resultats_capacites.json
```

Codes de sortie : 0 aucun critère à 100 % en échec, 1 sinon (ou régression bloquante), 2 mesure impossible ou non acceptée.
Les traces et résultats vont dans `rapports_evaluation/<horodatage>/` (hors dépôt) ; seule la ligne de base de la chaîne actuelle,
mesurée avec accord, est versée dans `docs/EPIC - AGENT INTERPRETEUR/` (`--verser-ligne-de-base`).

## Ce qui rend cette fiche fausse

Un nouveau critère dans `rapport.LIBELLES`, un moteur ajouté à `moteurs.MOTEURS`, un changement des seuils du §7.2 de
l'architecture (aujourd'hui « à confirmer »), un prompt qui cite une formulation d'un cas `renouvelable`, un outil du registre MCP
qui devient une écriture (`RegistreMesure` refuse alors de démarrer), l'ajout de `top_p` ou du contenu en liste à la passerelle (US-350).

## Limites connues

* La ligne de base de la chaîne actuelle (CA8 d'US-337) n'est pas mesurée tant que l'accord sur le volume n'est pas donné.
* Les seuils du §7.2 sont à confirmer avec le porteur du produit.
* Les cas du potager rempli supposent le potager 33 (« planche principal », tomates) ; sans lui, les attendus de lecture se jugent sur
  ce que le potager contient, pas sur des valeurs figées.
* Le jardinier simulé ne reproduit pas l'imprévu d'un vrai jardinier ; il couvre les formulations écrites et leurs réponses de fiche.
