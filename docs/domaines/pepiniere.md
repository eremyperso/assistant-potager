# Pépinière — échéances d'un lot, action suggérée, ordre d'urgence

Fiche de conception de la Pépinière « poste de travail » (épic 12). Elle se lit
avant de toucher `app/services/echeances_lots.py`, au calcul des lots
(`utils/stock.calcul_lots_pepiniere`) ou à la réponse de `GET /pepiniere/lots`.

## Principe

Les échéances, l'action suggérée et le rang d'urgence sont calculés **à un seul
endroit** — `app/services/echeances_lots.py` — en **lecture seule**, à une date de
référence, sans appel au modèle. L'API recopie ; les écrans (US-218 Ma pépinière,
US-216 fiche du lot) affichent. Aucun d'eux ne recalcule
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
déplacement, une **levée notée** (US-212 : le jardinier qui compte ses levés ne
l'a pas oublié), une plantation ou une sortie (vente, perte) qui lui est imputée.
L'observation libre sur la parcelle n'en est pas un.

## Action suggérée — une par lot

Évaluée dans cet ordre, la première qui s'applique gagne :

1. **Clôturer** — le lot est dormant ;
2. **Repiquer** — repiquage *à repiquer* ou *en retard* ;
3. **Mettre en terre** — endurcissement en cours ou terminé, ou mise en terre
   prévue atteinte ou dépassée ;
4. **Noter la levée** — des graines à repiquer, avant la fourchette de repiquage,
   aucune levée notée (`_levee_notee` : `nb_leves` n'est pas `None`, le geste est
   celui d'US-212) ;
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
| `a_repiquer` | `lots`, `plants` — lots *à repiquer* ou *en retard* ; `plants` = plants **levés** quand la levée est notée (US-212), sinon graines semées |
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
- **Levée (US-212).** Livrée : `LEVEE_DISPONIBLE = true` dans `ficheLot.js` (le drapeau
  reste, il coupe « Noter la levée » d'un coup), `levee` fait partie de `GESTES_OUVERTS_PWA` et
  de `GESTES_DE_LOT`. **La fiche ne saisit rien** : « Noter la levée » est un `BoutonGeste` comme
  les autres, qui dépose le geste avec son seul lot — ni compteur, ni case « terminée » ; le
  serveur ignore un nombre qu'un ancien client enverrait (`deposer_geste`). Le bot demande le
  détail. Voir la section « La levée d'un lot ».

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
| cycle de vie | `cycle_vie_culture` → `clotures`, `GET /godets/detail` → `clotures` (`godets_soldes`, `graines_soldees`) : une ligne 🔒 du fil « Détail du lot », filtrée sur le lot affiché |
| bot | récapitulatif en une phrase, dit ce qui est soldé ; lot inconnu, déjà clôturé ou épuisé : `ClotureRefuseeError`, rien d'écrit |

Le geste préparé attend dans la file de gestes en attente (US-224), dont les relances
le rappellent au jardinier : aucune relance propre à la clôture.

## La levée d'un lot (US-212)

Un **constat**, pas un mouvement de stock : « combien de graines de cette barquette ont
levé ». Événement `levee` (`origine_graines_id` = semis du lot, `quantite` = levés,
`nb_graines_semees` = le « sur N » dicté, `levee_terminee`). Colonne ajoutée par
`migration_v57.sql` (booléen, CHECK : seul un geste `levee` la porte) ; rien d'autre.

| Où | Règle |
|---|---|
| `calcul_lots_pepiniere` | le **dernier comptage** à la date de référence fait foi (`nb_leves`, `date_derniere_levee`) ; les comptages ne s'additionnent jamais. `taux_levee` = levés ÷ graines semées, `None` sans graines connues (≠ `taux_germination`, qui compte les plants repiqués) |
| levée **terminée** | état du lot, collant : un comptage ultérieur met le nombre à jour sans rouvrir la germination. `etat_germination` = « close », `graines_en_germination` = 0, `graines_non_levees_soldees` = semées − levés |
| levée non terminée | l'état de germination, `graines_en_germination` et tout ce qui touche au repiquage restent exactement ce qu'ils étaient (CA7) |
| moyenne (CA8) | `moyenne_levee_culture` = moyenne des taux des **autres** lots de la même culture dont la levée est notée, dans ce potager, **à partir de deux** lots (`nb_lots_moyenne_levee`) ; chaque lot pèse autant |
| incohérences | `incoherence_levee` (levés > semés), `incoherence_repiquage_levee` (plants repiqués > levés) : drapeaux, jamais de bornage ; le « sur N » discordant est signalé au récapitulatif (`_alertes_levee`) |
| cycle de vie (CA14) | `cycle_vie_culture` → `levees`, `GET /godets/detail` → `levees` (`nb_leves`, `sur`, `terminee`) : **chaque** comptage, à sa date, dans le fil « Détail du lot » |
| stocks (CA10) | **aucun** : `calcul_godets`, `calcul_stock_par_variete`, `/godets`, `/stats` sont lus tels quels ; `natures_impactees("levee")` = pépinière + semis, jamais stock |

### `graines_en_germination` contre `graines_non_soldees`

Deux notions que le code confondait avant US-212. `graines_en_germination` dit ce qui est
**encore en train de lever** : elle tombe à 0 pour un lot clôturé *ou dont la levée est
terminée*. `graines_non_soldees` (= semées − soldées par un repiquage, 0 si clôturé) dit ce que
le lot peut **encore fournir à un repiquage** : les plants levés restent à repiquer quand la
germination est close. Tout garde-fou de repiquage, tout « le lot a-t-il encore quelque
chose » lit `utils.stock.graines_restantes(lot)` — jamais `graines_en_germination` — et
cette fonction retombe sur l'ancienne clé pour un lot construit à la main (tests, mocks). Un
repiquage de plus de plants qu'il n'en a levé n'est jamais refusé (CA9) : c'est un drapeau.

### Désigner le lot, une seule fois

`evenements.designer_lot` est la règle unique du déplacement (US-211), de la clôture (US-216)
et de la levée : numéro cité (`origine_graines_id`), sinon la culture quand **un seul** lot en
cours correspond, sinon `LotIndetermineError` (le bot pose le choix par boutons, numéro et date
de semis — `godets._preparer_levee`, callback `levlot`). `resoudre_lot_levee` ajoute les refus
propres à la levée : lot sans semis rattaché, lot clôturé (`LeveeRefuseeError`), et aucun lot de
pépinière pour la culture (`LeveeHorsPepiniereError` — « les carottes ont levé » en pleine
terre : le bot le dit et propose de la noter en observation, `levlot_obs`, sans modèle).

### La PWA dépose le geste, le bot demande le détail (CA11)

Décision produit : depuis la PWA la saisie est limitée, **seul le geste** est possible
(« levée du lot 128 »). Mêmes principes que la mise en godet et la perte (US-224), avec deux
questions propres à la levée, posées par `godets._preparer_levee` avant le récapitulatif :

1. **Le nombre de levés** (`_poser_question_levee`) — quand `quantite` manque, que le geste vienne
   de la file ou d'une phrase dictée sans nombre. La question rappelle le lot (culture, variété,
   date de semis, graines semées, dernier comptage). La réponse est un texte
   (`messages._repondre_nombre_de_leves`, état `_QUANTITE_PENDING` marqué `levee`) : un nombre,
   zéro compris, « rien » et « aucun » valent 0 ; une phrase longue est une nouvelle saisie.
   **Lot déjà en partie repiqué** (`plants_obtenus` > 0 et graines restantes > 0) : la question
   porte sur les **graines restantes** (« parmi les 5 graines restantes »), car un plant repiqué a
   forcément levé. Le bot pose `_leves_deja_repiques` ; la réponse est convertie en total
   (repiqués + réponse, `_leves_parmi_restantes` gardé pour le récapitulatif). Le comptage
   enregistré reste donc un **total du lot** : taux, moyenne, solde et incohérences inchangés.
2. **La levée est-elle terminée ?** (`_poser_question_levee_terminee`, callbacks `levdet_oui` /
   `levdet_non`, état `_LEVEE_TERMINEE_PENDING`) — seulement quand le bot vient de demander le
   nombre (`_levee_a_preciser`) ; elle dit ce que « oui » solde (graines non levées, germination
   close) avant de demander. Une phrase dictée **avec** son nombre ne pose aucune des deux :
   sans « terminée », la levée est en cours.

Chaque réponse relance `_parse_and_save` avec le `geste_file` d'origine (INC-003) ; `levdet_cancel`
laisse le geste dans la file (« Laisser dans ma file ») ou l'annule.

### Grammaire

`llm/parseur_deterministe.py` lit « levée du lot 128 : 40 », « 40 choux frisés levés sur 48 »,
« les tomates cerise ont levé, 12 plants », « levée terminée pour le lot 128 : 40 ». Le verbe de
la levée est cherché dans **toute** la phrase quand aucun geste n'est en tête
(`_extraire_geste_levee`), avec son auxiliaire ; `llm/routeur._est_levee_dictee` fait de même
pour le routage. « terminée » n'est un drapeau qu'avec une levée.

## L'onglet « Ma pépinière » (US-218)

Deux onglets (`ONGLETS_PEPINIERE` de `lib/parcours.js`) : **Ma pépinière**, ouvert par
défaut, et **Lots** (journal de saison, US-242 — voir plus bas). Les onglets « Aujourd'hui » (US-215),
« Calendrier » (frise, première version d'US-218) et « Emplacements » (US-219) sont
**supprimés** ; `ongletInitial` envoie toute autre valeur (adresse, intention du Plan)
vers le parcours. Maquette de référence : « Ma pepiniere - HF » (Claude Design, projet
potager 2026). Le libellé « Ma pépinière » vient de la maquette HF ; la clé reste `parcours`.

`frontend/src/components/OngletParcours.jsx`, monté par `views/Pepiniere.jsx`. Mise en
forme dans `lib/parcours.js` (sans React, `npm test` : `parcours.test.js`) — rien n'y est
recalculé : colonnes, états, échéances, ordre dans une case et compteurs viennent du bloc
`parcours` (US-240, section suivante).

- **Une lecture** : `GET /pepiniere/lots`. Seule la pastille météo de la barre lit
  `GET /meteo`, et seulement sans date de référence passée ; illisible, elle se tait.
- **Kanban** : `kanban(parcours, { filtre })` → une ligne par pépinière (vides comprises),
  puis « Sans emplacement » si `parcours.sans_emplacement` ; un `<table>` sémantique au-dessus
  de 48rem de conteneur, quatre onglets de stade en dessous (`ongletStadeParDefaut` : le
  premier en alerte, sinon le premier non vide). Container queries, aucun breakpoint.
- **Étiquette** : `enteteEtiquette` (mot + teinte `tete-*`), `grandChiffre`, `quantitesEtiquette`,
  `datesEtiquette`, `regleEtiquette` (piste du `debut_regle` à la fin de fourchette ou au jour
  de référence ; sept cases en endurcissement ; rien sans fourchette). Fragments : repère
  `rang/total`, `fragmentsLies` éclairés au survol / focus, liens réciproques.
- **Gestes** : `gestesEtiquette` filtre `gestesDuLot` (la règle de la fiche, US-216) selon le
  fragment — levée : Repiquer, Noter la levée (« (terminée) » si `soldable_par_levee_terminee`) ;
  godets : Mettre en terre (quantité du fragment) ; sans emplacement : « Ranger dans… »
  (`deplacement` sans destination, US-241 / CA12). Deux au plus, déposés par `BoutonGeste`.
  « Durée ? » : la commande `/calendrier duree <culture> semis-godet|repiquage 10-15`, copiable.
- **Bande « Le bon moment pour semer »** : `bandeSemer` — tuiles de `parcours.a_semer`,
  repliées de `a_semer_sans_graines`, et, quand les deux sont vides, `parcours.calendrier_semis`
  (six mois, cultures qui s'ouvrent, prochaine ouverture ; calculé par
  `echeances_lots._calendrier_semis`, seulement dans ce cas).
- **Tiroir** : `parcours.dormants`, gestes `gestesDormant` (Mettre en terre s'il a des godets,
  Clôturer). Ouvert au large, bouton « Ouvrir › » au téléphone.
- **Compteurs** : `compteursBarre` ; à zéro ils restent, éteints (maquette HF). « à repiquer »,
  « à sortir », « endurcit » atténuent les autres étiquettes (`miseEnEvidence`).
- **État d'écran** (US-195, RT12) : `onglet`, `filtre`, `compteur`, `stade`, `tiroir` dans
  `useEtatEcran('pepiniere')` ; l'intention I5 du Plan pose `filtre` (nom de pépinière).
- **Tokens** : couleurs de stade `--sem`, `--god`, `--end`, `--frk` (+ `-d`, `-s`), police
  Kalam (`font-hand`) pour les jalons ; motifs `motif-*` et en-têtes `tete-*` hors `@layer`
  dans `index.css` (classes composées à l'exécution, à l'abri de la purge).
- **Fin de règle** : `echeances.sortie_prevue` (conservé de la première version, A39).
- **Fiche en bandeau** (maquette HF, option B retenue) : au-delà de 768 px de conteneur
  (`LARGEUR_BANDEAU`, le kanban en tableau), l'appui sur une étiquette ouvre `FicheLotBandeau`
  (`FicheLot.jsx`) dans une ligne `<tr>` glissée sous la rangée de sa pépinière (sous la
  dernière si la rangée est filtrée), découpée sur les colonnes : parties du lot (cliquables,
  elles changent l'étiquette ouverte), échéance de l'étiquette et « Où les mettre », gestes
  (`gestesDuLot`), bilan (`bilanLot`) et journal. L'étiquette ouverte porte un contour vert et
  la pastille « #n · ouvert » ; un second appui ferme. Un lot sans étiquette (dormant) et le
  téléphone gardent la fiche en fenêtre ; l'onglet Lots n'a plus de panneau (US-242).
- Page de contrôle visuel : `/pepiniere-parcours?etat=nominal|hf|une_pepiniere|pepiniere_vide|aucun_lot|sans_semer|lecture_seule|chargement|echec`.

## L'onglet « Lots » en journal de saison (US-242)

Registre **sans geste** (A40) remplaçant la grille de cartes d'US-061 ; maquette « Lots -
Journal de saison HF » (Claude Design, 19/10/2026). Règles dans `lib/lotsJournal.js`
(testées par `lotsJournal.test.js`), dessin dans `components/OngletLots.jsx`.

- **Statut** (`statutLot`) : `termine` = `estTermine` de la fiche ; `a_regler` = quantité
  semée non dite, ou `echeances.raisons` non vide sans échéance (délai non renseigné) ;
  `en_cours` sinon. Filtre En cours / À régler / Terminés / Tous, « Tous » par défaut.
- **Gestes datés** (`gestesDates`) : semis, dernière mise en godet, déplacement, levée,
  clôture, chaque mise en terre (avec sa parcelle), vente et perte en godet, et
  `date_dernier_geste` (« type non transmis ») s'il ne coïncide avec aucun. Mises en terre,
  ventes et pertes viennent de `sorties_datees` : `calcul_lots_pepiniere` garde, pour chaque
  sortie imputée à un lot (`_allouer`, paramètre `trace`), sa date, sa quantité et la parcelle
  de la plantation ; une plantation répartie sur deux lots donne à chacun sa part. Le reste
  non couvert (API sans le détail, geste sans date) est compté « date non transmise »
  (`gestesNonDates`), jamais posé sur la frise.
- **Fenêtre** (`fenetre`) : `saison` 1er mars → 30 nov., étendue au jour de référence ;
  `recent` du 1er du mois M-2 à la fin du mois M+1 (libellé calculé). Le téléphone (conteneur
  < 768 px) prend toujours la récente. Un semis antérieur est accroché au bord gauche, pâle.
- **Parts** (`partsDuLot`) : en levée = levés à repiquer si la levée est terminée, sinon
  graines non soldées ; non levées = semées − obtenues − en levée.
- **Fiche** : dépliée sous la ligne (conteneur ≥ 768 px), plein écran sinon ; « Agir dans Ma
  pépinière » bascule d'onglet et y ouvre `FicheLot`. « Aller au lot n° » remet « Tous » et
  déplie ; une adresse `lot=` sur l'onglet Lots déplie aussi.
- État d'écran : `filtreLots`, `zoom`, `lotDeplie`. Page de contrôle : `/pepiniere-lots`.

## Le parcours du plant (US-240)

Bloc `parcours` de `GET /pepiniere/lots`, calculé par `echeances_lots._parcours` dans la
même lecture que les échéances : l'onglet Ma pépinière (US-218) l'affiche sans rien recalculer
(RT7). Aucun geste, aucune lecture de plus. Conception : `docs/EPIC 9-12 - PLAN CULTURES
PEPINIERE/pepiniere/01_VUE_PARCOURS.md` (P4 à P23).

**Étiquettes, fragments (A31, CA2-CA4).** Un lot en cours, non dormant, donne une étiquette
par couple (stade, emplacement) : une « en levée » s'il a des graines non soldées
(`_graines_en_levee` = `graines_restantes` − `graines_non_levees_soldees`, donc ni repiquées,
ni soldées par une levée terminée ou une clôture ; un semis sans quantité est en levée, sans
nombre), une par emplacement où il a des godets disponibles (`_godets_par_emplacement`). Elles
sont numérotées `fragment.rang` sur `fragment.total`, levée d'abord ; `total` = 1 : pas de
repère. Les graines sont à `graines_emplacement` (parcelle du semis, ou destination d'un
déplacement **entier**) ; les godets là où les place `repartition_godets` (US-241, section
suivante) — une étiquette par pépinière d'un lot réparti. Une pépinière inconnue du potager
tombe dans « Sans emplacement » (`emplacement_id` nul).

**Table des colonnes (P9, CA5)**, à la date de référence :

| Colonne (`stade`) | Une étiquette y va quand… |
|---|---|
| **En levée** (`levee`) | graines non soldées |
| **En godet** (`godet`) | godets en pépinière chaude, de type inconnu ou sans emplacement, avant le compte à rebours d'endurcissement, mise en terre non atteinte ou non calculable |
| **Endurcissement** (`endurcissement`) | compte à rebours de 7 jours commencé (chaude ou inconnue, ou déplacé vers le froid depuis moins de 7 jours), **ou** godets en pépinière froide : ils s'endurcissent sur place (A35) |
| **Prêt à sortir** (`pret`) | fourchette de mise en terre prévue atteinte ou dépassée, quel que soit le type de pépinière — prime sur le reste |

**États (P15, CA6)** :

| `etat` | Colonne | Quand | Échéance |
|---|---|---|---|
| `repiquer_retard` | levée | repiquage après la fin de sa fourchette | jours de retard, `en_retard` |
| `a_repiquer` | levée | dans la fourchette de repiquage | 0 |
| `levee_en_cours` | levée | avant la fourchette ; **ou** graines restantes d'un lot en partie repiqué (A33) | jours avant la fourchette ; aucune pour A33 |
| `sortir_retard` | prêt | mise en terre après la fin de sa fourchette | jours de retard, `en_retard` |
| `a_sortir` | prêt | dans la fourchette de mise en terre | 0 |
| `sortir_bientot` | godet | mise en terre dans **15 jours** ou moins (`SEUIL_SORTIR_BIENTOT_JOURS`) | jours avant la fourchette |
| `en_cours` | godet | mise en terre à plus de 15 jours | jours avant la fourchette |
| `endurcir` | endurcissement | compte à rebours en cours, `echeance.endurcissement` = `{jour, sur}` | jours avant la mise en terre |
| `endurcit_sur_place` | endurcissement | godets en pépinière froide, sans compte à rebours | jours avant la mise en terre, si connue |
| `duree_inconnue` | levée ou godet | délai non renseigné, ou date de semis inconnue | aucune ; `echeance.raison` |

`a_repiquer` et `a_sortir` sont les deux états « dans la fourchette » que la liste de CA6 ne
nommait pas. Le seuil de 15 jours est une décision produit du bloc de tête, à côté de 7 et 60
jours, figée par un test.

**A33 — graines restantes.** Les graines d'un lot qui a déjà des plants en godet n'ont plus
d'échéance de repiquage (US-214 ne l'attend que sans aucun godet) : `levee_en_cours`, aucune
échéance, `soldable_par_levee_terminee` vrai — le geste « Noter la levée (terminée) » les
solde (US-212 / CA7). Faute de geste, la dormance d'US-214 ramasse le lot.

**Échéance d'une étiquette** : `jours`, `en_retard`, `du`/`au` (fourchette de repiquage pour
la levée, `echeances.sortie_prevue` pour les godets, A39), `debut_regle` (date de semis ; début
du compte à rebours en endurcissement), `raison`, `libelle` (celui d'US-214), `endurcissement`.
**Ordre** (`_cle_etiquette`, P22) : retards du plus grand au plus petit, échéances de la plus
proche à la plus lointaine, puis sans échéance ; à égalité numéro de lot, identifiant, rang.
La liste est triée une fois : chaque case l'est donc aussi.

**Lignes, compteurs, dormants.** `pepinieres` : toutes celles du potager, dans l'ordre des
parcelles, vides comprises, avec `nb_lots`, `nb_etiquettes`, `nb_alertes` (retards) et
`prochaine_sortie` (P10) ; `sans_emplacement` : la même chose, `None` quand vide (P12).
`compteurs` (`{total, retard}`) : `a_repiquer` (`repiquer_retard`, `a_repiquer`), `a_sortir`
(`sortir_retard`, `a_sortir`, `sortir_bientot`), `endurcit` (`endurcir`, `endurcit_sur_place`)
comptent des **étiquettes** ; `a_semer` des cultures, `dormants` des lots. Les lots dormants
d'US-214 n'ont aucune étiquette : `dormants` porte leurs jours sans geste, date de semis, reste
(graines, godets) et `a_des_godets` (A37), du plus ancien geste au plus récent.

**A34 — à semer.** `parcours.a_semer` = les cultures de `resume.a_semer` (règle d'US-214
inchangée, champs `du`, `au`, `periode`, `jours_restants`, `part_ecoulee` **ajoutés** par
`_bornes_fenetre`) dont des graines sont « en stock », avec `varietes_en_stock`. Les autres
vont dans `a_semer_sans_graines`, par nom. La fenêtre, connue au mois, finit le dernier jour
de son dernier mois ; à cheval sur l'année, elle s'ouvre l'année de la date de référence en
automne, l'année d'avant en hiver ; la part écoulée compte le jour de référence.
**Décision du 19/10/2026** : aucun inventaire de sachets n'existe — il est reporté à un épic
dédié. En attendant, « en stock » se lit dans les **cultures en cours** : une ligne de l'écran
Stocks (`calcul_stock_varietes`, la règle existante) dont le stock est supérieur à zéro ; une
variété à zéro n'est pas en stock, « Variété non précisée » rend la culture disponible sans
variété citée. `source_stock_graines` = `cultures_en_cours` le dit au front. Le stock est lu
**une fois**, et pas du tout sans culture candidate.

## Le déplacement partiel (US-241)

Le geste `deplacement` (US-211) accepte une **quantité de godets** facultative. Sans
quantité : le lot entier, graines comprises, comme avant. Avec : seuls des godets partent,
d'une **origine** vers une destination, et le lot est **coupé par l'emplacement**. Aucun
stock ne bouge (CA10) : `compter_evenements` exclut toujours le déplacement, et aucune
lecture de stock ne lit sa quantité.

**Donnée** (`migration_v58.sql`). `evenements.parcelle_origine_id`, nullable : la pépinière
d'où partent les godets d'un déplacement chiffré (NULL = emplacement jamais renseigné), ou
d'où une plantation, une perte, une vente retire ceux d'un lot réparti (NULL = non dite).
Écrite par `evenements._parcelle_origine`, jamais pour un déplacement entier.

**Répartition** (`utils/stock._rejouer_mouvements`, `_repartir_godets`). Un lot sans
déplacement chiffré garde la règle d'US-210 : tous ses godets à son emplacement courant.
Un lot qui en a un (`_partiel`) est **rejoué dans l'ordre des dates** (puis des
identifiants) à partir de la parcelle du semis : mises en godet, sorties imputées
(`_allouer` les note avec leur origine), déplacements, clôture. Tant que le lot est d'un
seul tenant il suit US-210 ; le premier déplacement chiffré le coupe ; un retour qui réunit
tous les godets au même endroit le rend d'un seul tenant ; un déplacement entier regroupe
tout, graines comprises. Une mise en godet faite après la coupe pose ses godets où elle le
dit, sinon là où sont les graines. Sortie : `repartition_godets` = [{`parcelle_id`, `nom`,
`type_pepiniere`, `godets`, `depuis`}] (godets **disponibles**, dans l'ordre d'arrivée),
`reparti`, `repartition_a_verifier`. Le stock du lot fait foi : un écart entre le rejeu et
`stock_residuel_godet` est ajusté sur l'emplacement courant et marque le lot « à vérifier ».
`graines_emplacement` ne suit que le dernier déplacement **entier**. `godets_par_emplacement`
(fiche Telegram) reprend la répartition nette d'un lot réparti. `emplacement` reste la
destination du dernier déplacement, chiffré ou non (contrat US-210 inchangé).

**Endurcissement par emplacement (CA8).** `depuis` = date de la dernière arrivée de godets
à cet endroit par un déplacement. `echeances_lots._godets_par_emplacement` la passe à
`_endurcissement` : la partie posée au froid compte « J+n/7 » depuis son déplacement, celle
restée au chaud garde son compte à rebours de mise en terre. Deux arrivées au même endroit :
la plus récente fait foi (prudence, on ne sort pas des godets non endurcis).

**Désigner l'origine** (`evenements.origine_des_godets`). L'origine choisie ou déposée
(`parcelle_origine_id` présent dans le geste, None = non renseigné), sinon dite
(`parcelle_origine`, lue par le parseur dans « de la serre »), sinon l'unique pépinière où
le lot a des godets. Un lot réparti sans origine : `OrigineAmbigueError`, le bot propose
« Serre (10) », « Châssis froid (6) » (`godets._demander_origine_godets`, callback
`deplorig:`).

**Refus** (`resoudre_lot_deplacement`) : quantité nulle, négative ou non entière ; lot sans
godet (« les graines suivent le lot entier », CA5) ; quantité supérieure aux godets de
l'origine (« n'a que 10 godets en « Serre » ») ; destination = origine. Tous les godets d'un
lot d'un seul tenant : la quantité est retirée, c'est un déplacement entier (CA1). Un lot
réparti peut être regroupé entier là où est déjà une partie.

**Sans destination (CA12).** « déplacement du lot 26 » (verbe explicite et lot cité ; un
verbe familier sans pépinière reste un repli), le bouton « Déplacer » de la fiche du lot ou
« Ranger dans… » : `DestinationManquanteError` porte les pépinières du potager hors
l'origine, le bot les propose (`_demander_destination`, callback `depldest:`). La file
(`deposer_geste`) accepte quantité, destination et `emplacement_id` (l'étiquette d'origine)
facultatifs ; `phrase_a_dicter` rend « déplacement de 6 godets du lot 21 parcelle châssis
froid ».

**A41 — consommation d'un lot réparti, EN SUSPENS** (PO, 19/10/2026 : à trancher après des
tests terrain). Aucune règle d'attribution n'est proposée au jardinier : une plantation, une
perte ou une vente d'un lot réparti sans origine fait demander l'origine par boutons
(`controler_origine_sortie`, crochet `saisie._parse_and_save`), un geste déposé depuis une
étiquette la porte. **Repli du calcul** (décision du 19/10/2026), pour l'historique, une
imputation FIFO ou une correction au Journal : retirer d'abord de l'emplacement courant, puis
des autres dans l'ordre d'arrivée, et marquer `repartition_a_verifier`. La piste « d'abord
la partie la plus avancée » n'est pas retenue.

