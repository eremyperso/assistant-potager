**ID :** US-218
**Titre :** Afficher l'onglet « Parcours » de la Pépinière — chaque lot rangé par emplacement et par stade, ce qui presse et ce qu'il est temps de semer
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

> ♻️ **Réécrite le 19/10/2026.** La version précédente (« onglet Calendrier », frise annuelle des lots,
> 5 points) est abandonnée avant livraison : la piste C du wireframe « Calendrier pépinière » la remplace.
> Elle reste lisible dans l'historique git de ce fichier. Le nom du fichier est conservé pour ne pas
> casser les liens (plan des épics, Jira). Cette US **absorbe US-219** (onglet Emplacements) et
> **remplace l'écran d'US-215** (onglet Aujourd'hui, livré). Conception :
> `docs/EPIC 9-12 - PLAN CULTURES PEPINIERE/pepiniere/01_VUE_PARCOURS.md` (règles **P1 à P30**,
> arbitrages **A30 à A40** dans `pepiniere/README.md`).

**Story :**
En tant que jardinier qui fait le tour de sa serre et de son châssis
Je veux voir d'un seul regard où se trouve chaque lot, à quel stade il en est, ce qui est en retard et ce qu'il est encore temps de semer
Afin de faire le bon geste au bon lot, sans passer d'un onglet à l'autre pour recouper la même information

**Contexte fonctionnel :**
La Pépinière a reçu trois façons de lire les mêmes lots : « Aujourd'hui » (la liste par urgence, US-215), « Calendrier » (la frise, cette US dans sa première version) et « Emplacements » (US-219). Le wireframe « C · Le parcours du plant — v2 » montre qu'un **kanban emplacement × stade** les porte toutes : les lignes sont les pépinières, les colonnes les stades (en levée, en godet, endurcissement, prêt à sortir), chaque case contient des **étiquettes** qui disent le lot, sa quantité, son échéance et son geste. La frise annuelle ne gardait qu'une utilité, dire « le bon moment pour semer », que l'onglet porte dans une bande dédiée.

La Pépinière passe donc à **deux onglets** : **Parcours**, ouvert par défaut, et **Lots**, l'écran actuel d'US-061, inchangé dans cette US (il sera repensé en registre plus tard). La fiche du lot (US-216) est la porte commune des deux.

Toutes les données — étiquettes, colonnes, compteurs, cultures à semer, dormants — sont calculées par le serveur (**US-240**). Cette US les **range et les dit** ; elle ne calcule aucune échéance (RT7).

⚖️ **Conception avant implémentation (RT9)** : wireframe `Wireframes - Calendrier pepiniere - C v2.html` (projet Claude Design *potager 2026*) pour la structure, maquette haute fidélité gelée avant le code, sur les données réelles du potager de dev.

**Critères d'acceptance :**

*Les onglets et la barre*
- [ ] CA1 : La Pépinière n'a plus que deux onglets : **« Parcours »**, ouvert par défaut, puis **« Lots »** (écran d'US-061 inchangé, numéro de lot compris). « Aujourd'hui », « Calendrier » et « Emplacements » n'existent plus. Le dernier onglet visité est rouvert pendant la session. Une intention ou une adresse qui visait « Aujourd'hui » ou « Emplacements » ouvre « Parcours » (P1)
- [ ] CA2 : La barre porte la **date de référence**, modifiable ; la changer relit l'écran une fois (RT3, P2)
- [ ] CA3 : La barre porte le sélecteur **« Toutes les pépinières ▾ »**, qui ne garde que la ligne choisie et filtre le tiroir d'autant. Avec une seule pépinière, il cède la place à sa pastille « SERRE · 2,5 m² · pépinière chaude » (US-215 / CA2), « type non renseigné » dit tel quel. Un filtre posé par une intention (US-201 / I5 amendée) s'affiche en pastille retirable (P3)
- [ ] CA4 : La barre porte les **compteurs** rendus par US-240 : « N à repiquer » (teinte d'alerte s'il y a un retard), « N à sortir », « N endurcit », « N à semer », « N dormants » ; un compteur à zéro n'est pas affiché. Un appui sur « à repiquer », « à sortir » ou « endurcit » met en évidence les étiquettes concernées et atténue les autres, un second appui retire l'effet ; « à semer » mène à la bande, « dormants » ouvre le tiroir (P4)

