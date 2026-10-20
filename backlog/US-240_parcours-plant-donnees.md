**ID :** US-240
**Titre :** Lire le parcours du plant — les étiquettes de chaque lot par stade et par emplacement, les compteurs, les dormants et le bon moment pour semer
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application sache, pour chaque lot, quelle part en est encore en graines, quelle part en godet, où chacune se trouve et ce qui presse, et quelles cultures je peux semer avec les graines que j'ai
Afin que l'écran Parcours me montre la vérité de ma pépinière sans rien inventer ni rien recalculer de son côté

**Contexte fonctionnel :**
L'onglet Parcours (US-218) range les lots dans un kanban **emplacement × stade**. Une case ne contient pas des lots mais des **étiquettes** : une par couple (lot, stade, emplacement) (A31). Un lot à moitié repiqué est à la fois « en levée » (ses graines restantes) et « en godet » (ses plants repiqués) : il a deux étiquettes, au même numéro, avec un repère « 1/2 », « 2/2 ».

US-214 calcule déjà les échéances de chaque lot, l'action suggérée, la dormance, l'ordre d'urgence et la liste des cultures « à semer ». Cette US **étend** cette lecture sans la rouvrir : elle découpe les lots en étiquettes, range chaque étiquette dans sa colonne, ajoute les compteurs de l'écran, sort les dormants du kanban et rend « à semer » utile en le limitant aux graines en stock.

Elle ne crée aucun geste et ne change aucun stock. Elle n'ajoute aucune lecture : tout passe par `GET /pepiniere/lots`.

Conception : `docs/EPIC 9-12 - PLAN CULTURES PEPINIERE/pepiniere/01_VUE_PARCOURS.md` — cette US porte le **calcul** des règles P4, P5, P6, P8, P9, P11, P12, P14 à P19, P22 et P23 ; US-218 en porte l'affichage.

**Critères d'acceptance :**

*Les étiquettes*
- [ ] CA1 : `GET /pepiniere/lots` ajoute un bloc **`parcours`**, sans retirer ni renommer aucun champ existant (US-214 / CA7) : l'onglet Lots et la fiche du lot fonctionnent sans changement
- [ ] CA2 : Chaque lot en cours, non dormant, donne **une étiquette par couple (stade, emplacement)** qu'il occupe (A31, P14) : une étiquette « en levée » s'il a des **graines non soldées** (semées, ni repiquées, ni soldées par une levée terminée ou une clôture), une étiquette par emplacement où il a des **godets disponibles**. Un lot non coupé a une étiquette sans repère ; un lot coupé en a plusieurs, numérotées « rang sur total » dans l'ordre du parcours (levée d'abord)
- [ ] CA3 : Tant qu'US-241 n'est pas livrée, tous les godets d'un lot sont à son emplacement courant (US-210, US-211) : un lot n'est coupé que par le stade. Une fois US-241 livrée, les godets sont répartis par emplacement sans changer ce contrat
- [ ] CA4 : Chaque étiquette porte : le lot (identifiant, numéro, culture, variété), son repère de fragment, son **stade**, son **emplacement** (ou aucun), ses **quantités** (graines, levés, godets), son **état** (P15), son **échéance** (jours, retard, fourchette, début de la règle) et une **mention** éventuelle (« déplacés le 12 oct. », « 12 déjà en godet ») (P17, P19)

*La colonne de chaque étiquette*
- [ ] CA5 : La colonne suit la table P9, à la date de référence :
  - **En levée** : graines non soldées ;
  - **En godet** : godets disponibles en pépinière chaude, de type inconnu ou sans emplacement, avant le compte à rebours d'endurcissement, mise en terre non atteinte ou non calculable ;
  - **Endurcissement** : compte à rebours de 7 jours commencé (chaude ou inconnue), **ou** godets en pépinière froide, qui s'endurcissent sur place sans compte à rebours (A35, US-214 / CA4) ;
  - **Prêt à sortir** : fourchette de mise en terre prévue atteinte ou dépassée, quel que soit le type de pépinière
