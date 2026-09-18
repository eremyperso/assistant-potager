# Calendrier cultural — US-068, US-069, US-070, US-177, US-178

## Calendrier cultural et zone climatique [US-068]

Quand semer (en pépinière / en pleine terre), quand récolter, et dans combien
de jours la culture lève ou se récolte — lu à ZÉRO jeton, corrigeable au bot.

```bash
psql -d potager -f migrations/migration_v46.sql
```

```
/calendrier <culture>
/calendrier zone [oceanique|continental|mediterraneen|montagnard|auto]
/calendrier fenetre <culture> [itinéraire] <pepiniere|pleine_terre|plantation|recolte> <mars-mai|aucune>
/calendrier duree <culture> [itinéraire] <levee|recolte|repiquage> <10|70-90|vivace|aucune>
GET /cultures/{culture}/calendrier   (forme de lecture pour US-060 / US-070 / Lot E)
```

Tout est aussi DICTABLE (US-172) : « quand semer les tomates ? », « passe mon
potager en zone méditerranéenne », « délai de levée des carottes : 14 à 21 jours ».
« Plantation » se tranche par la VALEUR (CA29) : des mois corrigent la fenêtre
(« plantation des poireaux : juin-juillet »), des jours la durée `repiquage`
(« délai avant plantation des tomates : 42 à 56 jours ») ; sinon rien n'est deviné.

⚠️ Frontière avec US-096 portée par la règle `calendrier_quand` de
`interpreteur_commandes` : verbe à l'INFINITIF exigé — « quand ai-je semé les
tomates ? » reste une question sur le journal du potager.

Le modèle — `app/services/calendrier_cultural.py` (seul point de lecture/écriture) :