*La bande « Le bon moment pour semer »*
- [ ] CA5 : Une tuile par culture **à semer** (US-240) : culture, « reste N j », jauge de la part de fenêtre écoulée, fenêtre en clair (« fenêtre 1er sept.–31 oct. »), variété(s) en stock, bouton « **+ Semer** » (P6)
- [ ] CA6 : « + Semer » **dépose** dans la file (US-224) le geste pré-rempli : semis en pépinière, culture, variété quand une seule est en stock, date de référence ; la pépinière est demandée par le compagnon. Le dépôt est confirmé par la notification d'US-215 / CA7 bis, sans quitter l'écran (P7)
- [ ] CA7 : Les cultures dans leur fenêtre **sans graines en stock** sont repliées en une phrase : « Aussi dans leur fenêtre, sans graines en stock : mâche, oignon blanc · Voir les 2 › » ; « Voir » les déplie, sans bouton « Semer ». Sans culture à semer ni repliée, la bande n'est pas affichée (P8)

*Le kanban*
- [ ] CA8 : Quatre colonnes, toujours affichées dans cet ordre — **En levée**, **En godet**, **Endurcissement**, **Prêt à sortir** — chacune avec un motif, un mot (lisibles en niveaux de gris, RT4) et le compteur de ses étiquettes. La colonne de chaque étiquette vient d'US-240 ; le front ne la recalcule pas (P9, P10)
- [ ] CA9 : **Une ligne par pépinière**, dans l'ordre des parcelles, **même vide** ; en tête : nom, type écrit, nombre de lots, d'étiquettes et d'alertes. Une case vide dit « vide » ; la case « Prêt à sortir » vide dit le prochain départ (« Rien à sortir aujourd'hui. Prochain : Poireau #24, le 23 oct. ») (P10, P11)
- [ ] CA10 : Une dernière ligne **« Sans emplacement »**, hachurée, n'apparaît que si elle n'est pas vide ; ses étiquettes portent « **Ranger dans…** », qui dépose un déplacement sans destination (US-241) ; tant qu'US-241 n'est pas livrée, l'étiquette affiche la phrase à dire au compagnon (« le lot 23 est dans la serre ») (P12)
- [ ] CA11 : **Aucune mesure de place** dans une pépinière : ni pourcentage, ni plaque, ni alvéole (A12, P13)

