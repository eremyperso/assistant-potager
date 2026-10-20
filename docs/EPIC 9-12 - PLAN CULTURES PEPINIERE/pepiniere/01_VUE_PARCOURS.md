# Conception fonctionnelle — onglet « Parcours » de la Pépinière

> Source : wireframe « C · Le parcours du plant — v2 » (19/10/2026). Arbitrages A30 à A41 :
> [README.md](README.md) § 3. Règles transverses RT1 à RT14 : [plan des épics](../PLAN_EPICS_9_A_12.md) § 4.
> Les règles de ce document sont numérotées **P1 à P30** pour que les CA des US les citent.

## 1. À quoi répond l'onglet

Ouvert par défaut, l'onglet « Parcours » répond, à la date de référence, à quatre questions du
jardinier devant ses barquettes :

1. **Qu'est-ce qui presse ?** — les étiquettes en retard ou proches de l'échéance, en couleur et en mots ;
2. **Où est chaque lot, et à quel stade ?** — une ligne par pépinière, une colonne par stade ;
3. **Que puis-je semer maintenant ?** — la bande « le bon moment pour semer » ;
4. **Qu'est-ce que j'ai oublié ?** — le tiroir des dormants.

Il ne répond pas à « combien ai-je obtenu de ce lot ? » : c'est le registre « Lots » (`03_VUE_LOTS.md`).

## 2. Anatomie de l'écran (desktop, 1280 px)

| Zone | Contenu | Règles |
|---|---|---|
| **Z1 — Barre d'onglets** | « Parcours » (actif) · « Lots » | P1 |
| **Z2 — Barre d'outils** | Date de référence ▾ · « Toutes les pépinières ▾ » · compteurs | P2 à P4 |
| **Z3 — Bande « Le bon moment pour semer »** | Une tuile par culture à semer, puis les cultures repliées | P5 à P8 |
| **Z4 — En-tête du kanban** | Quatre colonnes de stade, chacune avec sa pastille de motif et son compteur | P9, P10 |
| **Z5 — Lignes d'emplacement** | Une ligne par pépinière, puis « Sans emplacement » | P11 à P13 |
| **Z6 — Étiquettes** | Une étiquette par (lot, stade, emplacement) | P14 à P22 |
| **Z7 — Tiroir des dormants** | Les lots dormants, en bas, hors kanban | P23, P24 |
| **Z8 — Fiche du lot** | Panneau latéral (US-216) ouvert par une étiquette | P25 |

## 3. Règles

### Barre et compteurs

- **P1** — La Pépinière n'a plus que deux onglets : **Parcours**, ouvert par défaut, et **Lots**.
  « Aujourd'hui », « Calendrier » et « Emplacements » disparaissent. Le dernier onglet visité est
  rouvert pendant la session (même règle que le Plan, A18). Une ancienne intention qui visait
  « aujourdhui » ou « emplacements » (US-195, US-201 / I5) ouvre « Parcours ».
- **P2** — La **date de référence** est choisie dans la barre (RT3) ; la changer relit l'écran une fois.
  Tout ce qui s'affiche est l'état à cette date.
