# Wind River Greens Plant Database — extrait versionné

> **Attribution obligatoire (CC BY 4.0)**
> Plant variety data from [Wind River Greens Plant Database](https://plants.windrivergreens.com), CC BY 4.0.

| | |
|---|---|
| **Dépôt amont** | https://github.com/bripatch/plant-variety-database |
| **Version figée** | `v1.0.0` (release immuable, publiée le 23/05/2026) |
| **Licence** | CC BY 4.0 — partage, adaptation et usage commercial libres, attribution obligatoire |
| **Titulaire** | Wind River Greens (ferme de microgreens, Milton, Géorgie, États-Unis) |
| **Extrait le** | 01/09/2026 |
| **Code registre** | `wind_river_greens` (`migrations/migration_v40.sql`) |

## Ce que contient ce répertoire

Un **extrait filtré** aux dix cultures du périmètre initial, pas un dump. Les CSV
amont pèsent ~5 Mo pour 1 972 cultivars ; l'extrait en retient 276 et 3 146 arêtes
d'association, soit ~700 Ko. Même choix que `wikidata_familles.json`, qui n'est pas
un dump de Wikidata : on versionne ce qu'on utilise, en gardant la recette pour
reconstituer le reste.

| Fichier | Lignes | Origine |
|---|---|---|
| `varieties.csv` | 276 cultivars | `data/varieties.csv` amont, filtré |
| `companion_plants.csv` | 3 146 arêtes | `data/companion_plants.csv` amont, filtré |

## Reconstituer l'extrait

```bash
# 1. Récupérer les CSV complets depuis le tag figé — jamais depuis `main`,
#    que le dépôt amont rafraîchit chaque mois par GitHub Actions.
mkdir -p /tmp/wrg
for f in varieties companion_plants; do
  curl -sL "https://raw.githubusercontent.com/bripatch/plant-variety-database/v1.0.0/data/$f.csv" \
       -o "/tmp/wrg/$f.csv"
done

# 2. Filtrer vers cet extrait
python tools/adapter_wind_river.py --extraire /tmp/wrg

# 3. Produire le manifeste, puis l'importer
python tools/adapter_wind_river.py
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
```

## Ce qu'on retient de cette source — et ce qu'on écarte

| Donnée amont | Décision | Motif |
|---|---|---|
| `sun_requirement` | ✅ retenue → `exposition` | 29 formulations libres, normalisées par règles ; accord ≥ 88 % sur nos cultures |
| `water_requirement` | ✅ retenue → `besoin_eau` | 579 formulations, dont des quantités en pouces/semaine ramenées à trois catégories |
| `companion_plants.csv` | 🔶 extraite **brute**, non importée | 217 arêtes dans `wind_river_associations.json`, fichier séparé du manifeste. **Non révisée** — l'audit du 01/09/2026 y relève 41 libellés doublonnés, une contradiction masquée, 8 motifs décrivant une autre plante et une auto-association. À relire en US-163 |
| `usda_zone_min/max` | ⛔ écartée | Décrit la zone où la plante est *pérenne*, pas où on la cultive : les tomates y sont en « zones 10-11 », sauf Roma en « 4-9 ». Faux pour des annuelles |
| `planting_calendar.csv` | ⛔ écartée | Mois × zone USDA, dates de gelée nord-américaines. La zone 8 USDA contient Seattle *et* Dallas. Le calendrier français relève d'US-068 |
| profondeur de semis | ⛔ absente | Aucune colonne dans le jeu de données |
| `nutrition.csv` | ⛔ hors périmètre | Hors sujet pour un suivi de potager |

## Réserve à connaître sur la provenance amont

48 % des variétés dérivent de **Johnny's Selected Seeds**, un catalogue commercial ;
91 % de **NC State Extension** (public) et 26 % d'**USDA PLANTS** (domaine public).
Wind River Greens relicencie en CC BY 4.0 des données partiellement extraites d'une
base tierce, et ne donne aucune garantie — le texte CC BY l'énonce explicitement.

Des faits isolés ne sont pas protégeables ; une extraction substantielle et
systématique l'est en droit européen (droit *sui generis* du producteur de base de
données, directive 96/9/CE). Le risque est **faible en pratique** — dix cultures,
deux attributs qualitatifs, données agrégées et transformées — mais il n'est pas nul.

Si cette source devenait litigieuse, tout ce qui en dérive se liste en une requête :

```bash
python tools/importer_referentiel.py --derive-de wind_river_greens
```

et s'efface avec `migrations/rollback_v40.sql`, sans toucher aux valeurs corrigées
au bot, qui portent l'origine `saisie_manuelle`.