- [ ] CA6 : **État** de l'étiquette (P15) : *repiquer_retard*, *sortir_retard*, *sortir_bientot* (mise en terre dans les 15 jours), *endurcir* (avec J n sur 7), *endurcit_sur_place*, *levee_en_cours*, *en_cours*, *duree_inconnue*. Les seuils (15 jours, 7 jours) sont des décisions produit consignées au même endroit que celles d'US-214
- [ ] CA7 : **Échéance des graines restantes** d'un lot déjà en partie repiqué : **aucune** échéance de repiquage, aucun retard (A33) ; l'état est *levee_en_cours* et le fragment est signalé comme soldable par « Noter la levée (terminée) » (US-212 / CA7). La dormance d'US-214 s'applique au lot comme avant
- [ ] CA8 : **Sans la donnée requise, pas d'échéance** et la raison est rendue (« délai semis → godet non renseigné pour la carotte »), jamais une valeur par défaut (RT2) ; l'état est *duree_inconnue* et la fourchette est absente. La fin de fourchette d'un fragment vient de `echeances.sortie_prevue` (conservé du premier travail sur US-218, A39) et de la fourchette de repiquage d'US-214 (P18)
- [ ] CA9 : Dans chaque case (emplacement × colonne), les étiquettes sont rendues dans l'**ordre d'urgence** d'US-214 / CA6 : retards du plus grand au plus petit, échéances de la plus proche à la plus lointaine, puis sans échéance (P22)

*Les lignes, les compteurs, les dormants*
- [ ] CA10 : Le bloc liste **toutes les pépinières** du potager — nom, type (chaude, froide, non renseigné), superficie — dans l'ordre des parcelles, **vides comprises** (P11). Les étiquettes sans emplacement sont rattachées à « aucun » (P12)
- [ ] CA11 : **Compteurs** (P4) : *à repiquer* (étiquettes en état de repiquage, dont en retard), *à sortir* (*sortir_retard* et *sortir_bientot*), *endurcit* (*endurcir* et *endurcit_sur_place*), *à semer* (cultures, CA13), *dormants* (lots). Chaque compteur dit s'il contient un retard
- [ ] CA12 : Les lots **dormants** d'US-214 ne donnent **aucune étiquette** ; ils sont rendus à part, avec leurs jours sans geste, leur date de semis et ce qui leur reste (graines non levées, godets disponibles), du plus ancien geste au plus récent (P23, A37)

