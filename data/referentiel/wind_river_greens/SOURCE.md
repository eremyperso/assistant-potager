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

Un **extrait filtré**, pas un dump : les dix cultures du périmètre initial pour
les attributs et les associations, toutes les cultures de `culture_config` retrouvées
dans la source pour le calendrier [US-068]. Les CSV amont pèsent ~6,4 Mo pour 1 972
cultivars ; l'extrait en retient 604, 3 146 arêtes d'association (dix cultures
seulement) et 7 479 lignes de calendrier, soit ~1,6 Mo. Même choix que `wikidata_familles.json`, qui n'est pas
un dump de Wikidata : on versionne ce qu'on utilise, en gardant la recette pour
reconstituer le reste.

| Fichier | Lignes | Origine |
|---|---|---|
| `varieties.csv` | 604 cultivars | `data/varieties.csv` amont, filtré sur `APPARIEMENTS` ∪ `APPARIEMENTS_CALENDRIER` |
| `companion_plants.csv` | 3 146 arêtes | `data/companion_plants.csv` amont, filtré |
| `planting_calendar.csv` | 7 479 lignes (604 cultivars × 13 zones USDA, un cultivar n'en a que 6) | `data/planting_calendar.csv` amont, filtré **par identifiant** — le slug n'y est pas unique [US-068] |

Le calendrier complet a été fourni le 14/09/2026 et contrôlé avant extraction :
SHA-256 `e8c96e67e35853b2ebfd13c6b75999db18f51d6e9ee3139a00bd714fc4491080`,
identique au fichier du tag `v1.0.0`.

## Reconstituer l'extrait

```bash
# 1. Récupérer les CSV complets depuis le tag figé — jamais depuis `main`,
#    que le dépôt amont rafraîchit chaque mois par GitHub Actions.
mkdir -p /tmp/wrg
for f in varieties companion_plants planting_calendar; do
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
| `companion_plants.csv` | ✅ retenue → `cultures_associations`, après curation | 217 arêtes extraites brutes dans `wind_river_associations.json` (fichier séparé, jamais à importer). L'audit du 01/09/2026 y relevait 41 libellés doublonnés, une contradiction masquée, 8 motifs décrivant une autre plante et une auto-association ; `adaptateur_wind_river.curer_associations` [US-163] les traite tous — traduction en français, rattachement à une culture ou une famille de ce référentiel, retrait de ce qui n'a pas sa place. **113 des 217 retenues**, importées dans `wind_river_attributs.json` |
| `usda_zone_min/max` | ⛔ écartée | Décrit la zone où la plante est *pérenne*, pas où on la cultive : les tomates y sont en « zones 10-11 », sauf Roma en « 4-9 ». Faux pour des annuelles |
| `planting_calendar.csv` | ⚠️ retenue sous conditions → fenêtres `semis_pepiniere` / `semis_pleine_terre` / `plantation` / `recolte` [US-068, 14/09/2026 ; plantation le 15/09/2026] | Voir la section dédiée ci-dessous : correspondance de zones déclarée, six règles de rejet. **336 fenêtres sur 32 cultures** (salade comprise, alias de laitue), dont **64 de plantation** lues dans `outdoor_transplant_*` |
| `days_to_germination` | ✅ retenue → durée `levee` [US-068] | Médiane des minima et des maxima sur les cultivars appariés (≥ 3). Écartée pour ce qui ne se sème pas (ail, planté en caïeux) |
| `days_to_harvest` | ✅ retenue → durée `recolte` [US-068], **en pleine terre seulement** | Les catalogues comptent depuis la PLANTATION pour les cultures élevées à l'abri (tomate, poivron) : sans convention déclarée par la source, la durée n'est retenue que si le mode de semis voté est « direct sow » (haricot, carotte) |
| `sowing_method` | ✅ retenue → mode de semis voté, et durée `repiquage` [US-068] | « start indoors N-M weeks » → N×7 à M×7 jours, pour les cultures majoritairement élevées à l'abri. Un mode mixte (« direct sow, or start indoors… ») ne produit aucune durée de récolte |
| profondeur de semis | ⛔ absente | Aucune colonne dans le jeu de données |
| `nutrition.csv` | ⛔ hors périmètre | Hors sujet pour un suivi de potager |

## Le calendrier de semis — ce qu'il vaut, et comment on le lit [US-068]

D'abord retenu comme inutilisable (01/09/2026), puis repris le 14/09/2026 à la
demande du porteur du produit, **avec les réserves suivantes, mesurées sur la
donnée et non supposées**.

### Ce que le fichier est réellement

- **Un gabarit par catégorie, pas une donnée par cultivar.** 10 profils distincts
  pour 91 tomates, 15 pour 110 « lettuce », **un seul** pour 84 aromatiques
  (lavande, persil et coriandre ont le même calendrier). Les semis sont identiques
  dans une catégorie ; la récolte commence après un délai propre au cultivar et
  finit à un mois **constant pour toute la catégorie** (novembre pour les laitues,
  choux, racines et alliacées en zone 7).
- **Printemps seulement.** Aucun semis de fin d'été ni d'automne : la mâche y est
  semée en mars-mai comme une laitue, les poireaux et pommes de terre comme des
  carottes.
- **Des catégories hétérogènes.** `lettuce` contient épinard, mâche, oseille et
  cresson ; `brassica` contient la betterave `detroit-dark-red` et la blette ;
  `root-vegetable` contient poireaux, oignons et pommes de terre.
- **La source se contredit sur l'ail** : `varieties.csv` dit « planted in fall,
  harvest mid-summer », le calendrier le sème en mars-mai et le récolte de
  décembre à novembre.

C'est pourquoi l'appariement ne passe **pas** par les catégories du calendrier,
mais par `APPARIEMENTS_CALENDRIER` sur `varieties.csv` (catégorie + nom, relu,
le particulier avant le général), puis par jointure sur l'identifiant du cultivar.
Les noms scientifiques de la source sont par endroits faux (`golden-beet` y est un
zinnia, `nelson-carrot` un radis) : la catégorie est exigée chaque fois qu'elle
discrimine. `ALIAS_CALENDRIER` donne à « salade » le calendrier de la laitue.

### Couverture de `culture_config` (55 noms)

**Avec calendrier (32)** : tomate, haricot, haricot grimpant, courgette, pâtisson,
potiron, courge, chou, brocoli, chou frisé, carotte, radis, betterave, navet,
concombre, cornichon, poivron, aubergine, melon, pastèque, pois gourmand,
petit pois, poireau, oignon, laitue, salade, basilic, persil, thym, fenouil,
capucine — et menthe, pour sa seule durée de levée.

**Sans calendrier, et pourquoi** — ⛔ plantées et non semées (règle 1) : ail, échalote, pomme de terre, fraise, framboise, menthe (qui garde sa durée de levée) ; ⛔ moins de 3 cultivars : butternut (2), potimarron (1), chou de Bruxelles (1), ciboulette (2), épinard (1), mâche (1), oseille (2), roquette (2), mesclun (2), blette (1), coriandre (1), romarin (1), céleri (2) ; ⛔ absentes de la source : fève, asperge, rhubarbe, épinard perpétuel ; « automobile » n'est pas une culture.

**Avec fenêtre de plantation (16)** [amendement d'US-068, 15/09/2026] : tomate,
poivron, aubergine, chou, brocoli, chou frisé, concombre, melon, pastèque, basilic,
persil, thym, fenouil, capucine — et, plantation seule, menthe et **fraise**
(nouvelle entrée du manifeste : ses fenêtres de semis et de récolte restent
écartées par la règle 1). ⛔ Écartées : cornichon (3 fiches sur 7 seulement
décrivent une mise en place), potiron (1 cultivar sur 15), ail, échalote et
framboise (fiches décrivant une plantation d'automne). ⬜ **Aucune donnée de
plantation dans la source** : haricot, haricot grimpant, courgette, pâtisson,
courge, carotte, radis, betterave, navet, petit pois, pois gourmand, poireau,
oignon, laitue, salade — à compléter au bot ou dans
`calendrier_redaction_interne.json` pour celles qui se plantent.

**Incomplètes, printemps seulement** — leurs propres fiches mentionnent un semis
ou une plantation de fin d'été ou d'automne que le calendrier ignore : brocoli,
chou frisé, chou, radis, betterave, navet, poireau, oignon, laitue, persil.

### Correspondance des zones — une décision, pas une équivalence

| Zone climatique | Zone USDA lue | |
|---|---|---|
| montagnard | 4 | printemps le plus tardif |
| continental | 6 | |
| océanique | 7 | |
| méditerranéen | 8 | printemps le plus précoce |

Une zone USDA mesure le froid hivernal minimal. Lue comme telle, la France
océanique tomberait en 8-9 — le calendrier du Texas et de la Géorgie, tomates
plantées en avril à Rennes. Mais le calendrier source ne se sert de la zone que
pour caler ses mois sur la **date moyenne de dernière gelée** : c'est sur ce
critère seul que la correspondance est choisie, dans l'ordre des printemps.
**À valider par un humain** ; la table vit à un seul endroit,
`adaptateur_wind_river.ZONE_USDA_PAR_ZONE`, et se relit en diff.

### Les six règles de rejet (`adaptateur_wind_river.construire_fenetres`)

1. **Ce qui ne se sème pas ne reçoit aucune fenêtre de semis ni de récolte** — dès que la moitié des fiches décrivent une plantation (caïeux, plants de pomme de terre, bulbes, griffes, boutures). Écarte ail, échalote, pomme de terre, fraise, framboise, menthe. *Révisée le 15/09/2026* : leur **plantation** est lue, sauf si une de leurs fiches décrit une plantation d'automne — le gabarit de printemps est alors contredit (ail, échalote, framboise).
2. **Jointure par identifiant ET catégorie** — `black-beauty` est à la fois une aubergine, une courgette et un rosier.
3. **Une fenêtre à cheval sur l'année est rejetée** — dans ce fichier, c'est l'artefact d'un début de récolte calculé au-delà de la fin de saison fixe.
4. **Une phase n'est retenue que si ≥ 80 % des cultivars la portent**, et au moins 3 cultivars par culture — écarte les treize cultures à base trop faible.
5. **Médiane basse des débuts et des fins** — un mois réellement observé, jamais une moyenne.
6. **Un semis que les fiches de la source ne décrivent pas est écarté** — au moins la moitié des fiches doivent décrire ce mode (mixte compris). Écarte la pépinière du cornichon et du fenouil : le gabarit de catégorie les y met, leurs fiches disent « direct sow ». *Transposée le 15/09/2026* : une plantation exige que la moitié des fiches décrivent une mise en place (abri, mixte ou plantée) — écarte la plantation du cornichon.

Le compte rendu de l'adaptateur **signale sans corriger** une plantation qui ne s'enchaîne pas avec le semis en pépinière et le délai de repiquage (`signaler_incoherences`) — aucune sur l'extrait versionné au 15/09/2026.

Ce qui ne franchit pas ces règles reste **vide** : le calendrier affiche une
frise neutre, et le jardinier la complète au bot ou via
`calendrier_redaction_interne.json` (dont les valeurs, sur une case déjà écrite
par cette source, sont préservées et non écrasées).

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
