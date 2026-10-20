# Pépinière — réorganisation en deux onglets (19/10/2026)

> **Statut :** 📝 Conception fonctionnelle de la vue Parcours rédigée ; **US rédigées le 19/10/2026**
> (US-218 réécrite, US-240 et US-241 créées, US-215 / 216 / 219 / 201 amendées) ; arbitrages A30 à A41
> **à confirmer** ; tickets Jira à créer ou mettre à jour ; vue Lots à concevoir ensuite.
> **Source :** wireframe `Wireframes - Calendrier pepiniere - C v2.html`, projet Claude Design
> *potager 2026* (`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`), « C · Le parcours du plant — v2 », lu au 19/10/2026.
> **Branche lue :** `epic-9-12-refonte-plan-cultures-pepiniere`, HEAD `e528f8f`, v3.89.0, plus le
> travail US-218 non commité (frise annuelle).

## 1. Le constat

La Pépinière a reçu, en trois livraisons, trois façons de lire les mêmes lots :

| Onglet | US | Ce qu'il montre | Ce qu'il répète |
|---|---|---|---|
| **Aujourd'hui** (livré, v3.88.0) | US-215 | Liste par urgence, bandeau de quatre cartes, boutons de geste | — |
| **Calendrier** (en cours, non commité) | US-218 | Frise annuelle : un lot = une barre du semis à la sortie prévue | L'échéance d'« Aujourd'hui », en dessin |
| **Emplacements** (à faire) | US-219 | Une carte par pépinière, lots groupés par stade | Les lots d'« Aujourd'hui », regroupés autrement |
| **Lots** (écran d'US-061) | US-061, US-215 / CA1 | Fiche d'identité de chaque lot, par famille, lots réglés compris | Le stade, en frise Germin. › Godet › Terre |

La piste C du wireframe — un **kanban emplacement × stade** — porte à elle seule le stade,
l'emplacement, l'alerte et le geste. Elle couvre « Aujourd'hui » et, puisque ses lignes **sont**
les emplacements, l'onglet « Emplacements ». La frise annuelle ne garde qu'une utilité : dire
« le bon moment pour semer », que la piste C porte dans une bande dédiée.

## 2. La décision proposée : deux onglets au lieu de quatre

| Onglet | Rôle | Gestes | Ouvert par défaut |
|---|---|---|---|
| **Parcours** | Le poste de travail : où est chaque lot, à quel stade, ce qui presse, quoi semer | Oui (déposés dans la file, US-224) | **Oui** |
| **Lots** | Le registre : bilan de chaque lot, en cours et terminé | **Non** — la fiche du lot reste la porte des gestes | Non |

La **fiche du lot** (US-216) devient la **porte commune** aux deux onglets.

## 3. Arbitrages A30 à A41 — à confirmer avant la haute fidélité

Ils prolongent la numérotation du plan des épics (A1 à A29). Chacun a une décision par défaut ;
le changer, c'est amender l'US concernée avant son démarrage.

| # | Question | Décision proposée | Motif | US |
|---|---|---|---|---|
| **A30** | Nom de l'onglet principal : « Ma pépinière » ou « Parcours » ? | **« Parcours »** | L'écran s'appelle déjà « Pépinière » : « Pépinière › Ma pépinière » se lit en double. « Parcours » dit ce que l'onglet montre — le chemin du plant, de la graine à la sortie. Le mot « Calendrier » disparaît : seule la bande « le bon moment pour semer » parle de dates | US-218 |
| **A31** | Qu'est-ce qu'une étiquette du kanban ? | **Une étiquette par couple (lot, stade, emplacement).** Un lot qui n'est pas coupé a une étiquette sans repère ; un lot coupé en a plusieurs, toutes au même numéro, avec un repère « 1/2 », « 2/2 ». Le compteur d'une colonne compte des **étiquettes**, pas des lots | C'est la seule unité qui tient dans une case du kanban : un lot à moitié repiqué est à la fois « en levée » et « en godet » | US-240, US-218 |
| **A32** | Faut-il rouvrir le **déplacement partiel** d'un lot, hors périmètre depuis le 19/09 (§ 9 du plan) ? | **Oui, par une US à part (US-241)**, qui ne bloque pas l'écran. Sans elle, un lot n'est coupé que par le stade (graines restantes / godets) ; avec elle, il l'est aussi par l'emplacement (« 10 godets en serre, 6 au châssis ») | Le wireframe s'appuie dessus (poivron #21), et c'est le geste réel d'octobre : on sort une partie des godets au froid. Mais l'écran a de quoi s'afficher sans lui | US-241 |
| **A33** | Un lot en partie repiqué garde des graines non levées : ont-elles encore une échéance de repiquage ? | **Non (option A du wireframe).** L'étiquette « en levée » n'a pas d'échéance ; elle propose « Noter la levée (terminée) », qui solde le reste (US-212 / CA7). Si rien n'est fait, la dormance la ramasse à 60 jours | L'option B garderait un retard de repiquage éternel sur quatre graines qui ne lèveront pas : une alerte qui ment. US-214 n'attend déjà le repiquage que « tant que le lot n'a aucun plant en godet » | US-240 |
| **A34** | Quand une culture est-elle « à semer » ? | Fenêtre de semis en pépinière **ouverte** (règle actuelle d'US-214 / CA8), **aucun lot en cours**, et **graines de la culture en stock**. Les cultures qui remplissent les deux premières conditions sans graines sont **repliées** (« Aussi dans leur fenêtre, sans graines en stock : mâche, oignon blanc · Voir les 2 ») | Proposer de semer ce qu'on n'a pas en sachet, c'est envoyer le jardinier au placard pour rien. Les repliées restent visibles : c'est une liste d'achat | US-240 |
| **A35** | Un godet en pépinière **froide** est-il « en godet » ou « en endurcissement » ? | **En endurcissement**, avec la mention « s'endurcit sur place » et **sans compte à rebours** (US-214 / CA4). La colonne « En godet » d'une pépinière froide est donc normalement vide | C'est ce que dit déjà la table d'endurcissement d'US-214 ; le kanban ne fait que le ranger | US-240 |
| **A36** | Deux lots de la même culture sans délai connu : une étiquette commune (« Carotte #19 · #20 ») ou deux ? | **Deux**, une par lot (A31) — **écart assumé avec le wireframe** | Une étiquette commune rendrait « Noter la levée » ambigu (quel lot ?) et casserait la règle de comptage. La raison manquante est la même sur les deux : elle se lit deux fois, sans gêne | US-218 |
| **A37** | Que contient le **tiroir des dormants** ? | Les lots dormants d'US-214, **hors du kanban**, avec deux gestes au plus : *Clôturer* (toujours) et *Mettre en terre* **seulement si le lot a des godets disponibles** (US-216 / CA8). « Encore là » est retiré | Un lot dormant n'a plus de stade utile ; le laisser dans une colonne fausserait les compteurs. Correction du 19/10 : #7, #8 et #18 n'ont plus de godet, ils n'offrent que *Clôturer* | US-240, US-218 |
| **A38** | Que deviennent la pastille de pépinière (US-215 / CA2), le filtre d'emplacement (US-215 / CA9) et l'intention I5 venue du Plan (US-201) ? | Un **sélecteur « Toutes les pépinières ▾ »** dans la barre ; il remplace le filtre et masque les autres lignes du kanban. Avec une seule pépinière, il cède la place à la pastille d'US-215. L'intention I5 ouvre **Parcours filtré sur la pépinière** — il n'y a plus d'onglet Emplacements | Une seule mécanique de filtre au lieu de trois | US-218, US-201 (amendée) |
| **A39** | Que fait-on du travail US-218 « frise annuelle » non commité ? | **On garde le champ serveur `sortie_prevue`** et son test : il fournit la règle de chaque étiquette. **On met de côté** le reste (composant, lib de placement, page de contrôle, guide, fiches du corpus décrivant la frise) sur une branche `wip/us-218-frise`, sans le livrer | La frise n'a plus d'onglet. Ses fiches de corpus décrivent un écran qui n'existera pas : les committer violerait US-099 / CA9 | US-218 |
| **A40** | « Lots » garde-t-il des gestes ? | **Non** : registre en lecture, gestes par la fiche du lot. Conception détaillée dans `03_VUE_LOTS.md`, **après** la vue Parcours | Les gestes vivent à un seul endroit de l'écran (le kanban) et à un seul endroit du lot (sa fiche) | US-242 (à rédiger plus tard) |
| **A41** ⏸️ *(en suspens, PO 19/10 : à régler après tests terrain ; défaut provisoire d'US-241 = demander l'origine par boutons)* | Un lot réparti entre deux pépinières : d'où une plantation, une perte ou une vente retire-t-elle les godets quand la phrase ne le dit pas ? *(ajouté le 19/10 en rédigeant US-241)* | **D'abord dans la partie la plus avancée** (prêt à sortir, puis endurcissement, puis en godet), à égalité dans la plus anciennement déplacée. Le récapitulatif le dit (« 6 godets pris au châssis froid »), la correction reste possible ; un geste déposé depuis une étiquette porte son emplacement | On plante ce qu'on a endurci. Demander l'origine à chaque plantation d'un lot réparti ajouterait une question au geste le plus fréquent de la saison | US-241 |

## 4. Ce qui ne change pas

- Les règles transverses **RT1 à RT14** du plan s'appliquent telles quelles, avec la lecture
  d'US-224 pour RT1 : un bouton **dépose** un geste dans la file, le compagnon le propose.
- Les échéances restent calculées **côté serveur, à un seul endroit** (`app/services/echeances_lots.py`,
  US-214) ; le front ne fait que ranger et dire (RT7).
- **RT9** : une maquette haute fidélité de l'onglet Parcours est gelée dans Claude Design avant le code
  d'US-218. Elle peut être produite **pendant** la livraison des données (voir `02_IMPACTS_BACKLOG.md` § 4).
- Hors périmètre maintenu : plaque et alvéole (A12), mesure de place occupée dans une pépinière
  (US-219 / CA5 — la règle survit à l'US), saisie web directe (A16).