*L'étiquette*
- [ ] CA12 : Chaque étiquette porte : numéro, culture, variété, repère **« 1/2 », « 2/2 »** si le lot est coupé (par le stade, et par l'emplacement dès US-241) ; un **en-tête d'état en mot**, teinté selon la légende (*Repiquer — retard*, *Sortir — retard*, *Sortir bientôt*, *Endurcir · J n sur 7*, *S'endurcit sur place*, *Levée en cours*, *En cours*, *Durée ?*) ; le **grand chiffre** de l'échéance (« +6 j », « 8 j », « J3 », « ? », ou rien quand aucune échéance n'est attendue) ; les **quantités** en clair ; une **ligne de dates** en clair (P14 à P17, P19)
- [ ] CA13 : La **règle** de l'étiquette montre les jours écoulés, la fourchette attendue hachurée et la date de référence en trait rouge ; en endurcissement, sept cases ; sans fourchette (« Durée ? »), pas de règle (P18)
- [ ] CA14 : Deux **gestes** au plus, l'action suggérée d'US-214 en premier, choisis par la **même règle que la fiche du lot** (US-216 / CA15, une seule règle pour les deux) : *Repiquer*, *Noter la levée* ou *Noter la levée (terminée)* sur un fragment de graines restantes (A33), *Mettre en terre* **seulement si le fragment a des godets**, *Ranger dans…*. Chaque bouton dépose le geste dans la file (US-224) avec la notification d'US-215 / CA7 bis ; la liste est relue une fois au retour sur l'onglet (US-224 / CA22), sans squelette ni perte du filtre (P20)
- [ ] CA15 : Sur une étiquette « Durée ? », la phrase à dicter pour renseigner le délai (US-213) est affichée et copiable, pas en bouton (P20)
- [ ] CA16 : **Fragments liés** : au survol, au focus clavier ou au toucher d'une étiquette coupée, toutes les étiquettes du même lot s'éclairent (contour épais) et chacune porte un lien vers l'autre (« #23 · voir 2/2 › ») (P21)
- [ ] CA17 : Dans une case, les étiquettes suivent l'ordre rendu par US-240 : retards du plus grand au plus petit, échéances de la plus proche à la plus lointaine, puis sans échéance (P22)
- [ ] CA18 : Deux lots de la même culture sans délai connu ont **deux étiquettes**, une par lot (A36, écart assumé avec le wireframe)

*Le tiroir des dormants*
- [ ] CA19 : Les lots **dormants** sont hors du kanban, dans un tiroir en bas : « Tiroir des lots dormants · N lots, aucun geste depuis plus de 60 jours », mention « comptés dans les stocks tant qu'ils ne sont pas réglés ». Chaque lot porte numéro, culture, jours sans geste, variété, date de semis, ce qui reste, et au plus deux gestes : **Clôturer**, et **Mettre en terre** seulement s'il a des godets disponibles (A37). Tiroir vide : il n'est pas affiché (P23, P24)

*La fiche du lot*
- [ ] CA20 : Un appui sur une étiquette (hors bouton) ou sur un lot du tiroir ouvre la **fiche du lot** (US-216) : panneau à côté du kanban quand le conteneur fait au moins 900 px, plein écran en dessous. La fermer rend le kanban intact — défilement, filtre, onglet de stade (RT12, P25)

*Téléphone*
- [ ] CA21 : À 375 px, la bande s'empile (une ligne par culture, « + Semer » à droite, cibles de 44 px) ; le kanban devient **quatre onglets de stade** (« Levée », « Godet », « Endurci », « Prêt »), avec compteur et point d'alerte ; dans un onglet, les étiquettes sont groupées par pépinière puis « Sans emplacement ». L'onglet ouvert par défaut est le premier qui contient une alerte, sinon le premier non vide (P26, P27)
- [ ] CA22 : Un fragment rangé dans un autre onglet de stade est signalé par un lien (« 6 au châssis froid › ») qui y mène ; le tiroir est un bouton « Ouvrir › » ; gestes à **48 px** (écran de terrain, US-216 / CA11) ; aucun défilement horizontal ; container queries (P28)

*États, droits, accessibilité*
- [ ] CA23 : Aucun lot en cours : la bande seule, puis « Aucun lot en cours ». Chargement : squelette ; échec : message et relance. Un membre en lecture seule voit tout, sans aucun bouton de geste (RT11)
- [ ] CA24 : Le kanban est un tableau sémantique (lignes = pépinières, colonnes = stades) ; chaque étiquette est focalisable et nommée (« Lot 23, tomate cerise, fragment 1 sur 2, en levée, 4 graines ») ; chaque bouton nomme son lot (« Repiquer le lot 28 ») ; état et échéance sont écrits, jamais portés par la seule couleur ou le seul motif (P30)
- [ ] CA25 : **Une seule lecture** : `GET /pepiniere/lots`, enrichie par US-240 ; aucune lecture des calendriers côté front, aucune requête par lot ni par pépinière (RT6)

*Définition de terminé*
- [ ] CA26 : Le rangement en lignes et colonnes, le libellé des états, le grand chiffre, la règle, les liens entre fragments et l'onglet de stade par défaut vivent dans une lib sans React couverte par `npm test` ; le choix des gestes **réutilise** celui de la fiche du lot, sans le dupliquer (RT7)
- [ ] CA27 : Une page de contrôle visuel rejoue : nominal (deux pépinières et sans emplacement), une seule pépinière, pépinière vide, lot coupé par le stade, lot coupé par l'emplacement, lot en retard, « Durée ? », pépinière froide, aucun lot en cours, aucune culture à semer, tiroir vide, lecture seule, chargement, échec, thème sombre — à 375, 768 et 1280 px (P29)
- [ ] CA28 : Les amendements du 19/10/2026 d'**US-216** (CA1 réécrit, CA19 : fragments dans la fiche) et d'**US-201** (I5 : Parcours filtré sur la pépinière) sont livrés et testés avec cette US
- [ ] CA29 : Le code des onglets retirés (« Aujourd'hui », frise du « Calendrier », « Emplacements ») est supprimé ; ce qui est réutilisé (dépôt de geste, notification, pastille, lecture seule) est déplacé, pas copié. Les pages de contrôle visuel des onglets retirés sont supprimées
- [ ] CA30 : La fiche `pepiniere-par-lot.md` décrit l'onglet Parcours — colonnes, étiquettes, fragments, bande à semer, tiroir — et ne parle plus des onglets « Aujourd'hui », « Calendrier » ni « Emplacements » ; toute fiche du corpus qui les citait est corrigée (US-099 / CA9) ; le guide utilisateur suit
- [ ] CA31 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Pépinière), gestes déposés dans la file du compagnon
- Migration BDD requise : **non**
- Dépendances : **US-240** (données du parcours, bloquante) ; **US-241** conseillée, pas bloquante (fragments par emplacement, « Ranger dans… ») ; US-216 (fiche du lot), US-224 (file des gestes), US-215 (lib, dépôt, notification, pastille réutilisés), US-212 (levée), US-213 (phrase du délai) — toutes livrées
- Impact tokens : zéro
- Impact design system : composant d'étiquette (en-tête d'état, grand chiffre, règle, gestes) et sa règle de jours ; onglets de stade à 375 px. `MonthStrip` n'est **pas** touché
- Point de vigilance : **régression visible** — l'onglet « Aujourd'hui », livré en v3.88.0, disparaît. Les patch notes l'annoncent et disent où chaque chose est passée (urgences → compteurs et en-têtes d'étiquette, emplacements → lignes du kanban)
- Point de vigilance : le travail de la première version (frise) est mis de côté (A39) ; seul le champ serveur `sortie_prevue` est conservé, et sert à la règle des étiquettes
- Point de vigilance : **reproducteur vs végétatif** — sans objet en pépinière ; le type d'organe ne joue qu'après la mise en terre
- Wireframe : `Wireframes - Calendrier pepiniere - C v2.html` (Claude Design, projet `10f5afa7-58f8-4eb0-8dae-ca5834dfff59`)

**Estimation :** 8 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Ouvrir la Pépinière
  Given un potager avec une serre chaude et un châssis froid, et des lots en cours
  When j'ouvre la Pépinière
  Then l'onglet "Parcours" est ouvert
  And je vois une ligne "Serre chaude", une ligne "Châssis froid" et les colonnes "En levée", "En godet", "Endurcissement", "Prêt à sortir"
  And il n'y a pas d'onglet "Aujourd'hui", "Calendrier" ni "Emplacements"

Scénario: Un lot en retard de repiquage
  Given le lot 28, chou frisé semé le 1er octobre, repiquage attendu entre le 11 et le 13 octobre
  When j'ouvre "Parcours" au 19 octobre
  Then son étiquette est dans "Serre chaude" × "En levée", en-tête "Repiquer — retard", grand chiffre "+6 j"
  And le compteur "1 à repiquer" est en teinte d'alerte
  When j'appuie sur "Repiquer"
  Then le geste est déposé dans la file, une notification le confirme et je reste sur l'écran

Scénario: Un lot coupé par le stade
  Given le lot 23, tomate cerise, avec 12 godets et 4 graines encore en levée
  When je survole son étiquette "En godet"
  Then son étiquette "En levée" s'éclaire aussi
  And chacune porte un repère "1/2" ou "2/2" et un lien vers l'autre

Scénario: Le bon moment pour semer
  Given la fenêtre de semis en pépinière de la laitue d'hiver est ouverte jusqu'au 31 octobre, aucun lot en cours, des graines "Merveille d'hiver" en stock
  And la mâche est dans sa fenêtre mais sans graines en stock
  When j'ouvre "Parcours" au 19 octobre
  Then la bande montre "Laitue d'hiver · reste 12 j · Merveille d'hiver" avec "+ Semer"
  And la mâche est seulement citée dans "Aussi dans leur fenêtre, sans graines en stock"

Scénario: Un lot dormant
  Given le lot 7, tomate cœur de bœuf, sans godet, 5 graines non levées, aucun geste depuis 201 jours
  When j'ouvre "Parcours"
  Then le lot 7 n'est dans aucune colonne
  And il est dans le tiroir des dormants avec le seul geste "Clôturer"

Scénario: Au téléphone
  Given un écran de 375 px et un lot en retard dans la colonne "En levée"
  When j'ouvre "Parcours"
  Then je vois quatre onglets de stade, "Levée" ouvert et marqué d'un point d'alerte
  And aucun défilement horizontal n'est possible

Scénario: Lecture seule
  Given je suis membre du potager en lecture seule
  When j'ouvre "Parcours"
  Then je vois les étiquettes, la bande et le tiroir
  And aucun bouton de geste n'est proposé
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `pepiniere`, `mobile`
