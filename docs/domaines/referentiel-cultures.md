# Référentiel des cultures — US-166, US-161, US-163, US-162, US-174

## Import du référentiel structuré + rapport de couverture [US-166]

Hors ligne (aucun appel réseau), idempotent, rejouable.

```bash
python tools/importer_referentiel.py data/referentiel/wikidata_familles.json
python tools/importer_referentiel.py data/referentiel/wikidata_familles.json --dry-run
python tools/importer_referentiel.py --rapport-seul        # rapport sans rien importer
python tools/importer_referentiel.py --derive-de wikidata  # que retirer avec cette source ?
python tools/importer_referentiel.py --lister-sources      # registre : licence + attribution
```

## Attributs agronomiques de conduite [US-161]

Le gabarit est livré VIDE et se remplit à la main : aucun chiffre agronomique
n'est produit par un modèle de langage. Une valeur `null` n'écrit rien.

```bash
python tools/importer_referentiel.py data/referentiel/attributs_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/attributs_redaction_interne.json
```

Source Wind River Greens (CC BY 4.0) — attribution obligatoire à l'affichage.
L'adaptateur produit un manifeste ; l'import le joue. Aucun appel réseau.

```bash
python tools/adapter_wind_river.py                    # CSV versionnés → manifeste
# Écrit aussi wind_river_associations.json — extraction BRUTE pour US-163,
# à NE PAS passer à l'import : elle n'est pas révisée et ne s'importe pas.
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
```

Provenance, version figée et périmètre : `data/referentiel/wind_river_greens/SOURCE.md`.

Correction depuis le bot — prime sur tout rejeu de l'import :

```
/culture attributs <culture>
/culture exposition <culture> <plein soleil|mi-ombre|ombre>
/culture eau <culture> <faible|moyen|élevé>
/culture profondeur <culture> <cm>
/culture rusticite <culture> <°C>
```

## Associations de cultures et rotation calculable [US-163]

La saisie au bot reste le chemin premier (option A sur la licence — zéro
CC-BY-SA dans le socle). Amendement du 02/09/2026 : une source déjà au socle
en CC BY 4.0 (wind_river_greens, US-161) peut aussi alimenter la table après
curation humaine (traduction, périmètre, doublons) — jamais brute.

```
/association lister <culture>
/association saisir <cultureA> <cultureB> <favorable|defavorable|neutre> <etabli|traditionnel> <motif>
```

Import (même commande que les attributs de conduite — un seul manifeste) :

```bash
python tools/adapter_wind_river.py                    # régénère le manifeste, associations incluses
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json --dry-run
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
```

Rotation : un conflit se calcule (evenements × culture_config × familles_botaniques),
il ne se rédige pas — consultation seule ici, l'alerte proactive est US-167.

```
/rotation <parcelle> <culture>
```

CA12 : temps de réponse à VÉRIFIER sur la production avant tout câblage
automatique (US-167) — jamais supposé sous prétexte que les index existent.

```bash
python tools/mesurer_rotation.py <parcelle_id> <culture>
```

## Bioagresseurs et relation culture × bioagresseur [US-162]

« Qu'est-ce qui attaque mes poireaux » est une REQUÊTE, à zéro jeton — pas une
recherche de similarité. Deux tables : une identité (`bioagresseur`) et une arête
(`culture_bioagresseur`). Aucune colonne de produit, de dosage ni de description :
l'absence de colonne est la garantie qu'aucune prescription ne peut être servie.

```bash
psql -d potager -f migrations/migration_v43.sql
```

```
/bioagresseur lister <culture>
/bioagresseur declarer <champignon|insecte|mollusque|nematode|bacterie|virus|abiotique|carence> <nom>
/bioagresseur rattacher <culture> <courant|occasionnel|rare> <bioagresseur>
/bioagresseur orphelins        # identités connues rattachées à aucune culture
```

Une saisie au bot est TOUJOURS locale au potager et n'est jamais promue au
partagé : la promotion est une décision humaine.

Import — même commande et même manifeste que les attributs et les associations,
deux blocs supplémentaires (`bioagresseurs` puis `cultures_bioagresseurs`) :

```bash
python tools/importer_referentiel.py data/referentiel/bioagresseurs_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/bioagresseurs_redaction_interne.json
```

Le gabarit est livré VIDE et se remplit à la main. L'import PUBLIE le taux
d'appariement des libellés de culture (CA8) : sous ~70 %, la correspondance
manuelle sur les dix cultures du périmètre devient le mode nominal — la décision
se prend sur la mesure, pas sur l'intention.

Un rapprochement par nom vernaculaire seul (« laitue » pour « salade », déclaré
par `culture_en_base`) n'est JAMAIS appliqué sans `"revue_humaine": true` dans
le manifeste — un drapeau relu en diff git, pas un seuil de similarité (CA9).

Codes EPPO : conditions d'utilisation de data.eppo.int LUES et consignées dans
`data/referentiel/eppo/SOURCE.md` — elles autorisent la reprise en base et l'usage
commercial, contre citation d'EPPO ET de la date du dernier téléchargement.

## Bioagresseurs dans la fiche de culture [US-174]

`/fiche <culture>` porte une rubrique « À surveiller » — au plus
`app.services.fiche_culture.LIMITE_BIOAGRESSEURS` lignes, les plus fréquents
d'abord, le reste compté et renvoyé vers `/bioagresseur lister`.

⚠️ `generer_fiche_courte(db, culture, potager_id=...)` : la fiche est devenue
CONSCIENTE DU POTAGER. Ce paramètre ne scope QUE les bioagresseurs — famille,
délai de retour, attributs de conduite et description restent partagés.
