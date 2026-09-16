**ID :** US-068
**Titre :** Constituer le référentiel de calendrier cultural et de durées des cultures

**Story :**
En tant que jardinier
Je veux que l'application connaisse, pour chaque culture, ses périodes conseillées de semis, de plantation et de récolte ainsi que les délais de germination et de récolte attendus
Afin de savoir quand semer, quand mettre mes plants en place, dans combien de temps ma culture lèvera et quand je pourrai récolter, sans ressortir mon affiche de calendrier des semis

> **Amendement du 15/09/2026 — fenêtre de plantation.** Le modèle livré (v3.63.0) ne portait que trois fenêtres : semis en pépinière, semis en pleine terre, récolte. La **période de plantation** — mise en place définitive d'un plant — manquait. C'est un manque fonctionnel, pas un raffinement : pour une tomate, la frise disait « semis février-mars, récolte juillet-septembre » et restait muette sur le seul geste que la majorité des jardiniers amateurs font réellement (planter des plants, souvent achetés, en mai) ; pour l'ail, l'échalote ou la pomme de terre, qui ne se sèment pas, le calendrier était **vide par construction**. L'amendement est porté par les CA2 (modifié) et CA17 à CA30 ; l'arbitrage « le repiquage n'est pas une fenêtre autonome » est **révisé** (voir ci-dessous).

**Contexte fonctionnel :**
L'application ne sait rien du calendrier des cultures. `culture_config` ne porte aujourd'hui que le type d'organe de récolte, une description agronomique, l'espacement et la surface au sol par plant. La maquette 2026 affiche pourtant sur chaque tuile de culture une frise des douze mois (semis / plantation / récolte) et une durée de culture — toutes deux codées en dur dans ses données de démonstration.

Le modèle retenu n'est pas celui de la maquette mais celui des calendriers de semis du commerce, plus juste agronomiquement. Trois différences structurantes :

1. **La distinction n'est pas semis / plantation, mais semis à l'intérieur / semis à l'extérieur.** Une culture se sème soit en pépinière (godet, hors sol), soit directement en place — deux fenêtres différentes pour la même culture. ~~Le repiquage n'est pas une fenêtre autonome : il découle du semis en pépinière.~~ *Révisé le 15/09/2026 :* la **plantation** est une fenêtre à part entière, **indépendante** du semis en pépinière. Elle ne « découle » pas du semis : un plant mis en place peut venir de la pépinière du jardinier, d'une jardinerie, ou d'un organe de multiplication (caïeu, bulbe, tubercule, griffe, stolon, bouture). Déduire ses mois du semis en pépinière et du délai de repiquage serait une projection (US-070), jamais une fenêtre conseillée.
2. **Les fenêtres ne suffisent pas, il faut des durées.** Un calendrier de semis donne, pour chaque culture, le nombre de jours entre le semis et la germination, et entre le semis et la récolte. Ce sont ces durées, et non les fenêtres, qui permettront à **US-070** de recaler le calendrier sur la date réelle de semis du jardinier.
3. **Une culture porte plusieurs itinéraires culturaux.** « Chou-fleur culture précoce / d'été / d'automne / d'hiver », « Carotte d'été / Carotte d'hiver » ne sont pas des variétés mais des conduites de culture, chacune avec sa fenêtre et ses durées propres.

**Arbitrage produit — granularité :** le référentiel s'attache au couple **culture + itinéraire cultural**, jamais à la variété. Aucune source horticole réutilisable ne descend au niveau du cultivar ; y descendre reviendrait à tout saisir à la main. Une variété hérite de l'itinéraire sous lequel elle est conduite.

**Arbitrage produit — plantation (amendement du 15/09/2026) :** la plantation est la **mise en place définitive en parcelle** d'un plant ou d'un organe de multiplication — l'équivalent, dans le calendrier, du `type_action` `plantation` déjà enregistré. Elle se distingue de la **mise en godet** (repiquage en pépinière, `mise_en_godet`), qui n'a pas de fenêtre. Elle est **déclinée par zone climatique**, comme les semis : la date de mise en place est calée sur la dernière gelée, c'est même la phase la plus sensible au climat. Le **nom de la durée** `repiquage` (semis → plantation en place) est conservé en base : il ne change pas de sens.

