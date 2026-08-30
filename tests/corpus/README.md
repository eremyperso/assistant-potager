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