*Le bon moment pour semer*
- [ ] CA13 : Une culture est **à semer** si sa fenêtre de semis en pépinière est ouverte à la date de référence (règle actuelle d'US-214 / CA8, même évaluation que la confiance), qu'aucun lot n'est en cours pour elle, **et que des graines de cette culture sont en stock** (A34, P5). Elle porte : la ou les **variétés en stock**, la fenêtre en clair, ses bornes, les **jours restants** jusqu'au dernier jour du dernier mois de la fenêtre, et la **part écoulée** de la fenêtre (P6)
- [ ] CA14 : Les cultures qui remplissent les deux premières conditions **sans graines en stock** sont rendues dans une liste à part, par nom seulement (P8)
- [ ] CA15 : Le stock de graines est lu par la règle de stock existante (celle de l'écran Stocks), sans nouvelle règle de calcul ; une variété à zéro n'est pas « en stock »

*Contraintes*
- [ ] CA16 : Une seule requête, au plus une lecture météo (cache d'US-182) et une lecture du stock de graines groupée pour toutes les cultures candidates ; aucune requête par lot, par étiquette ni par culture (RT6)
- [ ] CA17 : Lecture seule : aucun geste n'est créé, aucun stock ne change ; `GET /godets`, `GET /stats` et l'écran Stocks rendent les mêmes valeurs avant et après (US-214 / CA10)
- [ ] CA18 : Isolation entre potagers : un lot, une pépinière ou un stock d'un autre potager n'apparaît jamais

*Définition de terminé*
- [ ] CA19 : Des tests couvrent chaque ligne de la table des colonnes, chaque état, la coupure par le stade, un lot sans semis rattaché, le fragment de graines restantes sans échéance (A33), la pépinière froide (A35), la date de référence passée, une pépinière vide, un lot sans emplacement, les dormants hors kanban, chaque compteur, « à semer » avec et sans graines en stock, une variété à zéro, les jours restants en fin de mois et en fenêtre à cheval sur l'année, l'isolation entre potagers
- [ ] CA20 : La fiche de domaine `docs/domaines/pepiniere.md` consigne la table des colonnes, la règle des fragments, les états et leurs seuils, A33, A34 et A35
- [ ] CA21 : La fiche `pepiniere-par-lot.md` explique au jardinier pourquoi un lot peut avoir deux étiquettes, pourquoi des graines restantes n'ont plus d'échéance, et pourquoi une culture dans sa fenêtre n'est pas proposée sans graines en stock (US-099 / CA9)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (lecture de la pépinière)
- Migration BDD requise : **non**
- Dépendances : **US-214** (échéances, dormance, ordre d'urgence, à semer), **US-212** (graines soldées, levée terminée), **US-210** et **US-211** (emplacement courant), **US-208** (type de pépinière) — toutes livrées. **US-241** enrichit la répartition des godets par emplacement sans changer le contrat
- Impact tokens : zéro (aucun appel au modèle)
- Point de vigilance : le calcul vit dans le **même module** que les échéances d'US-214 ; aucune règle n'est dupliquée dans le front (RT7). Les gestes proposés sur une étiquette ne sont **pas** calculés ici : ils suivent la règle de la fiche du lot (US-216 / CA15)
- Point de vigilance : **reproducteur vs végétatif** — sans objet en pépinière ; le type d'organe ne joue qu'après la mise en terre
- Conception : `pepiniere/01_VUE_PARCOURS.md` § 3 et § 6 (contrat indicatif du bloc `parcours`)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Un lot coupé par le stade
  Given le lot 23, tomate cerise semée en serre chaude, 16 graines semées, 12 repiquées en godet, 4 non soldées
  When je lis la pépinière au 19 octobre
  Then le lot 23 a deux étiquettes : "en levée" (4 graines, 1/2) et "en godet" (12 godets, 2/2)
  And l'étiquette "en levée" n'a aucune échéance de repiquage

Scénario: Un godet en pépinière froide
  Given le lot 21, poivron, 6 godets au châssis froid, mise en terre prévue du 10 au 20 novembre
  When je lis la pépinière au 19 octobre
  Then son étiquette est dans la colonne "Endurcissement", état "s'endurcit sur place", sans compte à rebours

Scénario: Prêt à sortir en retard
  Given le lot 30, laitue, 20 godets en serre, mise en terre prévue du 1er au 10 octobre
  When je lis la pépinière au 19 octobre
  Then son étiquette est dans la colonne "Prêt à sortir", état "sortir en retard", 9 jours de retard
  And le compteur "à sortir" signale un retard

Scénario: À semer limité aux graines en stock
  Given la fenêtre de semis en pépinière de la laitue d'hiver et de la mâche est ouverte, aucun lot en cours pour elles
  And j'ai des graines "Merveille d'hiver" en stock et aucune graine de mâche
  When je lis la pépinière au 19 octobre
  Then la laitue d'hiver est à semer, variété "Merveille d'hiver", 12 jours restants
  And la mâche est seulement dans la liste "sans graines en stock"

Scénario: Un lot dormant
  Given le lot 7, sans godet, 5 graines non levées, aucun geste depuis 201 jours
  When je lis la pépinière
  Then le lot 7 n'a aucune étiquette
  And il est dans la liste des dormants avec "5 graines non levées"

Scénario: Une pépinière vide
  Given un potager avec une serre et un châssis froid, aucun lot au châssis
  When je lis la pépinière
  Then le châssis froid est listé parmi les pépinières, sans étiquette
```

**Labels GitHub :** `us`, `backend`, `api`, `pepiniere`