**Arbitrage produit — climat :** le référentiel est **décliné par zone climatique**. Les fenêtres décalent de plusieurs semaines entre une côte océanique et un climat méditerranéen ; un référentiel unique serait faux pour la majorité des jardiniers. Les **durées**, elles, ne sont pas déclinées : le délai entre semis et récolte relève de la physiologie de la plante, pas de la latitude.

Cette US ne crée aucun écran et ne modifie aucun calcul existant : elle constitue une donnée de référence et la rend corrigeable. Ses consommatrices sont **US-070** (recalage sur les événements réels), l'écran Plan (US-060) et la vue « Cultures » du Lot E.

**Critères d'acceptance :**

*Structure du référentiel*
- [ ] CA1 : Une culture peut porter **un ou plusieurs itinéraires culturaux** nommés (ex. « standard », « culture précoce », « culture d'été », « culture d'automne », « culture d'hiver »). Une culture sans itinéraire nommé en possède un par défaut, implicite, qui n'oblige le jardinier à aucune saisie
- [ ] CA2 *(amendé le 15/09/2026)* : Chaque itinéraire porte **quatre fenêtres conseillées** indépendantes, chacune pouvant être vide : semis en pépinière (hors sol), semis en pleine terre, **plantation** (mise en place définitive), et récolte. Une culture qui ne se sème jamais en godet n'a pas de fenêtre pépinière ; une culture qui ne se plante jamais (semée en place) n'a pas de fenêtre de plantation ; une culture qui ne se sème pas (ail, pomme de terre) peut n'avoir qu'une fenêtre de plantation et une fenêtre de récolte ; une vivace peut n'avoir qu'une fenêtre de récolte
- [ ] CA3 : Chaque itinéraire porte deux **durées conseillées** : le délai entre le semis et la levée, et le délai entre le semis et la première récolte. Une troisième durée, le délai entre le semis et le repiquage, n'est renseignée que pour un itinéraire passant par la pépinière
- [ ] CA4 : Les durées sont exprimées en jours et peuvent être une fourchette (ex. « 70 à 90 jours ») ; les cultures qui n'en relèvent pas admettent une mention libre (ex. « vivace »). L'affichage ne doit jamais présenter une fourchette comme une date certaine
- [ ] CA5 : L'écartement entre plants **n'est pas ajouté** : `culture_config` porte déjà `espacement` et `surface_m2`, qui font foi. Le référentiel ne duplique pas cette donnée

*Déclinaison par zone climatique*
- [ ] CA6 : Les fenêtres du CA2 sont déclinées par **zone climatique** (a minima : océanique, continental, méditerranéen, montagnard). Les durées du CA3 ne le sont pas — elles sont communes à toutes les zones
- [ ] CA7 : Un potager porte **sa zone climatique**. Elle est pré-positionnée à partir de sa localisation lorsque celle-ci est connue, et reste **modifiable par le jardinier** — c'est lui qui connaît son microclimat, un fond de vallée n'a pas le calendrier du plateau voisin
- [ ] CA8 : Un potager sans zone renseignée reste pleinement fonctionnel : il lit les fenêtres d'une zone par défaut, sans erreur ni écran bloqué

*Alimentation et correction*
- [ ] CA9 : Le référentiel est **pré-rempli à la livraison** pour les cultures réellement présentes dans les données du potager, à partir d'une source de calendrier de semis identifiée. Le pré-remplissage n'écrase jamais une valeur déjà saisie par le jardinier
- [ ] CA10 : Le jardinier peut **consulter et corriger depuis le bot** les fenêtres et les durées d'une culture ; la commande confirme l'ancienne et la nouvelle valeur
- [ ] CA11 : Une correction saisie par un jardinier **ne modifie jamais** ce que lit un autre potager — contrairement à la famille botanique (US-067 / CA7), un calendrier est une préférence légitime, pas un fait botanique. La correction s'appuie sur le mécanisme de fiche personnalisée déjà présent sur `culture_config`
- [ ] CA12 : Le référentiel est retrouvé quelle que soit la casse et l'accentuation du nom de culture, cohérent avec la normalisation appliquée ailleurs aux noms de culture

*Robustesse et non-régression*
- [ ] CA13 : Une culture sans référentiel reste utilisable partout : les écrans affichent une frise neutre et des durées en tiret. **L'application n'invente jamais une période ni un délai**, ni côté serveur ni côté interface
- [ ] CA14 : La création d'une configuration de culture à la volée (déclenchée au premier événement sur une culture inconnue) **n'exige** ni fenêtre ni durée : le référentiel reste facultatif, sous peine de bloquer une saisie vocale sur une question horticole
- [ ] CA15 : Aucune régression sur les lectures existantes de `culture_config` — type d'organe de récolte, calcul de stock végétatif/reproducteur, écran Stocks, écran Statistiques et statistiques du bot conservent exactement leur comportement, vérifié par les tests existants passant sans modification
- [ ] CA16 : Des tests couvrent le pré-remplissage, une culture à plusieurs itinéraires, une culture sans fenêtre pépinière, la déclinaison par zone, un potager sans zone, la correction depuis le bot, son isolement par potager (CA11) et la non-régression du CA15

*Fenêtre de plantation — amendement du 15/09/2026*

Modèle et lecture
- [ ] CA17 : La fenêtre de plantation vit **dans la même structure** que les trois autres fenêtres (une par itinéraire, zone et phase, au mois, chevauchement de fin d'année admis) et obéit aux mêmes règles : absente = vide, jamais empruntée à une zone voisine (CA13), correction locale au potager (CA11), import incapable d'écraser une correction (CA9)
- [ ] CA18 : La fenêtre de plantation n'est **jamais calculée** à partir du semis en pépinière et du délai de repiquage, ni côté serveur ni côté interface. Une culture qui a une fenêtre de semis en pépinière et une durée de repiquage mais aucune fenêtre de plantation affiche une plantation **vide**
- [ ] CA19 : La présence d'une fenêtre de plantation **ne fait pas** d'un itinéraire un itinéraire « pépinière » : elle n'ouvre pas la durée de repiquage (CA3) et n'est pas un indice de semis en pépinière pour la proposition de contexte d'US-069 — un plant acheté se plante sans avoir été semé chez soi
- [ ] CA20 : Les **formes de lecture** existantes (consultation au bot, `GET /cultures/{culture}/calendrier`, lecture groupée de l'écran Plan) portent la plantation comme une phase de plus, dans l'ordre du geste : semis en pépinière, semis en pleine terre, plantation, récolte. L'ajout est **additif** : aucun champ existant ne change de nom ni de sens

Pré-remplissage — « pour toutes les cultures déjà présentes »
- [ ] CA21 : La fenêtre de plantation est **pré-remplie depuis la source déjà au socle** (Wind River Greens, `planting_calendar.csv`, colonnes `outdoor_transplant_start` / `outdoor_transplant_end`, aujourd'hui ignorées par l'adaptateur), avec la **même correspondance de zones déclarée** (océanique ← USDA 7, continental ← 6, méditerranéen ← 8, montagnard ← 4) et les mêmes règles de rejet que les autres fenêtres : jointure identifiant + catégorie, fenêtre à cheval sur l'année rejetée, ≥ 80 % des cultivars et ≥ 3 cultivars, médiane basse des bornes
- [ ] CA22 : Transposition de la règle de rejet n°6 : une fenêtre de plantation n'est retenue que si **au moins la moitié des fiches** de la culture décrivent un mode qui passe par une mise en place (élevé à l'abri, mixte, ou planté) — la source contre elle-même, sans avis agronomique
- [ ] CA23 : Révision de la règle de rejet n°1 : une culture **qui ne se sème pas** (ail, échalote, pomme de terre, fraise, framboise, menthe) n'est plus privée de toute fenêtre par principe — la plantation est précisément sa phase. Mais la fenêtre de plantation de la source ne lui est retenue **que si ses propres fiches ne la contredisent pas** ; une contradiction est écartée et motivée au compte rendu (mesure du 15/09/2026 : la source plante la framboise en mai-juin quand ses fiches disent « early spring or fall »). Ses fenêtres de **semis** et de **récolte** restent rejetées, pour le motif inchangé du CA9 d'origine
- [ ] CA24 : Le compte rendu de l'adaptateur **signale sans corriger** toute incohérence entre la fenêtre de semis en pépinière, la durée de repiquage et la fenêtre de plantation d'une même culture et d'une même zone (ex. plantation antérieure au semis augmenté du délai minimal). Aucune valeur n'est ajustée pour faire tomber l'incohérence
- [ ] CA25 : Le gabarit de rédaction interne `calendrier_redaction_interne.json` porte la clé `plantation` pour **chaque zone**, et couvre **toutes les cultures présentes dans `culture_config`** — et non plus les dix seules du périmètre initial — pour que chaque culture non couverte par la source ait sa case à remplir. Il reste livré **à null** : aucune fenêtre n'est produite par un modèle de langage, et une valeur déjà écrite par la source est préservée (CA9)
- [ ] CA26 : La couverture est **publiée** par l'adaptateur : cultures avec fenêtre de plantation, cultures écartées et motif, cultures sans aucune donnée source. Mesure préalable du 15/09/2026 (sur l'extrait versionné, avant règles 6 et 1 transposées) — ⚠️ à rejouer par l'adaptateur, pas à recopier :
  - **portée par la source, 100 % des cultivars, ≥ 3 cultivars** : tomate, aubergine, poivron, chou, brocoli, chou frisé, concombre, cornichon, melon, pastèque, basilic, persil, thym, fenouil, capucine (cornichon probablement écarté par le CA22 : 3 fiches sur 7 seulement décrivent une mise en place) ;
  - **portée mais base trop faible** : céleri, blette, coriandre, chou de Bruxelles, romarin, roquette ; **portée par 1 cultivar sur 15** : potiron ;
  - **portée mais culture non semée** (CA23) : fraise, framboise, menthe ;
  - **aucune donnée de plantation dans la source** : ail, échalote, pomme de terre, oignon, poireau, laitue, salade, courgette, courge, pâtisson, butternut, potimarron, haricot, haricot grimpant, carotte, radis, betterave, navet, petit pois, pois gourmand, mâche, épinard, ciboulette, oseille, mesclun — et fève, asperge, rhubarbe, épinard perpétuel, absentes de la source. Pour celles de ces cultures qui **se plantent** (ail, échalote, pomme de terre, oignon en bulbilles, poireau, laitue, courgette, courges, fraise, framboise, asperge, rhubarbe…), la plantation passe par le gabarit du CA25 ou par le bot ; pour celles qui se sèment en place (carotte, radis, navet…), la case reste vide et c'est juste

Correction au bot et à la dictée
- [ ] CA27 : `/calendrier fenetre <culture> [itinéraire] plantation <mois>` corrige la fenêtre de plantation de la zone du potager, avec la confirmation ancienne → nouvelle valeur du CA10. La consultation `/calendrier <culture>` affiche la ligne de plantation, vide comprise quand une autre phase est renseignée
- [ ] CA28 : Le **vocabulaire fermé** des phases proposé en boutons quand l'argument manque (US-172 / CA13) compte quatre entrées, dérivées de la même liste que le service — jamais recopiées
- [ ] CA29 : Une phrase dictée qui parle de plantation est **désambiguïsée par la nature de la valeur**, sans deviner : « plantation des poireaux : juin-juillet » (des mois) corrige la **fenêtre** ; « délai avant plantation des tomates : 42 à 56 jours » (des jours) corrige la **durée de repiquage**. Une phrase où la valeur ne tranche pas est traitée comme un argument manquant et demandée. « Quand planter les tomates ? » reste une consultation (règle `calendrier_quand`), et « quand ai-je planté les tomates ? » reste une question sur le journal (US-096)

Non-régression, corpus et tests
- [ ] CA30 : Aucune régression sur US-069 (proposition de contexte, statistiques par filière), sur le calcul de stock, sur `/stats` ni sur les corrections locales existantes. La fiche d'aide `calendrier-et-zone-climatique.md` est corrigée **dans la même livraison** (définition de terminé du corpus, US-099 / CA9) et `pytest tests/test_us099_corpus_fonctionnement.py` reste vert — ⚠️ la fiche nomme déjà « quand planter » dans ses termes associés, et le corpus de mesure route « avant de planter » vers la fiche rotation : les 65 questions doivent rester classées. Des tests couvrent : fenêtre de plantation lue par zone, plantation sans fenêtre pépinière (plants achetés), culture non semée avec plantation seule, absence de calcul du CA18, non-influence sur le contexte de semis du CA19, règles de rejet des CA21 à CA23, gabarit du CA25, correction et isolement par potager, désambiguïsation dictée du CA29

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et enregistrement (métadonnées de culture)
- Migration BDD requise : **oui** — référentiel de calendrier rattaché à `culture_config` (itinéraires, fenêtres déclinées par zone, durées), et zone climatique sur le potager, avec leur pré-remplissage
- Dépendances : aucune bloquante. **US-069** (distinction pépinière / pleine terre à la saisie) est nécessaire pour que la bonne fenêtre soit appliquée à un semis donné, mais le référentiel peut être constitué avant. **US-070** en est la consommatrice principale
- Voisinage : **US-067** enrichit la même table avec la famille botanique — US indépendante, mais même fichier de migration, à séquencer si les deux sont menées en parallèle
- Point de vigilance : `culture_config` n'est créée qu'à la demande, jamais pré-semée pour un catalogue — le pré-remplissage du CA9 ne doit pas créer de configuration pour des cultures que le jardinier n'a jamais utilisées
- Point de vigilance : la source du pré-remplissage doit être identifiée et sa réutilisation vérifiée avant développement (licence, format, couverture des cultures réellement suivies). C'est le principal risque de chiffrage de cette US
- Point laissé ouvert : l'édition du référentiel depuis l'interface web n'est **pas** traitée ici — elle relève de la vue « Cultures » du Lot E. Le bot suffit à satisfaire l'exigence « corrigeable sans livraison »

**Amendement du 15/09/2026 — migration :** **aucune**. `fenetre_culturale.phase` est un `VARCHAR(20)` sans CHECK de vocabulaire (arbitrage explicite de `migration_v46`, vocabulaire validé par le seul point d'écriture `calendrier_cultural.py`) et l'unicité `(itineraire_id, zone_climatique, phase)` accueille une quatrième phase telle quelle. À vérifier en implémentation contre le schéma de production, pas à supposer.

**Amendement du 15/09/2026 — impacts sur la chaîne d'exploitation :**

| Maillon | Ce qui change | Porté par |
|---|---|---|
| `app/services/calendrier_cultural.py` | `PHASES` passe à quatre (ordre du geste), libellé « Plantation », alias de saisie. ⚠️ `_ALIAS_ETAPES` mappe **aujourd'hui** « plantation » vers la **durée** `repiquage` : ce raccourci entre en collision avec la nouvelle phase — le lever ou le garder se décide avec le CA29. `_a_pepiniere` inchangé (CA19). Docstring du modèle | US-068 (CA17, CA19, CA20) |
| `app/services/adaptateur_wind_river.py` | `COLONNES_PHASE` reprend `outdoor_transplant_*` (le commentaire qui l'excluait tombe), règles 1 et 6 transposées, contrôle d'incohérence, couverture publiée | US-068 (CA21 à CA24, CA26) |
| `data/referentiel/wind_river_attributs.json` | Régénéré par l'adaptateur, jamais édité ; `_lisez_moi` à jour | US-068 (CA21) |
| `data/referentiel/wind_river_greens/SOURCE.md` | Ligne `planting_calendar.csv` (« `outdoor_transplant_*` non repris ») et section des six règles réécrites, comptes de fenêtres rejoués | US-068 (CA21, CA26) |
| `data/referentiel/calendrier_redaction_interne.json` | Clé `plantation` par zone, **toutes** les cultures de `culture_config`, livré à null | US-068 (CA25) |
| `app/services/import_referentiel.py` | Accepte la phase par le service (aucune liste propre à tenir) ; exemple de la docstring à compléter ; préservation d'une valeur déjà écrite inchangée | US-068 (CA17) |
| `bot.py` — `/calendrier` | Affichage de la ligne de plantation, `USAGE` et exemple d'erreur | US-068 (CA27) |
| `app/services/menu_commandes.py` | Vocabulaire des phases dérivé de `PHASES` : quatre boutons sans recopie ; `controler_parite()` reste vert | US-068 (CA28) |
| `app/services/interpreteur_commandes.py` | `_PHASES_DITES` et motif `calendrier_fenetre` : plantation ; désambiguïsation fenêtre / durée par la valeur ; corpus `tests/corpus/us172_commandes.csv` enrichi | US-068 (CA29) |
| `app/services/contexte_semis.py` | **Aucun changement de code attendu** — mais test garantissant qu'une fenêtre de plantation n'est pas un indice de pépinière | US-068 (CA19) / US-069 |
| `main.py` — `GET /cultures/{culture}/calendrier`, `GET /plan/calendriers` | Additif : une phase de plus dans `fenetres`, `frise` et `mois` | US-068 (CA20) |
| `calendriers_du_plan` + `MonthStrip.jsx`, `lib/calendrier.js`, `Plan.jsx` | La bande « plantation » **revient**, cette fois lue du référentiel : US-176 / CA3 (« aucune bande plantation ») devient faux. Quatrième teinte et règle de priorité quand deux phases tombent le même mois | **US-176** (amendée) |
| Recalage sur le réel | La fenêtre de plantation sert de « conseillé » pour une culture **plantée sans semis connu** (plants achetés, ail) | **US-070** (amendée) |
| Corpus `doc_app` | `calendrier-et-zone-climatique.md` (sections « Savoir quand semer », « Pourquoi semer en godet… », « Retrouver le calendrier… sur l'écran Plan ») et sa ligne dans `data/connaissance/doc_app/README.md` | US-068 (CA30) |
| `CLAUDE.md`, `PATCH_NOTES.md`, `VERSION`, épic | Syntaxe `/calendrier fenetre … <pepiniere\|pleine_terre\|plantation\|recolte>`, comptes « 272 fenêtres », arbitrage « Phases » de l'épic | Livraison de l'amendement |

**Amendement du 15/09/2026 — avancement (même jour, non commité) :**
- ✅ Faits : CA17 et CA20 (`PHASE_PLANTATION` dans `PHASES`, lecture additive), CA18 (par construction, testé), CA19 (test US-069), CA21 à CA24 (adaptateur), CA26 (compte rendu), manifeste `wind_river_attributs.json` régénéré — **64 fenêtres de plantation sur 16 cultures** : tomate, poivron, aubergine, chou, brocoli, chou frisé, concombre, melon, pastèque, basilic, persil, thym, fenouil, capucine, menthe, et **fraise** (nouvelle entrée, plantation seule, à relire). `/calendrier fenetre … plantation …` fonctionne au bot par le service ; `USAGE`, `CLAUDE.md`, `SOURCE.md`, fiche d'aide mis à jour
- ✅ Faits ensuite (même jour, prise en charge Développeur) :
  - **CA25** — `calendrier_redaction_interne.json` porte les quatre phases par zone pour **106 cultures** : les dix d'origine en tête, puis toutes celles semées par `migration_v5` / `v6` / `v13` (moins `courge butternut`, supprimée par `v13`) et celles du manifeste Wind River. ⚠️ La base de production n'étant pas lisible depuis le dépôt, « toutes les cultures de `culture_config` » est approché par ce qui y est semé ; une culture créée à la volée en production reste à ajouter à la main. Livré à null, testé
  - **CA27** — la consultation `/calendrier <culture>` dit « Plantation : — » dès qu'une autre fenêtre est renseignée ; correction `/calendrier fenetre … plantation …` confirmée ancienne → nouvelle valeur et isolée par potager, testée
  - **CA28** — déjà satisfait par construction (`menu_commandes` lit `PHASES`) ; question des boutons complétée « … plantation ou récolte ? », test ajouté
  - **CA29** — `interpreteur_commandes` : « plantation des poireaux : juin-juillet » et « période de plantation des tomates : mai à juin » → **fenêtre** ; « délai avant plantation des tomates : 42 à 56 jours » → **durée `repiquage`**. La règle elliptique (sans « période ») exige une plage de deux mois ou un séparateur, pour ne pas capter un geste daté (« plantation de 10 poireaux le 3 mai »). **Point ouvert tranché :** l'alias d'étape `plantation → repiquage` est **gardé** — au bot la sous-commande tranche, à la dictée la valeur. ⚠️ Écart assumé sur « une phrase où la valeur ne tranche pas est demandée » : elle n'est reconnue par **aucune** règle (ni devinée), mais le bot ne pose pas la question « fenêtre ou délai ? » — l'interpréteur ne sait compléter qu'un argument d'une commande déjà choisie, pas choisir entre deux commandes. Corpus `us172_commandes.csv` : +4 commandes, +2 phrases hors périmètre
  - **CA30** — suites US-068, US-069, US-099, US-172, US-176 vertes ; fiche d'aide mise à jour (plantation sur la frise, priorité)
  - Frontend (US-176 / CA3, CA3bis) livré, rendu vérifié à 375 px
- ⬜ Restent, décisions produit : durée plantation → première récolte, libellé « Semis → plantation en place », validation de `ZONE_USDA_PAR_ZONE`, relecture de l'entrée **fraise** (plantation seule, mai-juin en océanique)
- ⬜ **Aucune donnée de plantation dans la source** pour 17 des 32 cultures du manifeste : haricot, haricot grimpant, courgette, pâtisson, potiron, courge, carotte, radis, betterave, navet, cornichon, petit pois, pois gourmand, poireau, oignon, laitue, salade — à compléter à la main pour celles qui se plantent

**Amendement du 15/09/2026 — points ouverts, à trancher avant développement :**
- **Durée plantation → première récolte.** L'amendement pose la *fenêtre* de plantation, pas de *durée* depuis la plantation. Or `duree_culturale.recolte` compte depuis le **semis** : pour des plants achetés, US-070 ne pourra rien projeter. Constat mesuré déjà consigné dans `SOURCE.md` : `days_to_harvest` de la source compte **depuis la plantation** pour les cultures élevées à l'abri — c'est précisément pour ce motif qu'il a été rejeté sur tomate et poivron. Une étape `plantation_recolte` rendrait cette donnée utilisable. Recommandation : l'ajouter à cet amendement plutôt que de la découvrir en développant US-070
- **Libellé de la durée `repiquage`.** « Semis → repiquage » se confond avec la mise en godet. Recommandation : clé inchangée en base, libellé « Semis → plantation en place »
- **Correspondance des zones USDA.** La mesure donne une plantation de tomate en **avril-mai** en océanique (zone USDA 7). La plantation étant la phase la plus sensible à la dernière gelée, c'est elle qui éprouvera le plus durement la correspondance déclarée d'`ZONE_USDA_PAR_ZONE`, toujours « à valider par un humain »

**Estimation :** 8 points — **amendement du 15/09/2026 : + 3 points** (adaptateur et règles transposées, service, bot et interpréteur, gabarit, fiche d'aide, tests) ; + 1 point si la durée plantation → première récolte est retenue. L'affichage de la bande est chiffré dans US-176

**Scénario Gherkin :**
```gherkin
Scénario: Deux itinéraires pour une même culture
  Given une culture "chou-fleur" portant les itinéraires "culture précoce" et "culture d'hiver"
  When le jardinier consulte le calendrier du chou-fleur
  Then les deux itinéraires sont proposés avec leurs fenêtres et leurs durées propres

Scénario: Culture semée uniquement en pleine terre
  Given une culture "carotte" dont la fenêtre de semis en pépinière n'est pas renseignée
  When le jardinier consulte son calendrier
  Then seules les fenêtres de semis en pleine terre et de récolte sont affichées
  And aucune fenêtre de pépinière n'apparaît

Scénario: Fenêtres décalées selon la zone climatique
  Given une culture "courgette" dont le semis en pleine terre est conseillé en mai en zone continentale et en avril en zone méditerranéenne
  When un potager situé en zone méditerranéenne consulte ce calendrier
  Then la fenêtre de semis en pleine terre démarre en avril

Scénario: Durée identique quelle que soit la zone
  Given une culture "courgette" dont le délai semis → récolte conseillé est de 95 jours
  When deux potagers de zones climatiques différentes consultent ce calendrier
  Then les deux lisent le même délai de 95 jours

Scénario: Potager sans zone climatique renseignée
  Given un potager dont la zone climatique n'est pas renseignée
  When le jardinier consulte le calendrier d'une culture
  Then les fenêtres de la zone par défaut s'affichent
  And aucun écran n'est bloqué

Scénario: Correction propre à un potager
  Given deux potagers utilisant la culture "tomate"
  When le jardinier du premier avance sa fenêtre de semis en pépinière de mars à février
  Then son calendrier de la tomate démarre en février
  And celui du second potager reste inchangé

Scénario: Culture sans référentiel
  Given une culture "topinambour" sans aucune fenêtre ni durée renseignée
  When le jardinier enregistre un semis de topinambour
  Then l'événement est enregistré normalement, sans question sur le calendrier
  And les écrans affichent une frise neutre et des durées en tiret

Scénario: Fenêtre de plantation déclinée par zone
  Given une culture "tomate" dont la plantation est conseillée en mai-juin en zone continentale et en avril-mai en zone méditerranéenne
  When un potager situé en zone continentale consulte ce calendrier
  Then la fenêtre de plantation affichée est "mai-juin"
  And elle apparaît entre le semis en pépinière et la récolte

Scénario: Plantation jamais déduite du semis en pépinière
  Given une culture "aubergine" portant une fenêtre de semis en pépinière et une durée de repiquage
  And aucune fenêtre de plantation
  When le jardinier consulte son calendrier
  Then la fenêtre de plantation est vide
  And aucun mois de plantation n'est calculé

Scénario: Culture plantée qui ne se sème pas
  Given une culture "ail" sans fenêtre de semis
  And une fenêtre de plantation "octobre-novembre" saisie au gabarit de rédaction interne pour la zone océanique
  When un potager en zone océanique consulte ce calendrier
  Then seule la fenêtre de plantation est affichée
  And aucune fenêtre de semis n'apparaît

Scénario: Une fenêtre de plantation n'est pas un indice de pépinière
  Given une culture dont le référentiel porte une fenêtre de semis en pleine terre et une fenêtre de plantation
  And aucune fenêtre de semis en pépinière
  When le jardinier dicte un semis de cette culture sans préciser le contexte
  Then le bot propose "pleine terre"

Scénario: Correction de la plantation au bot
  Given un potager en zone océanique utilisant la culture "tomate"
  When le jardinier envoie "/calendrier fenetre tomate plantation mai-juin"
  Then le bot confirme l'ancienne et la nouvelle fenêtre de plantation
  And le calendrier de la tomate d'un autre potager reste inchangé

Scénario: Plantation dictée — fenêtre ou durée selon la valeur
  Given le jardinier dicte "plantation des poireaux : juin-juillet"
  Then la fenêtre de plantation des poireaux est proposée à la correction
  When le jardinier dicte "délai avant plantation des tomates : 42 à 56 jours"
  Then c'est la durée de repiquage des tomates qui est proposée à la correction
```

**Labels GitHub :** `us`, `backend`, `cultures`, `referentiel`
