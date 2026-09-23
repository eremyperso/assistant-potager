# Le plan en rangs

Tout ce qui répartit les cultures en place sur les rangs de leur parcelle vit
dans `app/services/repartition_rangs.py`, et nulle part ailleurs. `GET /plan`
l'appelle une fois et recopie ce qu'elle rend ; la Vue plan (US-200), le détail
de parcelle (US-222) et la Pépinière (« où mettre les plants », US-217) lisent
tous cette même répartition. C'est la raison d'être du module : deux écrans ne
peuvent pas compter différemment la place qui reste.

## Les deux sens du mot « rang »

Ils ne se mélangent jamais, et tout le module tient dans cette distinction :

| | Le rang d'une **parcelle** | Le rang d'un **geste** |
|---|---|---|
| Où | `Parcelle.nb_rangs` (US-197) | `Evenement.rang` |
| Ce que c'est | un **dénominateur déclaré** : « la planche nord a 5 rangs » | un **multiplicateur de quantité** : « planté 4 salades **sur** 3 rangs » = 12 plants |
| Ce que ça n'est pas | une mesure, une surface | une **position** |

Une planche a en revanche **une longueur unique** (`Parcelle.longueur_m`,
US-225), et tous ses rangs la partagent : « longueur de la parcelle » et
« longueur d'un rang » sont le même nombre, ce qui évite d'avoir à déclarer quoi
que ce soit rang par rang. C'est la longueur *utile*, allées et bordures
exclues. La **largeur** n'existe nulle part en base : elle se déduit à la lecture
(`superficie_m2 ÷ longueur_m`, `utils.parcelles.largeur_deduite`), sert de repère
d'affichage et n'est jamais réinjectée dans un calcul — la stocker aurait créé un
triplet longueur × largeur × superficie dont deux valeurs sur trois auraient
dérivé à la première correction. Une largeur déduite sous 0,2 m est signalée
(`largeur_incoherente`) sans que rien ne soit corrigé : le jardinier seul sait
laquelle des deux valeurs est fausse.

La base ne sait donc pas qu'une tomate est « au rang 1 ». Les rangs sont
numérotés **dans l'ordre d'installation** des cultures, et la réponse le dit
(`mode_numerotation: "ordre_installation"`, arbitrage A5). La position réelle
devient possible avec US-203, qui ouvrira `positions` et `mixte` — le champ
existe pour ça dès maintenant.

## Les neuf règles de répartition (US-198)

