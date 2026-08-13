**ID :** US-060
**Titre :** Refondre l'écran Plan (liste des parcelles et détail)

**Story :**
En tant que jardinier utilisant l'interface web
Je veux choisir une parcelle dans une liste et lire son détail à côté, aussi bien sur mon téléphone au potager que sur mon ordinateur
Afin de comparer d'un coup d'œil la charge de toutes mes parcelles, puis d'entrer dans le contenu de celle qui m'intéresse sans faire défiler une longue colonne unique

**Contexte fonctionnel :**
Deuxième US du Lot B de la refonte de l'interface web (voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §7.3). L'écran Plan (`views/Plan.jsx`) est aujourd'hui une pile de cartes de parcelle conçue pour le mobile uniquement : depuis US-053 qui a retiré la contrainte de largeur maximale, ces cartes s'étirent sur toute la largeur d'un écran d'ordinateur, ce qui donne un rendu dégradé (§7.4, point 2). L'écran porte par ailleurs 29 références aux alias de couleurs `--g-*` à migrer (§7.4, point 1).

La maquette (`web-screens.jsx`, `ScreenPlan`) ne conserve pas ce principe de cartes autonomes empilées : elle organise l'écran en **maître-détail**. Une colonne de gauche liste toutes les parcelles en lignes compactes et sélectionnables ; une colonne de droite affiche la fiche de la parcelle sélectionnée (surface, exposition, occupation) puis la carte « Cultures en place », où chaque culture devient une tuile portant sa famille, sa durée de culture et son calendrier des douze mois. C'est ce principe qui fait foi ici : la barre d'accent latérale colorée de l'écran actuel n'existe pas dans la maquette et disparaît, comme le CA8 d'US-061 arbitré au §5.9.

Il s'agit d'une refonte **strictement visuelle** : aucune donnée nouvelle produite par cette US, aucun appel serveur nouveau, aucune règle métier touchée.

**Périmètre du calendrier cultural — arbitrage produit.** Les tuiles de culture affichent une frise de douze mois dont la donnée n'existe pas en base. Cette US **fige la structure standard de la maquette** — trois phases (semis, plantation, récolte), douze mois, valeurs conseillées génériques portées par une table de correspondance provisoire côté interface — et **ne traite pas** le calendrier réel : référentiel corrigeable, zones climatiques, contexte de semis et recalage sur les événements de la parcelle relèvent en totalité de l'`docs/EPIC_CALENDRIER_CULTURAL.md` (US-068, US-069, US-070). La famille botanique suit le même principe : elle est lue de la table provisoire posée par US-061 (`frontend/src/lib/familles.js`) jusqu'à ce qu'**US-067** l'externalise. US-060 est donc livrable seule, sans aucune de ces US, et n'invente jamais une valeur pour une culture absente de la table.

**Critères d'acceptance :**

*Structure maître-détail*
- [x] CA1 : L'écran est organisé en deux zones conformément à la maquette — une **liste des parcelles** précédée de son intitulé de section « Mes parcelles · N » (N = nombre de parcelles réellement listées, filtre appliqué), et un **panneau de détail** consacré à la parcelle sélectionnée. Une seule parcelle est sélectionnée à la fois ; à l'ouverture de l'écran, c'est la première de la liste
- [x] CA2 : Chaque ligne de la liste porte, dans cet ordre : une **tuile d'emplacement carrée arrondie portant l'icône d'épingle**, l'icône étant colorée selon le taux d'occupation (le fond de la tuile, lui, bascule sur la couleur de carte quand la ligne est sélectionnée) ; le nom de la parcelle en serif ; la mention « N cultures · X m² » ; et le pourcentage d'occupation aligné à droite dans la couleur du taux. La ligne sélectionnée se distingue par un fond et une bordure de la couleur de marque, **sans ombre portée** — les lignes non sélectionnées gardant la leur
- [x] CA3 : La bascule entre la disposition à deux colonnes et l'**empilement de la liste au-dessus du détail** est pilotée par la largeur du conteneur (`container-type: inline-size` + `@container`) et non par un breakpoint d'écran (règle non négociable de `CLAUDE.md`). Les valeurs de la maquette font foi et ne sont pas retranscrites au jugé (cf. §5.9) : **une seule colonne sous 900 px de conteneur, puis une colonne de liste de largeur fixe 290 px et un détail fluide**, les deux colonnes alignées en haut (`align-items: start`). En empilement, la parcelle sélectionnée reste visible sans navigation supplémentaire — aucun écran de détail séparé, aucun bouton retour

