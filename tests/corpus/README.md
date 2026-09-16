# Corpus de mesure du parseur déterministe (US-094)

Deux fichiers, versionnés pour que la mesure du CA5 et le test différentiel du
CA6 soient **rejouables à l'identique**, sans base de production ni appel au
modèle.

## `us094_saisies_reelles.csv`

Saisies **réelles** extraites de `evenements.texte_original`, potager de
production rechargé en développement le 28/08/2026. C'est une exigence
explicite du CA5 : *« construire la grammaire sur des phrases imaginées
produirait une couverture flatteuse et fausse »*.

- **213 phrases distinctes**, 223 lignes (une phrase peut avoir produit
  plusieurs évènements — récolte pesée *et* dénombrée, par exemple).
- Les 96 bulletins `[AUTO-METEO]` sont exclus : ce sont des écritures machine,
  jamais des saisies (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §8.6).
- `texte` est le message **tel qu'il a été dicté**, tronqué avant la première
  trace `[CORR …]` : ces traces ont été ajoutées après coup et ne faisaient
  pas partie de l'entrée du parseur.

| Colonne | Sens |
|---|---|
| `texte` | le message dicté |
| `jour_saisie` | date de l'évènement — sert d'« aujourd'hui » pour rejouer les ancrages relatifs de façon déterministe |
| `corrigee` | `1` si le jardinier a corrigé cette ligne après coup |
| `action` … `nb_graines_semees` | les champs **réellement enregistrés** par le chemin modèle |

### Pourquoi `corrigee` change tout pour le CA6

Sur une ligne corrigée, la valeur en base n'est plus celle produite par le
modèle mais celle saisie par le jardinier. La comparer au parseur déterministe
ne mesurerait pas un écart de parsing. Ces lignes restent dans l'assiette de
**couverture** (CA5) et sortent de l'assiette de **comparaison** (CA6).

## `us094_catalogue.csv`

Cultures, variétés et parcelles du même potager. Indispensable : le parseur
refuse par construction toute culture ou parcelle inconnue (CA4), donc une base
de test vide ne reconnaîtrait **rien** et la mesure vaudrait zéro.

## Rejouer l'extraction

Le corpus se régénère depuis une base rechargée avec les données de production
(`tools/extraction_corpus_rejeu.sql` pour le dump). Le régénérer déplace la
mesure de référence : à faire délibérément, jamais pour faire passer un test.

## `corpus_familles_cultures_parcelles.csv`

Corpus de **mesure de couverture**, pas encore rattaché à une US : il sert à
savoir, à un instant donné, ce que `app.services.reponses_chiffrees` sait déjà
répondre sur le triangle culture ↔ famille botanique ↔ parcelle, et ce qui
retombe encore dans la cascade (étage 2/3, donc un appel modèle).

| Colonne | Sens |
|---|---|
| `question` | la question, phrasée de façon variée (formelle, orale, dictée sans ponctuation, avec fautes) |
| `famille_attendue` | nom de la `Famille` du catalogue qui la sert aujourd'hui — **vide si aucune ne la sert** |
| `categorie` | le type de relation demandée (voir ci-dessous) |

Chaque valeur de `famille_attendue` a été obtenue en exécutant réellement
`reponses_chiffrees.reconnait_famille` contre un potager de test (3 parcelles,
4 familles botaniques, 7 cultures) — jamais devinée depuis la seule lecture des
motifs. Rejouer cette mesure : construire un potager de ce type dans une
session Python (voir `tests/test_us067_famille_botanique.py` pour le gabarit de
fixture) et appeler `reconnait_famille` sur chaque ligne.

Sept catégories :

- `culture_vers_parcelles` — « sur quelles parcelles ai-je des tomates ? »
  → servie par `parcelles_par_culture`.
- `famille_vers_parcelles` — « où sont mes solanacées ? »
  → servie par `parcelles_par_famille`.
- `parcelle_vers_cultures` — « qu'y a-t-il sur la parcelle nord ? », « combien
  de cultures sur la parcelle nord ? » → capturée par `occupation_parcelle`,
  qui **liste** les cultures mais ne rend aucun chiffre agrégé : une question de
  comptage y trouve une réponse approximative (le jardinier compte lui-même les
  lignes), pas une réponse exacte au format attendu.
- `parcelle_vers_familles` — « quelles familles botaniques sur la parcelle
  nord ? », le sens inverse de `parcelles_par_famille`. **Non couvert** : la
  question retombe elle aussi sur `occupation_parcelle` (elle nomme une
  parcelle), qui répond par une liste de cultures et non de familles — une
  réponse qui a l'air pertinente mais ne dit pas ce qui a été demandé.
- `comptage_cultures_par_famille` — « combien de cultures ai-je dans la famille
  des solanacées ? » → **aucune famille du catalogue ne la sert** ; aucun motif
  ne déclenche sur le mot « famille » seul en dehors d'une famille botanique
  déjà nommément résolue par `parcelles_par_famille`.
- `comptage_global` — « combien de familles botaniques différentes dans mon
  potager ? », « combien de cultures différentes ai-je au total ? »
  → **non couvert**, aucun agrégat de ce type au catalogue.
- `identite_famille_culture` — « quelle est la famille de la tomate ? »
  → **non couvert** par `reponses_chiffrees` (question d'identité, pas de
  chiffre) ; c'est la fiche `/fiche <culture>` ou le socle de connaissance qui
  porte ce type de réponse, pas le catalogue SQL.

Ce fichier n'est consommé par aucun test aujourd'hui — il documente une mesure
de couverture. Il se rattache au même patron que
`tests/corpus/us141_questions_memoire.csv` (`question,famille_attendue`) et
peut être parcouru par un test `@pytest.mark.parametrize` du même type
(`rc.reconnait_famille(...) == (famille_attendue or None)`) le jour où une US
vient combler tout ou partie de ces lacunes.