**Récapitulatif** : « déplacement de 6 godets du lot 21 (poivron) · serre chaude → châssis
froid » ; origine inconnue : « emplacement non renseigné » (CA13), au récapitulatif comme au
cycle de vie (`_deplacements_du_lot` → `quantite`, origine stockée).

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

`tests/test_us212_noter_levee.py` — les formes dictées, l'instantané, la levée terminée, la
moyenne (0, 1, 2 lots, isolation entre potagers), les incohérences, les refus, l'absence de
stock, la PWA ; `frontend/src/lib/gestes.test.js` pour la phrase à dicter.

`tests/test_us217_ou_mettre_plants.py` — suggestions, exclusions, exposition, ordre,
rangs inconnus, places, date passée, lecture unique du Plan.

`tests/test_us215_pepiniere_aujourdhui.py` — pépinières exposées, corpus, garde-fous
du front (aucune redirection, onglet Lots intact).

`tests/test_us214_echeances_lots.py` — chaque ligne de la table, chaque action,
les fourchettes et leurs bornes, l'absence de chaque donnée, les trois cas
d'endurcissement et la borne J+7, la dormance et son exclusion, l'ordre
d'urgence, le résumé, la date de référence passée, l'isolation entre potagers.

`tests/test_us218_pepiniere_calendrier.py` — `sortie_prevue` à chaque stade, son absence
motivée, l'API, le corpus, les garde-fous du front ; `frontend/src/lib/calendrierPepiniere.test.js`
pour le placement.

`tests/test_us240_parcours_plant.py` — chaque ligne de la table des colonnes, chaque état, la
coupure par le stade, A33, A35, la date passée, les lignes (vide, sans emplacement), les
dormants, chaque compteur, à semer avec et sans culture en cours, la variété à zéro, les bornes
de fenêtre, une seule lecture du stock, la lecture seule, l'isolation, l'API.

`tests/test_us241_deplacement_partiel.py` — entier inchangé, partiel, quantité égale au
disponible, excessive, nulle, graines, origine ambiguë, sans emplacement, sans destination,
retour à l'origine, endurcissement par emplacement, sorties d'un lot réparti (origine dite,
demandée, repli), correction et suppression, date passée, stocks inchangés, isolation.

`tests/test_us216_fiche_lot.py` — la clôture (lot, stock agrégé, refus), les gestes de la fiche
et leurs phrases à dicter, la lecture par numéro, le corpus ; `frontend/src/lib/ficheLot.test.js`
pour les règles d'affichage.