- **P3** — Le sélecteur **« Toutes les pépinières ▾ »** ne garde que la ligne choisie (et le tiroir
  filtré d'autant). Avec **une seule pépinière**, il est remplacé par sa pastille
  « SERRE · 2,5 m² · pépinière chaude » (US-215 / CA2), « type non renseigné » dit tel quel.
  Une intention venue du Plan (I5) pose ce filtre, affiché en pastille retirable.
- **P4** — Les **compteurs** de la barre : « N à repiquer » (teinte d'alerte si un retard),
  « N à sortir », « N endurcit », « N à semer », « N dormants ». Un compteur à zéro n'est pas affiché.
  Un appui sur « à repiquer », « à sortir » ou « endurcit » **met en évidence** les étiquettes
  concernées et atténue les autres ; un second appui retire l'effet. « à semer » fait défiler jusqu'à
  la bande, « dormants » ouvre le tiroir. Les compteurs comptent des **étiquettes** (A31), sauf « à
  semer » (des cultures) et « dormants » (des lots).

### Bande « Le bon moment pour semer »

- **P5** — Une culture y figure si sa fenêtre de semis en pépinière est **ouverte** à la date de
  référence (règle actuelle d'US-214 / CA8, même évaluation que la confiance), qu'**aucun lot n'est
  en cours** pour elle, et que **des graines de la culture sont en stock** (A34).
- **P6** — Chaque tuile porte : la culture, « reste N j » jusqu'à la fin de la fenêtre, une jauge de la
  part de fenêtre écoulée, la fenêtre en clair (« fenêtre 1er sept.–31 oct. »), la ou les variétés en
  stock, et le bouton « **+ Semer** ». La fenêtre étant connue au mois, sa fin est le dernier jour de
  son dernier mois : c'est une borne du référentiel, pas une estimation (RT2).
- **P7** — « + Semer » **dépose** le geste pré-rempli (US-224) : semis en pépinière, culture, variété
  quand une seule est en stock, date de référence ; la pépinière est demandée par le compagnon.
  Absent en lecture seule (RT11).
- **P8** — Les cultures dont la fenêtre est ouverte, sans lot en cours mais **sans graines en stock**,
  sont repliées en une phrase : « Aussi dans leur fenêtre, sans graines en stock : mâche, oignon
  blanc · Voir les 2 › ». Aucune culture à semer et aucune repliée : la bande disparaît.

### Kanban : colonnes et lignes

- **P9** — Quatre colonnes, toujours affichées, dans cet ordre :

  | Colonne | Une étiquette y va quand… |
  |---|---|
  | **En levée** | le lot a des **graines non soldées** (semées, ni repiquées, ni soldées par une levée terminée ou une clôture) |
  | **En godet** | le lot a des **godets disponibles** en pépinière chaude, de type inconnu ou sans emplacement, avant le compte à rebours d'endurcissement, et sa mise en terre n'est pas atteinte — ou n'est pas calculable |
  | **Endurcissement** | le compte à rebours de 7 jours avant la mise en terre a commencé (pépinière chaude ou inconnue), **ou** les godets sont en pépinière froide : ils s'endurcissent sur place, sans compte à rebours (A35) |
  | **Prêt à sortir** | la fourchette de mise en terre prévue est **atteinte** (ou dépassée), quel que soit le type de pépinière |

  Un lot dormant n'est dans aucune colonne (P23). Un lot terminé n'est pas sur cet onglet.
- **P10** — Chaque colonne porte un **motif** et un **mot** (RT4 : lisible en niveaux de gris) et un
  compteur d'étiquettes. Une case vide dit « vide » ; la case « Prêt à sortir » vide d'une ligne dit
  le prochain départ : « Rien à sortir aujourd'hui. Prochain : Poireau #24, le 23 oct. ».
- **P11** — Une **ligne par pépinière** du potager, dans l'ordre des parcelles, **même vide** (une
  pépinière vide se voit). En tête de ligne : nom, nombre de lots, nombre d'étiquettes, nombre
  d'alertes. Le type (chaude, froide, non renseigné) est écrit.
- **P12** — Une dernière ligne **« Sans emplacement »**, hachurée, regroupe les lots dont la pépinière
  n'est pas connue (US-210 / CA5). Elle n'apparaît que si elle n'est pas vide. Ses étiquettes portent
  « **Ranger dans…** », qui dépose un déplacement (US-211) sans destination : le compagnon la demande.
- **P13** — **Aucune mesure de place** dans une pépinière : ni pourcentage, ni plaque, ni alvéole
  (A12, ex-US-219 / CA5).

### L'étiquette

- **P14** — Une étiquette par couple **(lot, stade, emplacement)** (A31). Elle porte le numéro du lot,
  la culture, la variété, et — si le lot est coupé — un repère **« 1/2 », « 2/2 »**. Un lot se coupe :
  - par le **stade**, dès aujourd'hui : graines encore en levée **et** godets ;
  - par l'**emplacement**, une fois le déplacement partiel livré (US-241, A32).
- **P15** — **En-tête** : un état en mot, coloré selon la légende du wireframe :

  | État | Teinte | Quand |
  |---|---|---|
  | *Repiquer — retard* | alerte (rouge) | repiquage attendu dépassé |
  | *Sortir — retard* | alerte (rouge) | mise en terre prévue dépassée |
  | *Sortir bientôt* | jaune | mise en terre dans les 15 jours |
  | *Endurcir* · J n sur 7 | bleu | compte à rebours en cours |
  | *S'endurcit sur place* | bleu | godets en pépinière froide |
  | *Levée en cours* / *En cours* | neutre | rien ne presse |
  | *Durée ?* | gris, bord pointillé | délai non renseigné : pas d'échéance (RT2) |

- **P16** — **Grand chiffre** à droite : l'échéance en jours — « +6 j » (retard), « 8 j » (avant la
  sortie), « J3 » (endurcissement), « ? » (délai non renseigné). Un fragment sans échéance attendue
  (graines restantes d'un lot en partie repiqué, A33) n'a pas de grand chiffre.
- **P17** — **Quantités** du fragment, en clair : « 24 graines · 18 levées », « 12 godets »,
  « 4 graines · 12 déjà en godet », « 6 godets · déplacés le 12 oct. ».
- **P18** — **Règle** : une piste des jours écoulés, la fourchette attendue hachurée, la date de
  référence en trait rouge. Endurcissement : sept cases. Sans fourchette (« Durée ? »), pas de règle.
  La fin de fourchette vient d'`echeances.sortie_prevue` (champ serveur ajouté par le travail US-218, A39).
- **P19** — **Ligne de dates** en clair : « semé 1er oct. · repiquage prévu 11–13 oct. »,
  « mise en terre 27 oct.–5 nov. · endurcir dès demain », « délai semis → godet non renseigné pour la
  carotte ».
- **P20** — **Gestes** : deux au plus sur l'étiquette, l'action suggérée d'US-214 en premier, choisis
  par la **même règle que la fiche du lot** (US-216 / CA15, une seule règle pour les deux) :
  *Repiquer*, *Noter la levée* (ou *Noter la levée (terminée)* sur un fragment de graines restantes,
  A33), *Mettre en terre* (**seulement si le fragment a des godets**), *Ranger dans…* (P12). Sur une
  étiquette « Durée ? », la phrase à dicter pour renseigner le délai (« /calendrier duree carotte
  godet … », US-213) est affichée, copiable, pas un bouton. Chaque bouton dépose le geste dans la file
  (US-224), sans quitter l'écran, avec la notification d'US-215 / CA7 bis ; la liste est relue une fois
  au retour sur l'onglet (US-224 / CA22). Aucun geste en lecture seule (RT11).
- **P21** — **Fragments liés** : au survol, au focus clavier ou au toucher d'une étiquette coupée,
  toutes les étiquettes du même lot s'éclairent (contour épais) et chacune porte un lien vers l'autre
  (« #23 · voir 2/2 › »). Sur téléphone, le lien change d'onglet de stade (P27).
- **P22** — **Ordre dans une case** : retards du plus grand au plus petit, puis échéances de la plus
  proche à la plus lointaine, puis sans échéance (ordre d'urgence d'US-214 / CA6).

### Le tiroir des dormants

- **P23** — Les lots **dormants** d'US-214 (graines ou godets restants, aucun geste depuis 60 jours,
  mise en terre dépassée ou inconnue) sortent du kanban et vont dans un tiroir en bas de l'écran :
  « Tiroir des lots dormants · 6 lots, aucun geste depuis plus de 60 jours », avec la mention « comptés
  dans les stocks tant qu'ils ne sont pas réglés ».
- **P24** — Chaque lot du tiroir porte : numéro, culture, jours sans geste, variété, date de semis, ce
  qui reste (« 5 graines non levées »), et au plus deux gestes : **Clôturer** (toujours) et **Mettre en
  terre** si et seulement si le lot a des godets disponibles (A37). Ordre : du plus ancien geste au plus
  récent.

### La fiche du lot

- **P25** — Un appui sur une étiquette (hors bouton) ou sur un lot du tiroir ouvre la **fiche du lot**
  (US-216) : panneau à côté du kanban quand le conteneur fait au moins 900 px, plein écran en dessous.
  La fiche montre **tous les fragments** du lot (où sont ses graines, où sont ses godets). La fermer
  rend le kanban intact — défilement, filtre, onglet de stade (RT12).

## 4. Téléphone (375 px)

- **P26** — La bande « à semer » s'empile : une ligne par culture (nom, « reste N j · variété »,
  « + Semer »), cibles de 44 px.
- **P27** — Le kanban devient **quatre onglets de stade** (« Levée », « Godet », « Endurci »,
  « Prêt »), chacun avec son compteur et un point d'alerte s'il contient un retard. Dans un onglet,
  les étiquettes sont groupées par **pépinière** (intertitre), puis « Sans emplacement ». L'onglet de
  stade ouvert par défaut est le premier qui contient une alerte, sinon le premier non vide.
- **P28** — Un fragment situé dans un autre onglet de stade est signalé par un lien
  (« 6 au châssis froid › ») qui y mène. Le tiroir des dormants est un bouton « Ouvrir › » en bas.
  Cibles de 48 px sur les gestes (écran de terrain, US-216 / CA11). Aucun défilement horizontal.

## 5. États, droits, accessibilité

- **P29** — États à rejouer dans la page de contrôle visuel : nominal (deux pépinières et sans
  emplacement), une seule pépinière, pépinière vide, lot coupé par le stade, lot coupé par
  l'emplacement (si US-241), lot en retard, « Durée ? », pépinière froide, aucun lot en cours (bande
  seule, ou « Aucun lot en cours »), aucune culture à semer, tiroir vide, lecture seule, chargement
  (squelette), échec (message et relance), thème sombre, 375 / 768 / 1280 px.