*Panneau de détail*
- [x] CA4 : La fiche de la parcelle affiche son nom en titre serif **dans la couleur de marque**, puis ses caractéristiques sous forme de pastilles : la superficie en m² (teinte marque) et l'exposition, libellée « **Exposition** <valeur> » (teinte ambre) comme dans la maquette. La pastille « Sol » de la maquette est **omise** tant que le type de sol n'existe pas en base (colonne posée par US-058, non livrée) — elle n'est pas remplacée par un texte de substitution
- [x] CA5 : Sous un séparateur, la fiche affiche la ligne « Occupation de la surface » avec son infobulle explicative, le pourcentage occupé et la barre de progression du design system, tous deux dans la couleur du taux
- [x] CA6 : La carte « Cultures en place » porte en sous-titre le nombre de cultures et le **total de plants** de la parcelle, et à droite la légende des trois phases — Semis (bleu), Plantation (vert), Récolte (ambre). Le total de plants n'agrège que les cultures effectivement comptées en plants : une culture suivie dans une autre unité (m², graines) n'est jamais additionnée à ce total ni convertie pour l'y faire entrer
- [x] CA7 : Chaque culture de la parcelle est une tuile portant : le nom de la culture en serif, sa variété en italique à côté, la quantité alignée à droite, la ligne « famille · durée de culture », et le calendrier des douze mois (`MonthStrip` du design system). Les tuiles se répartissent selon la largeur du conteneur, aux paliers de la maquette : **une colonne, deux à partir de 640 px, trois à partir de 1400 px**

*Calendrier cultural — valeurs standard, périmètre figé*
- [x] CA8 : La frise affiche les **fenêtres conseillées génériques standard** de la culture — semis, plantation, récolte — et la ligne « famille · durée » lit les mêmes valeurs. Ces valeurs sont portées par une **table de correspondance provisoire côté interface**, sur le modèle de `frontend/src/lib/familles.js` posée par US-061 : elles ne dépendent ni de la parcelle, ni de la date des événements réels, ni de la zone climatique du potager
- [x] CA9 : Une culture absente de cette table s'affiche **en mode dégradé** et non en valeurs par défaut : frise entièrement neutre, sans aucun mois coloré, famille et durée en tiret (`—`), comme le prototype (`meta.fam || '—'`). **Aucune valeur horticole n'est inventée** — ni pour une culture inconnue, ni pour une culture partiellement renseignée
- [x] CA10 : Le **mois mis en évidence** sur la frise suit la **date de référence** de l'écran (US-030/031), jamais l'horloge du navigateur — sans quoi l'écran serait dans le passé et la frise dans le présent. `MonthStrip` (`frontend/src/components/ui/MonthStrip.jsx`) calcule aujourd'hui ce mois avec `new Date().getMonth()` : **cette US lui ajoute le paramètre correspondant**, avec repli sur le mois courant quand il n'est pas fourni, pour ne pas modifier les autres écrans qui l'utilisent
- [x] CA11 : La dette ainsi créée est **explicitement tracée** dans `docs/ANALYSE_REFONTE_UI_WEB_2026.md` au même titre que celle de `familles.js` : le calendrier réel (référentiel corrigeable, zone climatique, contexte de semis, recalage sur les événements de la parcelle, quatrième état « en croissance », durée restante avant récolte) relève d'`EPIC_CALENDRIER_CULTURAL` et **n'est pas dans le périmètre d'US-060**. La table provisoire disparaît avec US-068