| Table | Rôle |
|---|---|
| `itineraire_cultural` | une CONDUITE (« standard », « culture d'hiver »), jamais une variété |
| `fenetre_culturale` | une par (itinéraire, zone, phase), au mois ; absente = vide |
| `duree_culturale` | une par (itinéraire, étape), en jours ou mention libre, COMMUNE à toutes les zones (physiologie, pas latitude) |

⚠️ Trois décisions à ne pas rouvrir sans rouvrir l'US :

- **ZONE** : `potagers.zone_climatique` ne porte que le CHOIX du jardinier. Sans
  choix, la zone se DÉDUIT de la localisation À LA LECTURE
  (`zone_depuis_localisation` : règle grossière, déclarée), puis
  `CALENDRIER_ZONE_DEFAUT` (`app/config.py`, `oceanique`). Aucun backfill SQL
  de la zone : une seconde règle divergerait.
  [US-193] La règle lit aussi `potagers.altitude` (migration v48) : au-delà de
  `CALENDRIER_SEUIL_MONTAGNARD_M` (700) → montagnard ; sinon sud de 44,7° N et
  est de 2,8° E → méditerranéen ; est de 3,8° E → continental ; sinon
  océanique. Limites calées sur le tableau de villes d'US-193 / CA5
  (`tests/test_us193_zone_altitude.py`), en penchant vers le plus froid. Sans
  altitude, jamais « montagnard ». L'altitude arrive avec la ville
  (`elevation` d'Open-Meteo dans `VilleSearch.jsx`) et change AVEC les
  coordonnées (`modifier_potager`) ; les potagers déjà localisés la reçoivent
  par `tools/renseigner_altitude_potagers.py`, lancé après les migrations.
- **CORRECTION** : TOUJOURS locale au potager (CA11). La première correction COPIE
  l'itinéraire partagé en itinéraire personnalisé (`potager_id` non nul) qui
  le remplace pour ce potager. `culture_config.nom` étant UNIQUE, la
  convention « fiche personnalisée » s'applique sur les tables du calendrier,
  pas sur `culture_config`. L'import n'écrit que du PARTAGÉ : il ne peut pas
  écraser une correction, par construction (CA9).
- **HONNÊTETÉ** : aucune fenêtre empruntée à une zone voisine, aucune durée
  moyenne, jamais une date calculée (CA4, CA13). Sans donnée : frise vide,
  durée « — ».

### Pré-remplissage (CA9) — le calendrier du commerce est une œuvre protégée

- **DURÉES** : Wind River Greens (CC BY 4.0), bloc `cultures_calendriers` du
  manifeste existant — levée ; récolte en pleine terre SEULEMENT
  (`days_to_harvest` compte depuis la plantation pour ce qui est élevé à l'abri) ;
  repiquage depuis « start indoors N-M weeks ».
- **FENÊTRES** : même source, même bloc, lues dans `planting_calendar.csv`
  (identique au tag v1.0.0, extrait aux cultivars du périmètre).
  TOUT `culture_config` retrouvé dans la source (`APPARIEMENTS_CALENDRIER`,
  le particulier avant le général ; `ALIAS_CALENDRIER` : salade = laitue) :
  336 fenêtres (dont 64 de plantation) et 45 durées sur 33 cultures.
  Attributs et associations restent sur les dix d'`APPARIEMENTS`.
  Couverture détaillée et motifs d'exclusion : `wind_river_greens/SOURCE.md`.
- **PLANTATION** (amendement d'US-068 du 15/09/2026) : quatrième phase, mise en
  place DÉFINITIVE, lue dans `outdoor_transplant_*` — JAMAIS déduite
  du semis en pépinière + délai de repiquage, et jamais un indice de
  pépinière pour la proposition de contexte d'US-069. Portée par 16
  cultures (dont la fraise, plantation seule) ; les autres se plantent
  au gabarit de rédaction interne ou au bot, ou se sèment en place.

```bash
python tools/adapter_wind_river.py
python tools/importer_referentiel.py data/referentiel/wind_river_attributs.json
```

⚠️ Deux choses à savoir avant de toucher aux fenêtres :

- La source est en zones USDA. `adaptateur_wind_river.ZONE_USDA_PAR_ZONE`
  (océanique ← 7, continental ← 6, méditerranéen ← 8, montagnard ← 4) est
  une DÉCISION calée sur la date de dernière gelée, pas une équivalence de
  rusticité (qui mettrait la Bretagne au calendrier du Texas). À valider.
- Le calendrier source est un GABARIT PAR CATÉGORIE (10 profils pour 91
  tomates), printemps seulement : aucun semis de fin d'été ni d'automne.
  Six règles de rejet dans `construire_fenetres` — plantation majoritaire
  (ail, échalote, pomme de terre, fraise, framboise, menthe : semis et récolte
  écartés, plantation gardée sauf fiche de plantation d'automne), jointure id +
  catégorie, fenêtre à cheval sur l'année (artefact), phase minoritaire,
  médiane basse, semis contredit par les fiches de la source (pépinière du
  cornichon et du fenouil). `fenetres_incompletes` liste les cultures dont les
  fiches parlent d'un semis d'automne que le calendrier ignore.

Gabarit de rédaction interne, livré VIDE, pour ce que la source ne couvre pas
(aucun chiffre produit par un modèle de langage) — une valeur déjà écrite par
wind_river_greens y est PRÉSERVÉE, jamais écrasée :

```bash
python tools/importer_referentiel.py data/referentiel/calendrier_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/calendrier_redaction_interne.json
```

## Semis en pépinière ou en pleine terre [US-069]

Un semis porte sa FILIÈRE (`evenements.contexte_semis`) : dite dans la phrase
(« en pépinière », « en godets », « en pleine terre », « en place »), sinon
PROPOSÉE au récapitulatif du bot et adoptée par « Confirmer » — un seul geste.

```bash
psql -d potager -f migrations/migration_v47.sql
```

Un seul module — `app/services/contexte_semis.py` :

| Fonction | Rôle |
|---|---|
| `detecter_contexte` | ce qui est DIT, jamais deviné (« sous abri » n'y est pas) |
| `proposer_contexte` | deux indices et deux seulement : parcelle déclarée pépinière, puis un calendrier (US-068) qui ne connaît QU'UNE des deux fenêtres de semis. Sinon : sans contexte |
| `correction_contexte_seule` | « non, c'était en pépinière » se corrige SANS modèle |
| `semis_par_contexte` | trois totaux par culture et saison (`/stats`, `GET /stats`) |
| `fenetre_conseillee` | la fenêtre du référentiel qu'US-070 ancrera |

⚠️ Le contexte ne pilote AUCUN calcul de stock (CA8) : le stock se déduit
toujours de `parcelles.est_pepiniere`. Une parcelle ordinaire n'est pas non plus
un indice de pleine terre — un semis de pépinière est rattaché à une parcelle
comme tout événement.

⚠️ Pas d'interrogatoire (point de vigilance de l'US) : la proposition n'est faite
que pour une saisie d'UN geste ; une dictée multi-gestes s'enregistre sans
contexte non dit, corrigeable ensuite. La clé `contexte_semis` PRÉSENTE et vide
dans un item vaut « sans préciser » : la phrase n'est pas relue derrière ce choix.

## Calendrier recalé sur les événements réels [US-070]

Une culture EN PLACE se lit sur son propre calendrier : levée et première
récolte attendues depuis la date réelle du semis. Lecture seule, zéro jeton.

```
GET /plan/calendriers?culture=…&date_ref=YYYY-MM-DD   bloc `projections`
```

Un seul module — `app/services/recalage_calendrier.py` :

| Fonction | Rôle |
|---|---|
| `construire_series` / `semis_chaine` | séries : semis de la parcelle, ou chaînage plantation → godet → semis |
| `ancrer_serie` | [US-177] D'OÙ part la projection — règle à UN seul endroit : le SEMIS (durée `recolte`) prime toujours ; à défaut seulement, la PLANTATION (durée `plantation_recolte`) |
| `rattacher_recoltes` | plus ancienne série ouverte ; en végétatif la récolte CLÔT la série (CA6, CA10) |
| `projeter_serie` | fourchettes, état, mois de la frise (CA7) |

⚠️ Rien n'est deviné (CA11) : semis sans filière connue, durée `recolte` non
chiffrée, plantation sans `plantation_recolte`, ou culture sans référentiel →
`sans_recalage`, la tuile garde la frise CONSEILLÉE. Un semis dont la durée
manque n'emprunte JAMAIS celle de la plantation (US-177 / CA8). Un semis
chaîné à un godet vaut pépinière (même preuve que v47).

## Durée plantation → première récolte [US-177]

Quatrième étape de `duree_culturale` (`plantation_recolte`), aucune migration
(VARCHAR(20) sans CHECK). Portée par un itinéraire qui SE PLANTE seulement
(`calendrier_cultural._se_plante`) ; pré-remplie depuis `days_to_harvest` de
Wind River là où la source compte depuis la plantation (à l'abri, ou ce qui ne
se sème pas) — JAMAIS par soustraction de `repiquage` à `recolte`.

```
/calendrier duree <culture> plantation-recolte 60-80
« délai entre la plantation et la récolte des tomates : 60 à 80 jours »
```

⚠️ « plantation » SEUL reste l'alias de `repiquage` (semis → mise en place) :
la dictée d'US-177 exige les DEUX bornes, plantation ET récolte.

⚠️ Aucune écriture, aucun calcul de stock touché (CA13) — un test le vérifie.

## Moteur de confiance semis / plantation [US-178]

« Est-ce raisonnable de semer ça, ici, maintenant ? » — 1 à 3 étoiles et les
MOTIFS qui l'expliquent, à zéro jeton. Le module CALCULE et EXPOSE ; il n'affiche
rien (consommateurs : US-179 bot, US-180 écran Plan) et n'écrit rien (CA11).

```
GET /cultures/{culture}/confiance?action=&date=&parcelle_id=&itineraire=
GET /plan/confiances?culture=…&culture=…&action=&date=      (lecture groupée, UNE lecture météo)
```

Un seul module — `app/services/confiance_semis.py` :

| Règle | Ce qu'elle lit | Points |
|---|---|---|
| R1 fenêtre conseillée de la zone | `fenetre_culturale` via `lire_calendrier` | 40 / 20 (mois adjacent) / 0 |
| R2 dernière gelée moyenne de la ZONE | `culture_config.rusticite_min_c` + table déclarée | 20 / 10 / 0 |
| R3 gel annoncé sur la quinzaine | prévisions en cache (US-182) | 20 / 0 |
| R4 nuits douces (7 j) | prévisions en cache (US-182) | 10 / 0 |
| R5 saison restante | durée `recolte` / `plantation_recolte` + fenêtre `recolte` | 10 / 0 |

⚠️ **R5 teste une APPARTENANCE à la saison de récolte, jamais l'antériorité de
sa seule fin** — correctif du 18/09/2026, constaté sur deux potagers réels.
Comparer à la seule borne de fin obligeait, quand ce mois était déjà passé, à
reporter la saison d'un an ; ce report offrait onze mois de marge à la culture la
PLUS hors saison. Le même haricot semé le 19 septembre GAGNAIT la règle en zone
océanique (récolte juillet → août, reportée à l'an prochain) et la PERDAIT en
zone montagnarde (récolte août → octobre, encore ouverte) : plus on était en
retard, plus on marquait. Le report, lui, reste indispensable — un ail planté en
octobre se récolte bien dans la fenêtre « mars → mai » de l'année suivante — et
vit désormais dans `prochaine_saison_de_recolte`, qui rend l'intervalle entier.
Son balayage commence à l'année PRÉCÉDENTE : une fenêtre qui enjambe le 31/12
(« novembre → février ») est encore ouverte en janvier bien qu'ayant commencé
l'année d'avant. Le motif perdu distingue « après la fin de saison » de « saison
de récolte déjà passée », qui ne se corrigent pas de la même façon.

⚠️ Quatre décisions à ne pas rouvrir sans rouvrir l'US :

- **UN SEUL ENDROIT** (CA3) : barèmes, seuils d'étoiles (≥ 75 ★★★, ≥ 45 ★★),
  `DERNIERE_GELEE_MOYENNE_PAR_ZONE`, `SEUIL_NUITS_DOUCES_C`, `SEUIL_GELIVITE_C`
  vivent dans le bloc « Barème » du module, et nulle part ailleurs. Ce sont des
  **décisions produit**, comme `ZONE_USDA_PAR_ZONE` — pas des mesures. La table
  des dernières gelées (méditerranéen 15-03, océanique 05-04, continental 25-04,
  montagnard 10-05) est celle que le plan d'épic 8 § 12 a fait **valider par un
  humain le 17/09/2026** : la changer, c'est rouvrir l'arbitrage, et un test la
  compare valeur par valeur. Les deux seuils 🧪 restent des hypothèses.
- **MUET PLUTÔT QUE MENTEUR** (CA5) : une donnée absente rend un motif
  `indetermine` à 0 point et ABAISSE `score_max_atteignable` — sans météo le
  plafond est 70, la troisième étoile est hors d'atteinte et un avertissement le
  dit. Aucune valeur par défaut, aucune compensation.
- **PAS DE SCORE SANS R1** : la phase demandée sans fenêtre pour la zone rend un
  tiret (`etoiles: null`), jamais la fenêtre d'une autre phase ni d'une autre
  zone (CA4). La priorité des corrections locales est celle de `lire_calendrier`,
  sans second mécanisme.
- **R2 ET R3 RESTENT DEUX RÈGLES** : climatologie de la zone d'un côté, météo de
  la quinzaine de l'autre. Les fusionner perdrait le motif « trop tôt pour ta
  zone » quand la quinzaine est douce.

Le résultat porte aussi la **fourchette de récolte attendue** si l'action a lieu à
cette date (`recolte_attendue`, bornes ou rien) : le gabarit de réponse du bot
(`docs/EPIC 8-confiance-calendrier/GABARIT_REPONSE_CONFIANCE_BOT.md`) interdit à
US-179 de recalculer quoi que ce soit ou de reformuler un motif — les libellés
rendus ici sont donc ceux du gabarit, à la lettre, et un test les fige.

⚠️ Une parcelle déclarée pépinière IMPOSE le semis en pépinière quand la filière
n'est pas dite (CA8) ; une plantation qu'on y demande n'est pas corrigée en
douce — elle porte un avertissement. Un semis en pépinière tient R2, R3 et R4
pour acquises : la pépinière non chauffée de février attend l'abri d'US-181.


## « Je peux semer ? » au bot [US-179]

Le moteur d'US-178 mis dans la main du jardinier, à zéro jeton. Trois fichiers,
et trois seulement :

| Fichier | Rôle |
|---|---|
| `interpreteur_commandes.py` (bloc « Confiance ») | quatre règles reconnaissent la question et la traduisent en `/confiance` |
| `menu_commandes.FORMES_DICTABLES` | la commande, ses quatre arguments, `confirmation=False` |
| `app/bot/commandes_confiance.py` | le handler, le gabarit de réponse, les boutons |

Forme : `/confiance <culture> <semis|pepiniere|pleine_terre|plantation> [date] [parcelle]`.

⚠️ Cinq décisions à ne pas rouvrir sans rouvrir l'US :

- **L'ACTION EST LE PIVOT** de `ctx.args`, et c'est pour cela qu'elle est
  obligatoire : « pomme de terre » et « planche nord » comptent chacune plusieurs
  mots, et sans un jeton connu entre les deux, aucune lecture positionnelle ne
  dit où finit l'une. Les quatre règles la renseignent toujours — elle vient du
  verbe, qu'aucune ne rend facultatif.
- **AUCUNE RÈGLE NE RECONNAÎT UN VERBE DE SEMIS NU.** Il faut une MODALITÉ
  (« je peux », « c'est le moment », « bonne idée », « ou j'attends ? »). Sans
  cette exigence, la règle capterait la SAISIE, qui est le geste le plus fréquent
  du bot : « je sème les carottes ce week-end » reste une déclaration, seule
  l'alternative finale en fait une question. Le corpus porte les deux formes
  côte à côte pour que ça ne puisse pas se perdre.
- **LE GARDE 1 D'US-172 S'EFFACE ICI, ET ICI SEULEMENT** : « peut-on semer des
  haricots ? » s'ouvre comme une demande de procédure et n'en est pas une.
  `_est_question_d_opportunite` est assemblé des mêmes briques que les règles,
  pour que le garde et elles ne puissent pas diverger. « comment semer des
  haricots ? », sans modalité, reste une demande de savoir.
- **ARBITRAGE CONFIANCE ⟩ ROTATION** (17/09/2026, `_ARBITRAGES`) : « je peux
  semer des tomates sur la planche nord ? » est à la fois une question de
  rotation (US-163) et de saison. Les deux lectures sont justes ; demander
  laquelle ajouterait un geste à la question la plus fréquente de l'application.
  La confiance répond ; la rotation garde `/rotation` et sa formulation explicite
  (« vérifie la rotation des tomates sur la planche nord »). La table est ÉCRITE,
  jamais déduite de l'ordre de déclaration des règles.
- **AUCUN NOUVEAU CHEMIN D'ÉCRITURE** : le bouton « Enregistrer » appelle
  `saisie._parse_and_save` avec un item PRÉ-PARSÉ — même contrat que le parseur
  déterministe d'US-094. Donc la confirmation habituelle, les avertissements de
  rotation, la demande de parcelle : tout est celui du flux existant, et aucun
  jeton n'est consommé.

L'état de la question vit dans `etat._CONFIANCE_PENDING` (15 min), jamais dans
`ctx.user_data['mode']` qui capturerait la commande suivante (CA10).

⚠️ **La grammaire de dates a gagné un MODE, pas une seconde grammaire.**
`utils/date_utils.resoudre_ancrage_temporel(..., futur=True)` : jusqu'ici tout
`date_utils` datait le PASSÉ (`_construire` refuse explicitement une date future),
parce qu'il ne servait qu'à rattacher un geste déjà fait. « Samedi » vaut la
dernière occurrence pour « j'ai semé samedi », la prochaine pour « je peux semer
samedi » — aucune lecture ne peut être la bonne partout. Le mode ouvre
« demain », « après-demain », « dans N jours », « dans N semaines », « la semaine
prochaine », « cette semaine », « ce week-end » (le samedi qui vient) et le jour
de semaine seul, et fait basculer d'un an l'année sous-entendue d'une date
absolue. Sans `futur=True`, rien ne change pour les appelants existants.
