**ID :** US-215
**Titre :** Afficher l'onglet « Aujourd'hui » de la Pépinière — ce qu'il y a à faire, lot par lot, du plus urgent au plus calme
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux ouvrir la Pépinière sur ce que j'ai à faire aujourd'hui — repiquer, endurcir, mettre en terre, semer — avec les lots en retard en premier
Afin de faire le tour de ma serre et de mon châssis sans rien oublier, et de lancer chaque geste d'un appui

**Contexte fonctionnel :**
L'écran Pépinière actuel (US-061) est un tableau de bord : une carte par lot, sa frise des trois stades, son anneau de plants, groupées par famille. La v2 en fait un **poste de travail** à quatre onglets — **Aujourd'hui** · Lots · Calendrier · Emplacements — et ouvre sur « Aujourd'hui », « l'écran qu'on ouvre en passant ». La v1 le garantit : « Les cartes actuelles (3 stades, donut, décomposition) restent telles quelles sous l'onglet Lots. Le calendrier est un second regard sur les mêmes données, pas un remplacement. »

Cette US crée l'onglet « Aujourd'hui » et la barre d'onglets, sur les échéances calculées par US-214. Les onglets « Calendrier » (US-218) et « Emplacements » (US-219) s'ajoutent quand ils sont livrés ; aucun onglet vide n'est montré entre-temps.

⚖️ **Conception avant implémentation (RT9)** : wireframe v2 § 3 pour la structure, maquette haute fidélité gelée avant le code.

**Critères d'acceptance :**

*Structure de l'écran*
- [ ] CA1 : La Pépinière gagne une barre d'onglets : **« Aujourd'hui »**, ouvert par défaut, puis **« Lots »**, qui porte l'écran actuel **inchangé** (cartes, groupes par famille, recherche, tri, repères, bandeaux), numéro de lot en plus (US-209). « Calendrier » et « Emplacements » n'apparaissent que livrés ; « Emplacements » seulement si le potager compte au moins deux pépinières (US-219)
- [ ] CA2 : Dans la barre de l'écran : la date de référence (RT3), le champ « Aller au lot n° » (US-209), et, quand le potager ne compte qu'une pépinière, sa pastille « SERRE · 2,5 m² · pépinière chaude » (type non renseigné dit tel quel)

*Le bandeau des quatre réponses*
- [ ] CA3 : Quatre cartes, lues dans le résumé d'US-214 : **À repiquer** (lots et plants, avec les retards nommés : « chou frisé +6 j · tomate cerise dans 3 j »), **À endurcir** (lots, avec leur compte à rebours), **Prêts pour le plan** (plants, avec les rangs libres par parcelle quand le Plan les connaît), **À semer** (cultures dont la fenêtre de semis en pépinière est ouverte et qui n'ont aucun lot en cours). Une carte à zéro dit « rien » plutôt que de disparaître
- [ ] CA4 : La carte « À repiquer » prend la teinte d'alerte quand un lot est en retard. Un appui sur « À repiquer », « À endurcir » ou « Prêts pour le plan » filtre la liste sur ces lots ; un second appui retire le filtre. Dans « À semer », le nom d'une culture ouvre sa **fiche culture** (US-207), d'où la fiche calendrier permet d'enregistrer le semis