- **P30** — Accessibilité : le kanban est un tableau sémantique (lignes = pépinières, colonnes =
  stades) ; chaque étiquette est un élément focalisable nommé (« Lot 23, tomate cerise, fragment 1 sur
  2, en levée, 4 graines ») ; chaque bouton nomme son lot (« Repiquer le lot 28 ») ; état et échéance
  sont écrits, jamais portés par la seule couleur ou le seul motif.

## 6. Données — une lecture

**Une seule lecture** : `GET /pepiniere/lots` (RT6), enrichie par US-240. Plus de lecture des
calendriers côté front (`GET /plan/calendriers` n'est plus nécessaire : la fenêtre et les jours
restants viennent du serveur). Contrat **indicatif** — le nom des champs est laissé au développement,
leur présence ne l'est pas :

```text
parcours
├─ pepinieres[]      id, nom, type (chaude|froide|null), superficie_m2 — vides comprises
├─ etiquettes[]      lot (id, numero, culture, variete), fragment (rang, total),
│                    stade (levee|godet|endurcissement|pret), emplacement (id|null),
│                    quantites (graines, leves, godets), etat (P15), echeance (jours, en_retard,
│                    fourchette du/au, debut de la règle), mention (« déplacés le 12 oct. »)
├─ compteurs         a_repiquer, a_sortir, endurcit, a_semer, dormants
├─ a_semer[]         culture, varietes_en_stock[], fenetre (du, au), jours_restants, part_ecoulee
├─ a_semer_sans_graines[]  culture
└─ dormants[]        lot, jours_sans_geste, reste (graines, godets)
```

