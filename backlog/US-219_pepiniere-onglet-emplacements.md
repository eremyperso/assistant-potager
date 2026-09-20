**ID :** US-219
**Titre :** Afficher l'onglet « Emplacements » de la Pépinière — ce que contient chaque pépinière, chaude ou froide
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier qui a plusieurs pépinières — une serre chauffée, un châssis froid, une étagère dans la véranda
Je veux voir ce que contient chacune d'elles
Afin de savoir ce qui lève au chaud, ce qui s'endurcit au froid, et ce que j'ai encore à y loger

**Contexte fonctionnel :**
La v2 (§ 3b) dessine cet onglet pour « répondre à « ai-je encore de la place dans la serre ? » », en reprenant l'analyse du 17/07 : une carte par pépinière, « SERRE » et « Châssis froid », avec les lots qui s'y trouvent. Elle précise : « « Emplacements » n'a de sens qu'à partir de deux pépinières déclarées — il peut n'apparaître que dans ce cas. »

Elle y dessinait aussi des **plaques** et des alvéoles (« Plaque 1 : tomate cerise #131, 60 alvéoles », « 2 plaques sur 3 ») en les marquant « à trancher avant de la dessiner en haute fidélité ». Arbitrage A12 : l'emplacement s'arrête à la **parcelle pépinière** ; la plaque n'existe nulle part et reste hors périmètre. L'onglet dit donc ce qu'il y a dans chaque pépinière — lots, graines, godets — **sans prétendre mesurer la place** qu'ils prennent.

Il repose sur le type de pépinière (US-208), l'emplacement courant de chaque lot (US-210) et ses déplacements (US-211).

⚖️ **Conception avant implémentation (RT9)** : wireframe v2 § 3b pour la structure, sans les plaques ; maquette haute fidélité gelée avant le code.

**Critères d'acceptance :**
- [ ] CA1 : L'onglet « Emplacements » n'apparaît que si le potager compte **au moins deux pépinières** ; avec une seule, sa pastille est dans la barre de l'onglet « Aujourd'hui » (US-215 / CA2)
- [ ] CA2 : Une **carte par pépinière**, dans l'ordre des parcelles : nom, type (« pépinière chaude », « pépinière froide », « type non renseigné »), superficie ou « superficie non renseignée », puis le nombre de lots, de graines en germination et de godets qui s'y trouvent à la date de référence. Une pépinière vide dit « libre »
- [ ] CA3 : Dans chaque carte, les lots sont groupés par stade — *en germination*, *en godet* — avec leur numéro, leur culture, leur variété, leur quantité et leur échéance courte (US-214). Dans une pépinière froide, un lot en godet porte « s'endurcit ici »
- [ ] CA4 : Une dernière carte « **emplacement non renseigné** » regroupe les lots dont l'emplacement n'est pas connu (US-210 / CA5), avec la phrase à dire au compagnon pour le préciser ; elle n'apparaît que si elle n'est pas vide
- [ ] CA5 : **Aucune mesure de place** : ni pourcentage, ni plaques, ni alvéoles ; l'onglet le dit une fois (« la place occupée dans une pépinière n'est pas mesurée »), sans rien estimer (RT2)
- [ ] CA6 : Un appui sur un lot ouvre sa **fiche** (US-216) ; « Ce qu'il y a à faire ici → » ouvre l'onglet « Aujourd'hui » filtré sur cette pépinière (US-215 / CA9). Arrivé du Plan par la carte d'une pépinière (US-201 / I5), l'onglet s'ouvre sur cette pépinière, mise en évidence et focalisée
- [ ] CA7 : Une seule lecture : `GET /pepiniere/lots` rend, en plus des lots, la liste des pépinières du potager — nom, type, superficie — pour qu'une pépinière vide s'affiche ; aucune requête par pépinière
- [ ] CA8 : Mise en page en container queries : cartes côte à côte quand la largeur le permet, empilées à 375 px, sans défilement horizontal
- [ ] CA9 : Accessibilité : chaque carte est une région nommée par sa pépinière ; type et stade sont écrits, jamais portés par la seule couleur
- [ ] CA10 : Le regroupement par pépinière et par stade vit dans une lib sans React couverte par `npm test`
- [ ] CA11 : Une page de contrôle visuel rejoue : deux et trois pépinières, une vide, une de type inconnu, des lots sans emplacement, un lot déplacé du chaud au froid, thème sombre
- [ ] CA12 : La fiche `pepiniere-par-lot.md` décrit ce que montre chaque pépinière et ce que l'onglet ne mesure pas (US-099 / CA9) ; l'analyse du 17/07 note que le cas « est-ce que j'ai encore de la place dans ma serre ? » reçoit une réponse partielle (contenu, pas place)
- [ ] CA13 : Le rendu correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA, écran Pépinière)
- Migration BDD requise : **non**
- Dépendances : **US-208** (type), **US-210** (emplacement courant), **US-215** (barre d'onglets) ; US-211 (déplacements) pour que l'onglet reste juste quand les lots bougent ; US-214 (échéances), US-216 (fiche du lot)
- Impact tokens : zéro
- Point de vigilance : sans US-211, un lot sorti de la serre y resterait affiché ; livrer cet onglet **après** US-211 est recommandé
- Point de vigilance : la **plaque** est un sujet ouvert, pas oublié. Si le besoin se confirme, il fera l'objet d'une US de modèle (emplacement dans l'emplacement), puis d'une évolution de cet onglet
- Wireframe : `maquette front/wireframes/Wireframes v2 - Plan Cultures Pepiniere.html`, § 3b et l'encart « Ce que ça demande au modèle »

**Estimation :** 3 points (hors conception)

**Scénario Gherkin :**
```gherkin
Scénario: Deux pépinières
  Given la serre, pépinière chaude, abrite le lot 131 en germination et le lot 128 en germination
  And le châssis froid, pépinière froide, abrite le lot 119 en godet
  When j'ouvre l'onglet "Emplacements"
  Then la carte de la serre liste les lots 131 et 128 sous "en germination"
  And la carte du châssis froid liste le lot 119 sous "en godet", avec "s'endurcit ici"

Scénario: Une seule pépinière
  Given le potager ne compte que la serre comme pépinière
  When j'ouvre la Pépinière
  Then l'onglet "Emplacements" n'est pas affiché
  And la pastille de la serre est dans la barre de l'onglet "Aujourd'hui"

Scénario: Pépinière vide
  Given le châssis froid ne contient aucun lot
  When j'ouvre l'onglet "Emplacements"
  Then la carte du châssis froid dit "libre"

Scénario: Lots sans emplacement
  Given le lot 140 a été semé sans parcelle
  When j'ouvre l'onglet "Emplacements"
  Then une carte "emplacement non renseigné" liste le lot 140 avec la phrase à dire au compagnon

Scénario: Venir du Plan
  Given j'appuie sur la carte du châssis froid dans la Vue plan
  Then l'onglet "Emplacements" s'ouvre, la carte du châssis froid mise en évidence
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `pepiniere`
