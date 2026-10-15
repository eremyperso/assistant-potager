# Pépinière — échéances d'un lot, action suggérée, ordre d'urgence

Fiche de conception de la Pépinière « poste de travail » (épic 12). Elle se lit
avant de toucher `app/services/echeances_lots.py`, au calcul des lots
(`utils/stock.calcul_lots_pepiniere`) ou à la réponse de `GET /pepiniere/lots`.

## Principe

Les échéances, l'action suggérée et le rang d'urgence sont calculés **à un seul
endroit** — `app/services/echeances_lots.py` — en **lecture seule**, à une date de
référence, sans appel au modèle. L'API recopie ; les écrans (US-215 Aujourd'hui,
US-216 fiche du lot, US-218 Calendrier) affichent. Aucun d'eux ne recalcule
quoi que ce soit : une règle écrite deux fois finit par se contredire.

Entrées : la sortie de `calcul_lots_pepiniere` à la même date, les durées du
calendrier cultural (lues **une fois par culture**, jamais par lot), et pour
« à semer » l'évaluation de confiance d'US-178.

## Table des échéances

| Échéance | Règle | Donnée requise |
|---|---|---|
| **Repiquage en godet** | date de semis + délai semis → godet (`ETAPE_SEMIS_GODET`, US-213), en fourchette. Tant que le lot n'a **aucun** plant en godet : *dans N j* avant la fourchette, *à repiquer* dedans, *en retard de N j* après sa fin | délai semis → godet |
| **Mise en terre prévue** | date de semis + délai avant plantation (`ETAPE_REPIQUAGE`, US-068), en fourchette. Pour un lot qui a des plants en godet : *dans N j*, *à faire* (dans la fourchette), *en retard de N j* (après sa fin) | délai avant plantation |
| **Endurcissement** (A11) | compte à rebours de **7 jours** qui finit au début de la mise en terre prévue, « J+n/7 », pour un lot en pépinière **chaude ou de type inconnu**. Pépinière **froide** : « en pépinière froide », pas de compte à rebours. Un lot **déplacé** vers une pépinière froide : compte à rebours depuis le jour du déplacement ; ses 7 jours écoulés, plus rien à compter, le lot reste « en pépinière froide » | type de la pépinière (US-208), dernier déplacement (US-211), mise en terre prévue |
| **Lot dormant** | des graines à lever ou des godets, **aucun geste depuis 60 jours**, mise en terre prévue **dépassée ou inconnue** | date du dernier geste |

Le compteur d'endurcissement est borné : jamais au-delà de « J+7 sur 7 ».
`termine` vaut vrai à J+7 (chaude) ou une fois les 7 jours écoulés après un
déplacement vers le froid.

## Deux décisions produit

Écrites dans **un bloc** en tête du module, corrigeables en un diff, comme le
barème de la confiance (US-178 / CA3). Un test les fige.

| Constante | Valeur | Statut |
|---|---|---|
| `DUREE_ENDURCISSEMENT_JOURS` | 7 jours | hypothèse, arbitrage A11 — à confirmer par le PO |
| `SEUIL_DORMANCE_JOURS` | 60 jours | hypothèse — à confirmer par le PO |

Un « geste » du lot, pour la dormance : son semis, une mise en godet, un
déplacement, une plantation ou une sortie (vente, perte) qui lui est imputée.
L'observation libre sur la parcelle n'en est pas un.

## Action suggérée — une par lot

Évaluée dans cet ordre, la première qui s'applique gagne :

1. **Clôturer** — le lot est dormant ;
2. **Repiquer** — repiquage *à repiquer* ou *en retard* ;
3. **Mettre en terre** — endurcissement en cours ou terminé, ou mise en terre
   prévue atteinte ou dépassée ;