*La liste des lots*
- [ ] CA5 : Les lots en cours sont listés dans **l'ordre d'urgence** d'US-214. Chaque ligne porte : numéro, culture, variété, « semé le … · N j · emplacement » ; « N semés → N levés » avec le taux de levée (US-212), ou les godets disponibles ; l'échéance en clair (« Repiquage +6 j », « Repiquage dans 3 j », « Endurcissement J+3 sur 7 », « En pépinière froide », « Dormant ») ; le bouton de l'**action suggérée**
- [ ] CA6 : Une ligne en retard est mise en évidence et son bouton est principal ; les lots **dormants** sont en fin de liste, atténués, avec « Clôturer »
- [ ] CA7 : Les boutons préparent le geste pré-rempli (US-196) — lot, culture, variété, date : *Repiquer* (mise en godet, nombre de levés proposé s'il est connu), *Mettre en terre* (plantation, godets disponibles proposés, parcelle demandée), *Clôturer* (le geste qui solde le lot : perte en pépinière de ses godets restants, ou levée terminée s'il n'a que des graines en germination). *Noter la levée* ouvre la fiche du lot sur son compteur (US-216). Aucune écriture dans la PWA
- [ ] CA8 : Un appui sur une ligne ouvre la **fiche du lot** (US-216) : en panneau à côté de la liste quand le conteneur fait au moins 900 px, en plein écran en dessous. La fermer rend la liste intacte (US-195 / CA8)
- [ ] CA9 : Recherche sur la culture, la variété et le numéro ; filtre d'emplacement, posé notamment par une intention venue du Plan (US-201 / I5), affiché en pastille retirable

*États, droits, mise en page*
- [ ] CA10 : Aucun lot en cours : « Aucun lot en cours » et le bandeau, « À semer » compris. Échéance incalculable : la ligne dit pourquoi (« délai non renseigné »), sans ordre inventé. Chargement : squelette ; échec : message et relance
- [ ] CA11 : Un membre en lecture seule voit tout, sans aucun bouton d'action (RT11)
- [ ] CA12 : À 375 px, chaque ligne devient une carte de deux ou trois lignes, bouton d'action compris, cibles de 44 px ; aucune colonne n'est perdue, aucun défilement horizontal. Container queries (règle « Responsive »)
- [ ] CA13 : Une seule lecture (`GET /pepiniere/lots`, US-214) ; au retour sur l'application après un geste confirmé au compagnon, la liste est relue une fois (US-196 / CA12)
- [ ] CA14 : Accessibilité : la liste est une liste ou un tableau sémantique ; chaque bouton nomme son lot (« Repiquer le lot 128 ») ; l'échéance est écrite, jamais portée par la seule couleur

*Définition de terminé*
- [ ] CA15 : Le libellé des échéances, le filtre du bandeau et le choix du geste de chaque bouton vivent dans une lib sans React (extension de `frontend/src/lib/pepiniere.js`) couverte par `npm test`
- [ ] CA16 : Une page de contrôle visuel rejoue : lots en retard, à repiquer, en endurcissement, en pépinière froide, dormant, sans échéance calculable, aucun lot, une et deux pépinières, lecture seule, thème sombre
- [ ] CA17 : La fiche `pepiniere-par-lot.md` décrit l'onglet « Aujourd'hui » et ses quatre réponses (US-099 / CA9)
- [ ] CA18 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Pépinière)
- Migration BDD requise : **non**
- Dépendances : **US-214** (échéances et résumé), **US-216** (fiche du lot), **US-196** (gestes pré-remplis) ; US-209 (numéro), US-212 (levée), US-207 (fiche culture) ; US-198 pour les rangs libres de « Prêts pour le plan »
- Impact tokens : zéro
- Impact design system : réutilise `Badge`, `Btn`, `SearchField`, `InfoBanner`, `DateRefPicker` ; nouveaux composants `CarteReponsePepiniere` et `LigneLot`
- Point de vigilance : l'onglet « Lots » est **strictement inchangé** hormis le numéro de lot ; c'est une condition de la v1
- Point de vigilance : la vignette de QR code dessinée en tête de ligne par la v2 n'apparaît qu'avec US-221 (option)
- Wireframe : `maquette front/wireframes/Wireframes v2 - Plan Cultures Pepiniere.html`, § 3 et ses notes

**Estimation :** 5 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Ouvrir la Pépinière le matin
  Given le lot 128 est en retard de repiquage de 6 jours et le lot 131 à repiquer dans 3 jours
  And le lot 119 est en endurcissement, J+3 sur 7
  When j'ouvre la Pépinière
  Then l'onglet "Aujourd'hui" est affiché
  And la carte "À repiquer" annonce 2 lots, en teinte d'alerte
  And le lot 128 est en tête de liste avec le bouton principal "Repiquer"

Scénario: L'onglet Lots est inchangé
  When j'ouvre l'onglet "Lots"
  Then je retrouve les cartes par lot, groupées par famille, avec leur frise des trois stades
  And chaque carte porte son numéro de lot

Scénario: Lancer un repiquage
  Given le lot 128 a 40 levés notés
  When j'appuie sur "Repiquer" sur la ligne du lot 128
  Then mon compagnon s'ouvre sur une mise en godet du lot 128, 40 plants proposés

Scénario: Clôturer un lot dormant
  Given le lot 103, basilic, dormant, 6 godets restants
  When j'appuie sur "Clôturer"
  Then mon compagnon s'ouvre sur une perte en pépinière de 6 plants du lot 103

Scénario: Filtrer depuis le bandeau
  When j'appuie sur la carte "À endurcir"
  Then la liste ne montre que les lots en endurcissement

Scénario: Venir du Plan
  Given j'ai appuyé sur la carte de la serre dans la Vue plan, avec une seule pépinière
  Then l'onglet "Aujourd'hui" s'ouvre filtré sur la serre
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `pepiniere`