| # | Règle |
|---|---|
| R1 | Une **ligne** est une culture × variété × unité en place dans la parcelle, exactement comme le plan d'occupation la compte (`calcul_occupation_parcelles`). Aucune ligne ajoutée, aucune retirée |
| R2 | Une ligne occupe **un rang**, ou le nombre de rangs **dit** à son installation. Plusieurs installations qui le disent → **somme** de leurs rangs ; celles qui n'en disent rien n'en ajoutent aucun — le nombre de *gestes* n'est pas un nombre de rangs (retour de terrain du 23/09/2026) |
| R3 | Chaque rang porte la **quantité par rang** : quantité ÷ rangs, arrondie à l'unité pour ce qui se compte, au dixième pour les m², **jamais zéro** quand la quantité ne l'est pas |
| R4 | **Mode d'implantation** déduit de l'unité : `m²`/`m2` → `surface` ; `poquet(s)` → `poquet` (US-199) ; toute autre unité → `rang`. Écrit une seule fois, dans `mode_implantation()` |
| R5 | **Numérotation** : lignes rangées de la plus anciennement installée à la plus récente (à égalité : nom de culture, puis variété), rangs numérotés à partir de 1 dans cet ordre. Les rangs libres suivent, jusqu'au nombre déclaré |
| R6 | **Rangs libres** = déclarés − occupés, jamais négatif. Sans nombre déclaré : `None` (« inconnu »), jamais zéro |
| R7 | **Dépassement** : plus de rangs occupés que déclarés → toutes les lignes restent, la parcelle porte l'écart. Aucune culture n'est jamais masquée |
| R8 | **Parcelle pépinière** : ses semis ne sont pas des lignes (exclusion de l'occupation, inchangée) ; elle porte le **nombre de lots en cours** qu'elle abrite. Une plantation faite dans une pépinière reste une ligne comme ailleurs |
| R9 | Les cultures **non localisées** forment un bloc à part : `rangs` à `None`, aucune numérotation |

Un **lot en cours** (R8) est un lot de `calcul_lots_pepiniere` qui occupe encore
la pépinière : des graines pas encore levées (`graines_en_germination > 0`) ou
des plants en godet pas encore plantés (`stock_residuel_godet > 0`).

## Remplissage progressif des plantations (US-198 / CA10 à CA19)

Les règles R2 et R3 restent le repli. Quand le nombre de rangs de la parcelle,
sa longueur et l'espacement sont connus, les plantations en plants (ou pieds)
sans nombre de rangs explicite sont réparties par capacité. L'identité reste
celle de l'occupation : culture × variété × unité × nature du geste, sans
fusion de variétés ni d'unités. Les semis, surfaces, poquets, pépinières et
cultures non localisées ne changent pas.

Une lecture des installations, filtrée par potager et date de référence,
remplace l'ancienne agrégation SQL des multiplicateurs. Elle fournit à la fois
les rangs déclarés et les gestes ordonnés par date puis identifiant, sans
requête supplémentaire. Les gestes implicites remplissent les rangs compatibles
par numéro croissant, puis ouvrent autant de rangs libres que nécessaire.
Un geste explicite conserve son multiplicateur et ouvre ses rangs déclarés ;
un ajout implicite ultérieur peut en compléter les places restantes.

Sans rang libre, l'excédent reste sur le dernier rang compatible. S'il n'existe
encore aucun rang compatible, une nouvelle culture occupe un rang supplémentaire
et le dépassement de parcelle est signalé. Aucun plant n'est supprimé et aucune
autre culture n'est mélangée ou déplacée. Deux rangs d'une même culture peuvent
donc être séparés par une autre culture : le frontend ne les groupe visuellement
que s'ils sont consécutifs.

`disposition.rangs[].quantite_par_rang` porte désormais la quantité réelle du
rang, utilisée pour ses mesures et son affichage. Le champ de ligne historique
`cultures[].quantite_par_rang` reste une moyenne arrondie de compatibilité ; il
ne doit pas remplacer les valeurs individuelles. Exemple : 16 salades sur une
planche à 13 places par rang donnent 13 puis 3, pas deux fois 8.

La répartition est reconstruite en lecture : elle s'applique aux plantations
existantes et se recalcule après correction de longueur ou d'espacement.
Le journal, le stock et les quantités d'occupation ne sont jamais modifiés.
Les événements postérieurs à la date de référence sont exclus ; les dimensions
et espacements restent les valeurs courantes, comme avant cette évolution.

Limite conservatoire en attendant l'arbitrage sur récoltes et pertes : si la
quantité nette d'une ligne diffère de la somme de ses installations, cette
ligne conserve R2/R3. Aucune nouvelle règle de retrait des plants par rang
n'est introduite. Les confirmations de gestes restent inchangées.

## D'où vient l'espacement sur le rang (US-226)

`culture_config.espacement` est une **chaîne libre** (`String`, nullable), pas un
nombre : « 110 × 135 cm ». Elle date de la migration v8 et n'est renseignée que
par la v13, sur les cucurbitacées et une poignée d'entrées. Elle porte **deux**
distances, pas une.

La convention est vérifiable, et c'est ce qui rend sa lecture sûre : dans
`migrations/migration_v13.sql`, chaque entrée respecte `A × B cm` avec `A ≤ B` et
`surface_m2 = A × B ÷ 10000` (potimarron `110 × 135 cm` → 1,485 m² = la surface
de sa fiche ; courge `150 × 200 cm` → 3,000 ; pâtisson `100 × 120 cm` → 1,200).
**A est l'espacement sur le rang**, B l'écart entre rangs, `surface_m2` est le
contrôle.

La notation `A à B cm` du référentiel est également reconnue (ou `A a B cm`,
avec des espaces autour du séparateur). Elle désigne les mêmes **deux
distances**, pas une fourchette : le premier nombre reste l'espacement sur
le rang et le second sert au contrôle de surface. Les vraies fourchettes ne
doivent donc pas être encodées avec cette notation dans ce champ.

`app/services/espacement_rang.py` est le seul endroit qui lit cette chaîne. Il
accepte `A × B cm`, `A x B cm`, `A×B`, `A - B cm`, avec ou sans espaces, virgule
ou point décimal, et une valeur unique (« 50 cm ») lue comme l'espacement sur le
rang. Hors bornes (1 à 400 cm), vide, absente ou illisible : **« non renseigné »**,
jamais zéro, jamais une valeur de repli, jamais l'espacement d'une culture
voisine. Quand `surface_m2` est renseignée, l'écart avec `A × B ÷ 10000` est
vérifié à 10 % près ; au-delà, la valeur est retenue quand même et l'incohérence
est journalisée en `warning`, une fois par culture et par lecture — c'est une
anomalie de référentiel, pas une erreur d'exécution.

La dérivation ne coûte **aucune lecture supplémentaire** : elle se branche sur
`app/services/plan.attributs_par_culture()`, la lecture de `culture_config` que
`GET /plan` faisait déjà pour la surface au sol. Une fiche personnalisée au
potager (`potager_id` non nul, US-040) y prime sur la fiche globale de même nom.
Une **variété** n'a pas d'espacement propre : elle partage celui de sa culture,
sauf si elle existe comme fiche `culture_config` à part entière.

⚠️ Le référentiel est très inégalement rempli : au premier jour, beaucoup de
rangs afficheront « places non calculées ». C'est assumé.
`tools/controler_espacements.py` dit où porter l'effort — il ne liste que les
cultures **réellement présentes dans les potagers**, pas les 300 fiches du
catalogue, et ne modifie rien. Les valeurs de la v13 ont par ailleurs été
écrites pour la surface au sol en plein champ, pas pour une planche de potager :
⚖️ l'arbitrage A24 est de lire la chaîne existante plutôt que d'ouvrir une
colonne numérique déclarable, que le retour de terrain rouvrira s'il le faut.

## Les places d'un rang (US-227)

`places = ⌊ longueur_m × 100 ÷ espacement_rang_cm ⌋`, **au minimum 1**. La
longueur est celle de la **parcelle** (US-225) — tous ses rangs comptent donc sur
la même —, l'espacement celui de la **culture du rang** (US-226). Le calcul vit
dans `repartition_rangs.py`, dans la boucle qui numérote déjà les rangs : il ne
relit rien, `GET /plan` lui passe l'index de fiches culture qu'il avait déjà lu
(`attributs_par_culture`), et `test_us227_ca6_aucune_lecture_supplementaire`
compare le compte de requêtes avec et sans les places — il est identique, et
indépendant de la taille du plan.

**Trois cas d'échec, et seulement trois** (R11) : longueur absente — et alors
aucun rang de la parcelle n'est chiffré —, espacement absent, implantation en
surface (`m²`). Le rang porte `places = null`, jamais zéro, jamais une moyenne.
Une pépinière n'a pas de places non plus : on n'y plante pas au cordeau, elle
abrite des lots (R8).

| Champ du rang | Sens |
|---|---|
| `quantite_par_rang` | quantité propre à ce rang, pas la moyenne de sa ligne |
| `places` | ce que la géométrie du rang permet |
| `places_prises` | ce qui y tient **réellement**, plafonné à `places` |
| `places_restantes` | `places − prises`, jamais négatif |
| `depassement_places` | l'excédent, quand plus de pieds que de places |
| `espacement_rang_cm` | l'espacement retenu, pour que le chiffre soit traçable |
| `part_semee`, `metres_restants`, `depassement_metres` | un semis en ligne (`ml`) seulement |
| `longueur_m`, `capacite_exemple` | un rang **libre** seulement |

`places_prises + depassement_places` redonne toujours la quantité déclarée : le
plafonnement est ce qui se dessine sur la piste (US-228), il ne corrige aucune
donnée. La quantité dite par le jardinier reste dans `quantite_par_rang`
(US-198 / R3), intacte. Le dépassement de **rang** (trop de pieds sur un rang) et
le dépassement de **parcelle** (US-198 / R7, trop de rangs occupés) sont deux
choses distinctes, à ne pas confondre dans une même alerte.

Un **semis en ligne** (unité `ml`, US-199) n'a pas de places : un rang de carottes
n'a pas « 24 emplacements ». Il porte sa part semée (plafonnée à 1) et ses mètres
restants — et son propre dépassement, en mètres.

Un **rang libre** n'a pas de places non plus : elles dépendraient de ce qu'on y
mettrait. Il porte sa longueur et, si la parcelle abrite une culture à
l'espacement renseigné, une **capacité d'exemple nommée** (« 24 tomates ») prise
sur la première culture installée — jamais sur un espacement par défaut (A26).

⚖️ **Une place n'est pas un taux d'occupation** (RT13, arbitrage A25). Le bloc de
totaux gagne `parcelles_sans_longueur` et **rien d'autre** : aucun total de
places, aucun pourcentage de remplissage, ni par rang, ni par parcelle, ni en
pied de vue. L'occupation du Plan reste « N rangs occupés sur M déclarés ».
`test_us227_ca4_*` le tient sur la forme même de la réponse.

⚠️ **Une place n'est pas une promesse.** Un rang de 12 m à 50 cm donne 24 places
de tomates ; personne ne plante 24 tomates sur un rang de potager domestique. La
formule dit ce que la géométrie permet, pas ce qu'il est raisonnable de faire —
la fiche d'aide le dit au jardinier, faute de quoi le chiffre se lit comme un
conseil.

## Ce que le module ne fait pas

- **Il ne recalcule rien.** L'occupation, les séries (US-070) et la phase du
  moment (US-194) lui sont passées déjà calculées, ou lues ailleurs. Il est en
  lecture seule : aucune écriture, aucun stock, aucune projection, aucune
  confiance touchés.
- **Il ne dessine rien.** La **longueur** d'un trait est de la mise en forme
  (quantité par rang comparée au rang le plus fourni de la même unité) : elle
  appartient à la lib de la Vue plan (US-200).
- **Il ne dit rien de la surface.** « 1 rang libre » n'est pas « 1,2 m² libre » :
  `occupation_pct` reste le seul indicateur de surface, calculé comme avant, et
  le pourcentage en rangs ne mêle **jamais** une parcelle sans dénominateur.

## Deux limites assumées

- Des **semis échelonnés** d'une même variété forment une seule ligne : le plan
  d'occupation les regroupe, la répartition ne les sépare donc pas non plus.
- Une **récolte partielle ne libère pas de rang** tant que la ligne reste en
  place. Un rang de haricots reste occupé récolte après récolte ; un rang de
  laitues se libère quand la ligne quitte le plan d'occupation, c'est-à-dire
  quand il ne reste plus de pieds.

## Le dessin, et où il s'arrête (US-200)

La Vue plan (US-200 / US-228) représente les places connues par **sept symboles
proportionnels**, avec les emoji de culture de la maquette : le nombre de
repères pleins est `arrondi(prises / places × 7)`, borné à sept et au minimum
un dès qu'une place est prise. Aucun repère ne vaut un nombre de plants ; les
quantités exactes et la phase écrite restent visibles sur chaque rang. Sans
places calculables, le trait relatif reste utilisé, hachuré pour une surface.
Aucune largeur standard de 40 cm n'est introduite pour les semis en surface.
Une pousse en contour marque les places restantes ; graines, jeune pousse et
panier identifient les phases dans les pastilles et la légende. Le symbole de
culture apparaît aussi en tête de rang sur les cartes larges. Les rangs libres
ne proposent pas de lien « ajouter une culture ».

`GET /plan` est la **seule** lecture de la Vue plan : la répartition, la phase du
moment, les totaux et les cultures non localisées y sont déjà. Le front ne
recompte rien, il met en forme, et tout ce qui se calcule tient dans
`frontend/src/lib/planVue.js` — sans React, vérifié par `npm test`.

La **longueur** d'un trait est de la mise en forme, pas de l'agronomie : quantité
par rang ÷ quantité du rang le mieux fourni de la parcelle **à unité égale**,
plancher 12 %, plafond 100 %. Un trait de plants ne se compare jamais à un trait
de m², et la quantité est toujours écrite à côté — c'est ce qui rend l'échelle
inoffensive. En mode poquet, la longueur n'est pas relative du tout : douze
segments font la largeur entière, un segment par poquet, et le compte réel
s'écrit (« ×18 ») au-delà de douze.

Trois composants du design system portent ce dessin — `CartePlanParcelle`,
`RangPlan`, `TraitRang` — et prennent leur **palette** et leur **taille** en
paramètre : l'onglet Rotation les reprendra avec la sienne, l'onglet Parcelles
(US-222) avec le gabarit agrandi, sans qu'aucun des deux ait à les modifier.

## Une seule lecture

`repartition_du_plan()` fait **une** requête d'agrégation pour les rangs
d'installation de toutes les lignes, plus une lecture des lots de pépinière
seulement si le potager en compte une. Jamais une requête par parcelle ni par
ligne : `test_us198_ca5_le_nombre_de_lectures_ne_depend_pas_de_la_taille_du_plan`
tient cette garantie en comparant un petit plan à un plan trois fois plus fourni.

Tout est borné par la **date de référence** (US-030) : une installation
postérieure n'occupe pas encore de rang, et ses rangs ne sont pas comptés.

## Commandes

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_us198_repartition_rangs.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_us197_nb_rangs_parcelle.py -q   # le dénominateur déclaré
.\.venv\Scripts\python.exe -m pytest tests/test_us225_longueur_parcelle.py -q   # la longueur, base des places
.\.venv\Scripts\python.exe -m pytest tests/test_us226_espacement_rang.py -q     # l'espacement sur le rang
.\.venv\Scripts\python.exe -m pytest tests/test_us227_places_par_rang.py -q     # les places et ce qu'il en reste
.\.venv\Scripts\python.exe tools/controler_espacements.py                       # où manque l'espacement
```