4. **Noter la levée** — des graines en germination, avant la fourchette de
   repiquage, aucune levée notée (le geste est US-212 : tant qu'il n'existe pas,
   `_levee_notee` rend faux et l'action reste proposée) ;
5. aucune.

## Ordre d'urgence

Un seul tri, sur une clé calculée avec les échéances. `rang_urgence` vaut 1 pour
le lot le plus pressant. L'ordre de `lots` dans la réponse, lui, ne change pas.

1. les **retards**, du plus grand au plus petit (repiquage ou mise en terre
   dépassés, le plus grand des deux) ;
2. les **échéances à venir**, de la plus proche à la plus lointaine (0 pour ce
   qui est à faire ou en cours) ;
3. les lots **sans échéance** (un lot épuisé après les lots actifs) ;
4. les lots **dormants**, en dernier.

À égalité : numéro de lot, puis identifiant du lot.

## Sans donnée, pas d'échéance (CA3 / RT2)

Jamais de valeur par défaut. Chaque échéance manquante porte sa `raison`, et
`echeances.raisons` les rassemble :

| Cas | Raison rendue |
|---|---|
| délai semis → godet absent, ou en simple mention | « délai semis → godet non renseigné pour la culture « X » » |
| délai avant plantation absent | « délai avant plantation non renseigné pour la culture « X » » |
| lot de godets sans semis rattaché, ou sans date de semis | « date de semis inconnue » |
| culture inconnue du référentiel | la raison du délai manquant |

Le délai de godet n'est **jamais déduit** de la levée ni du délai avant
plantation. Un lot sans échéance calculable n'est ni en retard ni à endurcir ;
il peut pourtant être dormant, puisque la dormance se lit dans le journal et
accepte une mise en terre « inconnue ».

## Résumé du bandeau

`resume` dans la réponse de `GET /pepiniere/lots` :

| Clé | Contenu |
|---|---|
| `a_repiquer` | `lots`, `plants` — lots *à repiquer* ou *en retard* ; `plants` = graines semées tant que la levée n'est pas notée (US-212) |
| `a_endurcir` | `lots` — endurcissement en cours |
| `prets_pour_le_plan` | `lots`, `plants` (godets disponibles des lots dont la mise en terre prévue est atteinte, dépassée ou inconnue), `rangs_libres_par_parcelle` (US-198, lu par `repartition_rangs`, planches ordinaires seulement ; calculé seulement s'il y a des plants prêts). Aucune surface : la géométrie est reportée |
| `a_semer` | `cultures` (`culture`, `fenetre`), `total` — fenêtre de semis en pépinière de la zone ouverte à la date de référence (**R1 à son maximum**, évaluation d'US-178 : le mois adjacent ne suffit pas) et aucun lot de la culture en cours |

« À semer » présélectionne en SQL les cultures qui ont une fenêtre ce mois-là,
puis évalue ; la météo est lue **une fois** (cache d'US-182), et pas du tout
s'il n'y a aucun candidat.

## Garde-fous

- **Lecture seule** : aucun geste créé, même pour un lot dormant ; aucun stock
  ne change (`tests/test_us214_echeances_lots.py`, CA10).
- **Aucune requête par lot** : le test compare le nombre d'instructions SQL
  pour 3 et 12 lots d'une même culture.
- **Isolation** : lots, calendriers corrigés et rangs sont ceux du potager
  consulté ; une correction locale d'un autre potager n'est jamais lue.
- `type_pepiniere` n'est lu que par ce module pour un calcul (US-208 / CA7 le
  prévoyait) ; `tests/test_us208_pepiniere_chaude_froide.py` en tient la liste.
- Le corpus jardinier (`data/connaissance/doc_app/pepiniere-par-lot.md`) suit
  toute modification de ces règles (US-099 / CA9).

## La fiche du lot et la clôture (US-216)

La fiche (`frontend/src/components/FicheLot.jsx`) **lit** : échéances, action suggérée
et dormance viennent de l'API, rien n'est recalculé côté écran. Ses règles — gestes
selon l'état du lot, quantités proposées, taux, comparaison à la moyenne — vivent dans
`frontend/src/lib/ficheLot.js` (sans React, `npm test`).

- **Une lecture.** Ouverte depuis la liste : aucune lecture de plus. Ouverte par numéro
  ou par l'adresse : `GET /pepiniere/lots/{numero}`, qui porte `echeances` et
  `action_suggeree` (`echeances_lots.echeances_d_un_lot`, un seul lot, sans rang
  d'urgence ni résumé). `GET /pepiniere/lots` gagne `pepinieres` : « Déplacer » n'est
  proposé qu'à partir de deux.
- **Gestes.** `GESTES_OUVERTS_PWA` gagne `mise_en_godet`, `perte_godet`, `cloture_lot`.
  Un geste de lot cite son lot comme le jardinier le dirait (`numero_lot_cite`,
  US-209), résolu au récapitulatif ; aucun chemin d'écriture n'est ajouté à la PWA.
- **Levée (US-212).** Pas livrée : `LEVEE_DISPONIBLE = false` dans `ficheLot.js`, ni
  « Noter la levée » ni compteur dans l'application. La page de contrôle visuel
  (`/fiche-lot`) force le geste pour montrer le compteur. US-212 passe la constante à
  `true` et ouvre le geste côté serveur dans la même livraison.

### Clôturer un lot (`cloture_lot`)

Solde le lot **entier**, définitivement : godets restants ET graines non levées. Décision
produit du 14/10/2026. Événement `cloture_lot` (`origine_graines_id` = semis du lot ;
`quantite` = godets soldés, `nb_graines_semees` = graines soldées, relus à la
confirmation par `evenements.resoudre_lot_cloture`).

| Où | Effet |
|---|---|
| `calcul_lots_pepiniere` | `cloture`, `date_cloture` ; `stock_residuel_godet` et `graines_en_germination` à 0 ; germination « close » ; l'historique (plants obtenus, plantés, vendus) n'est jamais réécrit |
| `calcul_godets`, `calcul_stock_par_variete` | les godets soldés sortent du stock comme une perte ; le semis clôturé n'est plus « en germination » |
| échéances | un lot clôturé n'a plus d'action suggérée et n'est plus dormant (rien ne reste) |
| bot | récapitulatif en une phrase, dit ce qui est soldé ; lot inconnu, déjà clôturé ou épuisé : `ClotureRefuseeError`, rien d'écrit |

Le geste préparé attend dans la file de gestes en attente (US-224), dont les relances
le rappellent au jardinier : aucune relance propre à la clôture.

## L'onglet « Aujourd'hui » (US-215)

`frontend/src/components/OngletAujourdhui.jsx` (`CarteReponsePepiniere`, `LigneLot`),
monté par `views/Pepiniere.jsx` derrière une barre d'onglets ; l'onglet **Lots** est
l'écran d'US-061 **inchangé**. Mise en forme dans `lib/pepiniere.js` (section US-215,
`npm test` : `pepiniere.aujourdhui.test.js`) — rien n'y est recalculé.

- **Onglets** : `ONGLETS_LIVRES` ; US-218 et US-219 y passent leur drapeau à `true`.
  Un onglet demandé mais non livré (intention `onglet=emplacements` du Plan) ouvre
  « Aujourd'hui ».
- **Une lecture** : `GET /pepiniere/lots`, dont `pepinieres` porte maintenant
  `superficie_m2` et `type_pepiniere` (copie pour la pastille d'une pépinière unique ;
  `lots_pepiniere.py` est ajouté à la liste d'US-208 / CA7, aucun calcul n'y lit le type).
- **Bandeau** : `cartesReponses(resume, lots)` ; les filtres (`FILTRES_BANDEAU`) reprennent
  les règles du résumé d'US-214 sur les échéances déjà calculées.
- **Boutons** : `boutonDeLigne` = le geste de l'action suggérée (`gestesDuLot`, US-216),
  déposé par `BoutonGeste` dans la file (US-224) : **aucune redirection vers Telegram**,
  une notification confirme le dépôt. La relecture au retour d'onglet est celle d'US-216.
- **État d'écran** (US-195) : `onglet`, `qJour`, `bandeau`, `emplacement` dans
  `useEtatEcran('pepiniere')`.
- Page de contrôle visuel : `/pepiniere-aujourdhui?etat=nominal|une_pepiniere|vide|lecture_seule|echec`.

## Où les mettre (US-217)

- `ou_mettre` est joint à chaque lot **qui a des godets** par `lire_echeances` (liste) et
  `echeances_d_un_lot` (fiche par numéro) ; `None` sinon.
- `_lire_le_plan` lit parcelles, occupation, fiches culture (`plan.attributs_par_culture`,
  qui porte désormais `exposition`) et la répartition **une fois** par lecture — jamais
  par lot (CA1). Le résumé « Prêts pour le plan » en dérive (`_rangs_libres(lecture)`),
  d'où des rangs libres identiques des deux côtés (CA10).
- Places : `repartition_rangs._places_du_rang(longueur parcelle, espacement culture du lot)`
  — la règle d'US-227, jamais un calcul parallèle. Places connues → la suggestion se dit
  en places, sinon en rangs libres (jamais les deux).
- Exposition [US-239] : `comparer_exposition(ensoleillement_parcelle, exposition_culture,
  nom_parcelle)` compare `Parcelle.ensoleillement` (migration_v56 ; l'orientation
  `Parcelle.exposition` n'entre plus dans la comparaison, jamais convertie) à celle de la
  culture, normalisées par `attributs_culture.normaliser_valeur`. L'écart se mesure en crans
  sur plein soleil → mi-ombre → ombre : `ecart` 0/1/2, `rang` 0/1/2, `deconseille` à 2 ;
  absente d'un côté → `non_comparable` (rang 3, `invitation` = la phrase à dire au
  compagnon). `utils.parcelles.normaliser_ensoleillement` est le point d'écriture unique
  (bot `/parcelle modifier … ensoleillement=`, règle `parcelle_ensoleillement`, PWA
  `PATCH /parcelles/{id}`) et porte les définitions en heures.
- Ordre : rang d'écart (concordante, 1 cran, 2 crans, non comparable), places libres
  décroissantes, rangs libres décroissants, ordre des parcelles ; rangs inconnus
  (`nb_rangs` nul) à la fin. `premier_rang_libre` reste `None` tant qu'US-203 ne donne
  pas de position.
- Front : section `OuLesMettre` de `FicheLot.jsx`, règles `suggestionsVisibles`,
  `placeEnClair`, `gesteMiseEnTerreIci` dans `lib/ficheLot.js`. La rotation est vérifiée
  par le compagnon à la confirmation (US-167), pas ici.

## Tests

`tests/test_us217_ou_mettre_plants.py` — suggestions, exclusions, exposition, ordre,
rangs inconnus, places, date passée, lecture unique du Plan.

`tests/test_us215_pepiniere_aujourdhui.py` — pépinières exposées, corpus, garde-fous
du front (aucune redirection, onglet Lots intact).

`tests/test_us214_echeances_lots.py` — chaque ligne de la table, chaque action,
les fourchettes et leurs bornes, l'absence de chaque donnée, les trois cas
d'endurcissement et la borne J+7, la dormance et son exclusion, l'ordre
d'urgence, le résumé, la date de référence passée, l'isolation entre potagers.

`tests/test_us216_fiche_lot.py` — la clôture (lot, stock agrégé, refus), les gestes de la fiche
et leurs phrases à dicter, la lecture par numéro, le corpus ; `frontend/src/lib/ficheLot.test.js`
pour les règles d'affichage.