Les champs actuels de chaque lot restent tels quels (US-214 / CA7 : on ajoute, on ne renomme rien),
ce qui laisse l'onglet « Lots » et la fiche du lot fonctionner sans changement.

## 7. Écarts entre le wireframe et le modèle réel

| Le wireframe montre | Le code dit | Conséquence |
|---|---|---|
| Poivron #21 : 10 godets en serre, 6 au châssis | Un déplacement porte sur le lot entier (US-211, plan § 9) | US-241 (A32). Sans elle, l'écran ne coupe que par le stade |
| « À semer » limité aux graines en stock | `_cultures_a_semer` ne lit pas le stock | US-240 (A34) |
| « reste 12 j », jauge de fenêtre | Le serveur rend la fenêtre en texte (`formater_fenetre`), sans jours restants | US-240 (P6) |
| Les 4 graines restantes de #23 sans échéance | US-214 n'attend le repiquage que sans godet — conforme, mais l'étiquette doit le dire | US-240 (A33) |
| « Carotte #19 · #20 » en une étiquette | — | Écart assumé : deux étiquettes (A36) |
| Lot carotte #22 sur la capture de l'onglet Lots | Absent des données du wireframe | Aligner le jeu de données de la **maquette haute fidélité** sur les données réelles de dev (skill `potager-dev`) |
| « Ranger dans… » sans destination | Le déplacement dicté exige une destination ; le cas « Déplacer sans destination » est noté ouvert au 14/10/2026 | US-241 couvre le dépôt d'un déplacement sans destination, que le compagnon complète |