*Non-régression — fonctions absentes de la maquette, toutes conservées*
- [x] CA12 : Sont conservés à l'identique : le code couleur d'occupation (vert sous 55 %, ambre de 55 à 79 %, rouge à partir de 80 %), le pourcentage de surface occupée, le compteur de cultures, l'exposition et la superficie, le nombre de pieds par culture, et la variété affichée à côté de la culture
- [x] CA13 : La pastille distinguant les cultures végétatives des reproductrices, absente de la maquette, est conservée sur la tuile de culture avec sa légende — c'est la clé de lecture du modèle de stock de l'application
- [x] CA14 : Une parcelle sans aucune culture reste identifiable : son badge « Libre » est conservé, sur sa ligne de liste comme dans son panneau de détail, et sa sélection n'affiche pas une carte « Cultures en place » vide
- [x] CA15 : Les observations (US-039) restent accessibles aux deux niveaux — sur la parcelle sélectionnée et sur chaque couple culture + variété — avec leur compteur, leur ouverture à la demande et le fait qu'un seul panneau reste ouvert à la fois
- [x] CA16 : Le sélecteur de date de référence, le filtre par culture (filtrant à la fois sur le nom de parcelle et sur les cultures et variétés qu'elle contient) et le bandeau « parcelles actives / cultures en place » sont conservés et utilisent les composants migrés par US-059. Quand le filtre exclut la parcelle sélectionnée, la sélection bascule sur la première parcelle encore listée
- [x] CA17 : Les tuiles de sous-navigation « Vue plan » et « Rotation » restent en l'état (écran « à venir » posé par US-053) — leur contenu fonctionnel est hors périmètre, il relève du Lot G

*Correction fonctionnelle assumée*
- [x] CA18 : La quantité de la tuile de culture est affichée **avec son unité**. C'est un **ajout**, pas une non-régression : l'écran actuel (`views/Plan.jsx`) affiche `nb_plants` nu, et la maquette une valeur nue elle aussi, alors que `GET /plan` renvoie déjà l'unité par culture (`utils/parcelles.py`). Une culture semée en m² reste donc affichée en m², jamais convertie en nombre de plants

*Dette technique*
- [x] CA19 : L'écran ne contient plus aucun alias de couleur `--g-*` ni classe `bg-g-*` / `text-g-*` / `border-g-*` — uniquement les tokens sémantiques de la nouvelle palette (29 occurrences soldées, cf. §7.4)
- [x] CA type (US avec impact visuel/UI) : Le rendu de l'écran correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille de navigation), US-059 (composants transverses migrés). **Aucune dépendance à US-067, US-068, US-069 ni US-070** : le calendrier et la famille sont figés en valeurs standard par les CA8 à CA11. Ces US reprennent la main **ensuite** — US-067 remplace la table de familles, US-068 le référentiel de calendrier, US-070 le recalage sur le réel et le quatrième état de la frise, en réutilisant le paramètre de mois ajouté au CA10
- Écarts assumés avec la maquette, à reporter dans `docs/ANALYSE_REFONTE_UI_WEB_2026.md` sur le modèle du §5.9 :
  - **supprimé** : barre d'accent latérale de l'écran actuel (absente de la maquette)
  - **omis** : pastille « Sol » (donnée inexistante en base)
  - **conservés bien qu'absents de la maquette** : pastille végétatif/reproducteur, badge « Libre », sélecteur de date de référence, filtre culture, bandeau de métriques, observations à deux niveaux
  - **ajoutés par rapport à la maquette** : l'unité sur la quantité (CA18) ; le mois mis en évidence piloté par la date de référence au lieu du mois codé en dur du prototype (`CUR_MONTH = 7`, CA10) ; le total de plants restreint aux cultures comptées en plants (CA6)
  - **artefact de prototype non repris** : la maquette ouvre l'écran sur la **deuxième** parcelle (`useState(WPARCELLES[1].id)`) pour montrer un détail plus fourni ; l'écran livré ouvre sur la première (CA1)
- ~~Cohérence de backlog à solder : `docs/ANALYSE_REFONTE_UI_WEB_2026.md` chiffre encore US-060 à **5 points** (tableau des US et totaux du Lot B) alors que l'US en porte **8** depuis son relevé~~ — soldé à la livraison (§7.2 : 8 points, totaux du Lot B recalculés)
- Écarts constatés à l'implémentation, tracés au §5.10 : la table de calendrier provisoire est `frontend/src/lib/calendrier.js` ; deux corrections de confort ont été assumées au-delà de la non-régression stricte — une parcelle retenue par **son nom** garde toutes ses cultures dans le détail (le filtre s'appliquait auparavant aussi à son contenu, et la parcelle s'affichait vide), et une exposition enregistrée sous la chaîne littérale `NULL` est omise au lieu d'afficher « Exposition NULL »

**Estimation :** 8 points *(relevé de 5 : le maître-détail avec état de sélection, le panneau de détail et les tuiles de culture ne sont pas un réhabillage des cartes existantes)*

**Scénario Gherkin :**
```gherkin
Scénario: Maître-détail sur grand écran
  Given l'utilisateur consulte l'écran "Plan" avec cinq parcelles enregistrées
  When il affiche l'application sur un écran de 1440px
  Then la liste des cinq parcelles occupe la colonne de gauche
  And le détail de la première parcelle occupe la colonne de droite

Scénario: Changement de parcelle sélectionnée
  Given l'utilisateur consulte l'écran "Plan"
  When il choisit la parcelle "Serre" dans la liste
  Then la ligne "Serre" est mise en évidence
  And le panneau de détail affiche la superficie, l'exposition, l'occupation et les cultures de la "Serre"

Scénario: Empilement sur mobile sans navigation supplémentaire
  Given l'utilisateur consulte l'écran "Plan" sur un téléphone de 375px
  When la page s'affiche
  Then la liste des parcelles s'affiche en premier, puis le détail de la parcelle sélectionnée en dessous
  And aucun bouton retour n'est nécessaire pour revenir à la liste

Scénario: Non-régression du code couleur d'occupation
  Given une parcelle occupée à 85 % de sa surface
  When l'utilisateur consulte l'écran "Plan"
  Then l'icône de sa ligne, son pourcentage et sa barre de progression sont en rouge

Scénario: Calendrier standard d'une culture connue
  Given une courgette plantée dans la parcelle affichée
  When l'utilisateur consulte cette parcelle
  Then la frise colore les mois conseillés standard de la courgette
  And la ligne famille · durée affiche "Cucurbitacée · 50-60 j"

Scénario: Culture sans métadonnée horticole
  Given une culture "topinambour" absente de la table de correspondance
  When l'utilisateur affiche la parcelle qui la contient
  Then la tuile affiche le nom, la variété et la quantité de la culture
  And la ligne famille · durée affiche des tirets
  And le calendrier des douze mois reste neutre, sans mois coloré

Scénario: La frise suit la date de référence
  Given l'utilisateur consulte l'écran "Plan" avec une date de référence reculée au 15 mars
  When une tuile de culture s'affiche
  Then le mois mis en évidence sur sa frise est mars

Scénario: Quantité affichée dans son unité de saisie
  Given une carotte semée sur 2 m² dans la parcelle affichée
  When l'utilisateur consulte cette parcelle
  Then la tuile affiche "2 m²" et non un nombre de plants
  And le total de plants du sous-titre "Cultures en place" ne compte pas cette culture

Scénario: Non-régression des observations à deux niveaux
  Given la parcelle sélectionnée porte deux observations et l'une de ses cultures en porte une
  When l'utilisateur ouvre le panneau d'observations de la culture
  Then seule la note de cette culture s'affiche, et le panneau de la parcelle se referme

Scénario: Filtre excluant la parcelle sélectionnée
  Given la parcelle "Serre" est sélectionnée
  When l'utilisateur filtre sur une culture absente de la "Serre"
  Then la "Serre" disparaît de la liste
  And le détail affiché est celui de la première parcelle encore listée
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `plan`
