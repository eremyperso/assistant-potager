# Pépinière — impacts sur le backlog, livraisons regroupées, modèle conseillé

> Périmètre : **vue Parcours** seulement. La vue Lots fera l'objet du même travail **ensuite**
> (`03_VUE_LOTS.md`) ; rien ici ne la préempte, sauf l'arbitrage A40 (registre sans gestes).
> État lu le 19/10/2026 : US-208 à US-217 et US-239 livrées dans le code (v3.86 à v3.89.0), US-218 en cours
> **non commitée** (frise annuelle), US-219 à US-221 à faire. Dernier numéro du backlog : **US-239**.
> ⚠️ Les statuts Jira ne suivent pas le code : voir le § 6.

## 1. Les US existantes, une par une

> ✅ **Amendements appliqués le 19/10/2026** : encadré en tête d'US-215 (remplacée) et d'US-219
> (absorbée) ; section « AMENDEMENT du 19/10/2026 » en fin d'US-216 (CA1 réécrit, CA2 et CA15 précisés,
> CA19 ajouté) et d'US-201 (I5 réécrite). Reste à faire côté Jira : colonne « Jira » ci-dessous.

| US | Statut | Impact de la vue Parcours | Ce que le PO fait | Jira |
|---|---|---|---|---|
| US-208 Pépinière chaude / froide | ✅ livrée | Aucun. Le type range les godets froids en « Endurcissement » (A35) — déjà dans la table d'US-214 | Rien | — |
| US-209 Numéro de lot | ✅ livrée | Aucun. « Aller au lot n° » quitte la barre de Parcours et reste dans Lots | Rien | — |
| US-210 Godets localisés | ✅ livrée | Aucun. Sa CA5 nourrit la ligne « Sans emplacement » (P12) | Rien | — |
| US-211 Déplacer un lot | ✅ livrée | **Étendue, pas rouverte** : le déplacement partiel et le dépôt sans destination vont dans US-241 | Rien sur l'US ; renvoi depuis US-241 | — |
| US-212 Noter la levée | ✅ livrée | Aucun. « Noter la levée (terminée) » sur les graines restantes réutilise sa CA7 (A33) | Rien | — |
| US-213 Délai semis → godet | ✅ livrée | Aucun. Sa phrase de dictée s'affiche sur l'étiquette « Durée ? » (P20) | Rien | — |
| US-214 Échéances d'un lot | ✅ livrée | **Étendue, pas rouverte** : « à semer » avec stock et jours restants, fragments, colonnes, compteurs, tiroir → US-240 | Rien sur l'US ; renvoi depuis US-240 | — |
| **US-215** Onglet « Aujourd'hui » | ✅ livrée | **Remplacée** : l'onglet disparaît. Sa lib (`lib/pepiniere.js`), le dépôt de geste et la notification (CA7, CA7 bis), la pastille (CA2) et la lecture seule (CA11) sont **réutilisés** par US-218 | Ajouter en tête un encadré « Remplacée le 19/10/2026 par US-218 (vue Parcours) — CA réutilisés : CA2, CA7, CA7 bis, CA11, CA13, CA14 » ; ne rien supprimer | Reste *Terminé* ; lien « est remplacée par » US-218 |
| **US-216** Fiche du lot | ✅ livrée | **Amendée** : devient la porte commune aux deux onglets. CA1 (points d'entrée) à réécrire : étiquette ou tiroir de Parcours, ligne de Lots, « Aller au lot n° », QR (US-221). **CA19 ajouté** : la fiche montre tous les fragments du lot (P25) | Amender CA1, ajouter CA19, mention « amendée le 19/10, livrée avec US-218 » | Commentaire ; pas de réouverture : l'amendement est livré et testé par US-218 |
| US-217 Où mettre les plants | ✅ livrée | Aucun (dans la fiche du lot) | Rien | — |
| **US-218** Onglet « Calendrier » | 🔨 en cours, non commitée | **Réécrite intégralement** : devient « Afficher l'onglet Parcours de la Pépinière — kanban emplacement × stade ». Absorbe US-219 et la partie écran d'US-215. Le travail non commité est mis de côté, sauf `sortie_prevue` (A39) | Réécrire titre, story, CA, dépendances, estimation (**8 pts**) à partir de `01_VUE_PARCOURS.md` | Mettre à jour titre et description ; repasser en *À faire* |
| **US-219** Onglet « Emplacements » | ⬜ à faire | **Absorbée** par US-218 : les lignes du kanban sont les emplacements. Sa règle « aucune mesure de place » (CA5) survit en P13 | Encadré « Absorbée le 19/10/2026 par US-218 » ; ne pas supprimer le fichier | Clore en *Abandonnée* (ou équivalent du workflow) avec lien vers US-218 |
| US-220 Confiance selon le type de pépinière | ⬜ à faire | Aucun : indépendante de l'écran | Rien | — |
| US-221 Étiquettes à QR code *(option)* | ⬜ à faire | Aucun : vise la fiche du lot, qui reste la cible | Rien | — |
| **US-201** Liens de la Vue plan | ✅ livrée | **Amendée** : I5 ouvre « Parcours filtré sur la pépinière », puisqu'il n'y a plus d'onglet Emplacements ni Aujourd'hui (A38) | Amender la ligne I5, mention « livrée avec US-218 » | Commentaire |
| US-224 File des gestes | ✅ livrée | Aucun : c'est le mécanisme de tous les boutons de Parcours | Rien | — |

## 2. Les US nouvelles

> ✅ **Rédigées le 19/10/2026** : `backlog/US-218_pepiniere-onglet-calendrier.md` (réécrite, nom de
> fichier conservé), `backlog/US-240_parcours-plant-donnees.md`, `backlog/US-241_deplacement-partiel-lot.md`.

| US (numéro provisoire) | Titre | Pts | Contenu | Dépend de |
|---|---|---|---|---|
| **US-240** | Lire le parcours du plant : étiquettes par lot, stade et emplacement, et le bon moment pour semer | 5 | Serveur seul. Ajoute à `GET /pepiniere/lots` le bloc `parcours` (01 § 6) : fragments par stade (et par emplacement dès US-241), colonne de chaque fragment (P9, A35), état et grand chiffre (P15, P16), compteurs (P4), « à semer » avec stock de graines, variétés en stock, jours restants et part écoulée (P5, P6, A34), cultures repliées sans graines (P8), échéance des graines restantes (A33), dormants hors kanban avec ce qui leur reste (P23), pépinières vides. Une lecture, aucun champ renommé | US-214, US-212, US-210 (livrées) |
| **US-241** | Déplacer une partie des godets d'un lot, et ranger un lot sans emplacement | **8** | Bot et serveur. « déplace 6 godets du lot 21 au châssis » : quantité facultative sur le geste de déplacement, emplacement **par fragment** (une pépinière peut porter une partie du lot), refus d'une quantité supérieure aux godets de l'origine ; dépôt d'un déplacement **sans destination** depuis l'écran (« Ranger dans… »), que le compagnon complète. Catalogue et parité (RT10), Journal, cycle de vie du lot. Rouvre le « déplacement partiel » du plan § 9 (A32) | US-211, US-224 |
| **US-218** *(réécrite)* | Afficher l'onglet Parcours de la Pépinière — le kanban emplacement × stade | 8 | Front. Deux onglets (P1), barre et compteurs (P2 à P4), bande à semer (P5 à P8), kanban (P9 à P13), étiquettes et fragments liés (P14 à P22), tiroir (P23, P24), fiche du lot en panneau (P25), téléphone (P26 à P28), états et accessibilité (P29, P30). Livre aussi les amendements d'US-216 (CA1, CA19) et d'US-201 (I5). Maquette haute fidélité gelée (RT9) | US-240 ; US-241 conseillée, pas bloquante |
| US-242 *(plus tard)* | Vue Lots : le registre des lots | — | À concevoir dans `03_VUE_LOTS.md`, après la vue Parcours | US-218 |

**Bilan ÉPIC 12** : US-218 passe de 5 à 8 points, US-219 (3) sort, US-240 (5) et US-241 (8) entrent :
**+13 points** pour la vue Parcours, vue Lots non chiffrée. US-241 a été relevée de 5 à 8 à la
rédaction : la consommation d'un lot réparti (A41) et la répartition par date en font la seule US qui
touche au modèle de l'emplacement.

## 3. Livraisons regroupées

Le principe : **une livraison = une session = une branche de travail = une entrée de PATCH_NOTES**,
plusieurs US à la fois, plutôt qu'une US par session. On coupe là où le contexte change de nature
(serveur et bot d'un côté, écran de l'autre), pas à chaque US.

| Livraison | Contenu | Pourquoi ensemble | Version |
|---|---|---|---|
| **L0 — Ranger le travail en cours** (≈ 30 min) | Isoler le travail US-218 « frise » sur `wip/us-218-frise` ; garder sur la branche de l'épic le champ `sortie_prevue` et son test ; **ne pas committer** les fiches de corpus, le guide `docs/MANUEL/guide-onglet-calendrier-pepiniere.md` ni la page de contrôle de la frise (A39) | Repartir d'un arbre propre avant L1 ; éviter de livrer un corpus qui décrit un écran mort (US-099 / CA9) | aucune |
| **L1a — Les données du parcours** | **US-240 + US-220** | Même domaine serveur (lecture de la pépinière, confiance d'un semis selon le type) et aucun bot. US-240 reprend `sortie_prevue` du travail mis de côté (§ 6). Sans US-241, un lot n'est coupé que par le stade (US-240 / CA3) : la livraison tient seule | MINOR |
| **L1b — Le déplacement partiel** | **US-241** | La seule US qui touche au modèle de l'emplacement et au bot. Séparée pour que l'arbitrage A41, **en suspens**, puisse mûrir pendant L1a et la maquette. Étend le contrat d'US-240 (fragments par emplacement) sans le changer | MINOR |
| **Maquette HF** (en parallèle de L1a et L1b) | Gel de la maquette Parcours dans Claude Design, sur les données réelles de dev (lot carotte #22 compris) | RT9 ; ne dépend que de `01_VUE_PARCOURS.md` | — |
| **L2 — L'écran Parcours** | **US-218 réécrite**, avec les amendements d'US-216 et d'US-201, le retrait des onglets Aujourd'hui / Calendrier / Emplacements | Un seul écran, une seule lib, une seule page de contrôle visuel, une seule passe de corpus. Après L1b ; si US-241 glisse, L2 peut partir sans elle (« conseillée, pas bloquante ») et le « Ranger dans… » affiche la phrase à dire (US-218 / CA10) | MINOR |
| **L3 — La vue Lots** | US-242 et ce que `03_VUE_LOTS.md` décidera | Après L2 seulement | MINOR |

**Accélérateur** : le contrat du § 6 de `01_VUE_PARCOURS.md` est fixé avant L1. L2 peut donc démarrer
sur un jeu de données factice dès que la maquette est gelée, dans un worktree séparé, pendant que
L1a et L1b se terminent ; il ne reste qu'à brancher la vraie lecture à la fin.

## 4. Modèle et niveau de raisonnement conseillés

| Étape | Modèle | Effort | Motif |
|---|---|---|---|
| **Persona PO** : réécrire US-218, amender US-215 / 216 / 201 / 219, créer US-240 et US-241 | **Sonnet 5.5** | **high** | Rédaction cadrée : le raisonnement est fait dans `01` et `02`. *high* pour tenir les renvois croisés P / A / CA sans contradiction ; Opus n'apporterait que du coût |
| **L1a** — US-240 + US-220 | **Opus 5.5** | **high** | Règles imbriquées (colonnes, fragments, dormance, A33), table de tests exhaustive, et une erreur se propage à l'écran et aux stocks |
| **L1b** — US-241 | **Opus 5.5** | **high** | Multi-domaines : parseur règles-first, catalogue et parité du bot (RT10), emplacement courant, Journal, cycle de vie. C'est la seule US qui touche le modèle de données |
| **L2** — US-218 | **Opus 5.5** | **medium** | Gros volume d'interface très spécifié : le risque est la tenue du responsive et l'écart à la maquette, pas le raisonnement. Passer en *high* seulement si la vérification visuelle boucle plus de deux fois |
| **QA, PATCH_NOTES, VERSION, corpus** (fin de L1a, de L1b, de L2) | **Sonnet 5.5** | **medium** | Mécanique, sauf le jugement « quelle fiche du corpus est devenue fausse », qui reste à portée de Sonnet avec la table du `README` du corpus |
| **Jira** (création, liens, transitions) | **Haiku 5.5** | **low** | Purement mécanique, la clé se lit dans Jira |
| **Recherches** (sous-agent Explore, grep) | **Haiku 5.5** | **low** | Localiser, pas juger |

Ce qui fait gagner le plus de temps n'est pas le modèle, c'est : **une session par livraison**, la
lecture de `01_VUE_PARCOURS.md` à la place du plan complet, la suite de tests complète une seule fois
par livraison, et le contrat de données fixé avant le code pour paralléliser L1 et L2.

## 5. Consignes pour le Persona PO

1. Lire `README.md` (A30 à A41), ce document, puis `01_VUE_PARCOURS.md` — **pas** le plan des épics en
   entier.
2. Numérotation : le dernier numéro est US-239 ; US-240 et US-241 sont les deux suivants.
3. Les CA d'US-218 et d'US-240 **citent les règles P1 à P30** qu'ils couvrent ; chaque règle P est
   couverte par une et une seule US (US-240 pour le calcul, US-218 pour l'affichage).
4. Épic à recopier : `ÉPIC 12 — Pépinière : le poste de travail sous abri` (absent de la liste du
   persona, à ajouter — plan des épics § 10.4).
5. ~~Le persona n'a que `createFiles`~~ — **tranché le 19/10/2026** : l'utilisateur a autorisé la
   réécriture et l'amendement des US existantes pour cette mission. Les amendements suivent le format
   déjà en usage (« ## ⚠️ AMENDEMENT du JJ/MM/AAAA » en fin de fichier, encadré en tête pour une US
   remplacée ou absorbée).
6. Ne rien rédiger pour la vue Lots.

## 6. Reprise des US existantes et du travail en cours

Ce que la réorganisation fait des US déjà livrées, et du travail non commité d'US-218. Lu le
19/10/2026 sur l'arbre de travail et sur Jira.

### 6.1 Les US livrées : rien à refaire, mais des statuts Jira en retard

| Clé Jira | US | Code | Jira | À faire |
|---|---|---|---|---|
| PIA-160 à 166, 169 | US-208 à 214, 217 | livrées, commitées | *Revue en cours* | Les passer en *Terminé* après validation du PO ; aucun code à reprendre |
| PIA-180 | US-224 | livrée | *Revue en cours* | Idem |
| PIA-205 | US-239 (ensoleillement) | livrée en v3.88.0 | **À faire** | Écart : à passer en *Terminé* après validation |
| PIA-167, 168, 153 | US-215, 216, 201 | livrées, **modifiées par US-218** | *Revue en cours* | Les laisser ainsi jusqu'à L2, puis *Terminé* : leurs amendements sont livrés avec US-218 |
| PIA-170 | US-218 | **non livrée** (frise mise de côté) | *Revue en cours* | Repasser en *À faire* (la frise n'est plus l'objet) |
| PIA-171 | US-219 | jamais développée | *Terminé* (clôturée le 19/10, absorbée) | Rien |
| PIA-172, 173 | US-220, 221 | à faire | *À faire* | US-220 part en L1a ; US-221 reste en option |

### 6.2 Le travail non commité d'US-218 (frise) : trier avant L1a

C'est le seul cas « en partie réalisé ». Il se découpe ainsi (étape **L0**, avant toute autre) :

| Élément | Fichiers | Devenir |
|---|---|---|
| Champ serveur `echeances.sortie_prevue` | `app/services/echeances_lots.py` ; tests `test_us218_ca3_*` (5 tests) | **Gardé**, repris par US-240 / CA8. Les 5 tests sont déplacés dans `tests/test_us240_parcours_plant.py`, renommés `test_us240_*` |
| Frise : composant, lib de placement et leurs tests, page de contrôle | `OngletCalendrier.jsx`, `calendrierPepiniere.js` + `.test.js`, `_PepiniereCalendrierPreview.jsx`, route `/pepiniere-calendrier` dans `main.jsx` | **Mis de côté** sur `wip/us-218-frise`, non livré. Quelques fonctions pures (`dateCourte`, `echeanceEnLettres`, `phraseDuLot`, `lectureTextuelle`) pourront être reprises en L2 si elles servent aux étiquettes : à décider alors, pas avant |
| Branchement dans l'écran | `views/Pepiniere.jsx` (lecture `api.calendriersPlan`, onglet) | **Annulé** : à retirer de l'arbre avant L1a |
| Drapeau `ONGLETS_LIVRES.calendrier: true` et le test qui l'attend | `lib/pepiniere.js`, `pepiniere.aujourdhui.test.js` | **Annulé** : à remettre à `false`, sans quoi l'onglet « Calendrier » apparaîtrait en production |
| Tests de la frise | `test_us218_*` hors `ca3` (onglet livré, semer maintenant, container queries, corpus, fiche de domaine…) | **Mis de côté** avec la frise |
| Documentation | section « L'onglet Calendrier » de `docs/domaines/pepiniere.md`, ligne `OngletCalendrier` de `docs/domaines/README.md`, `docs/MANUEL/guide-onglet-calendrier-pepiniere.md` | **Mis de côté** ; seul le paragraphe sur `sortie_prevue` reste dans la fiche de domaine |
| Corpus | `data/connaissance/doc_app/pepiniere-par-lot.md`, `README.md`, `tests/corpus/us099_questions_fonctionnement.csv` | **Annulé** : ces fiches décrivent un onglet qui n'existera pas (US-099 / CA9) |

Contrôle de fin de L0 : `git status` ne montre plus que `sortie_prevue` et ses tests ; `npm test` et
`pytest tests/test_us099_corpus_fonctionnement.py` sont verts.

### 6.3 Ce qu'US-218 retire, ce qu'elle garde (L2)

| Livré par | Devenir en L2 |
|---|---|
| US-215 : onglet « Aujourd'hui », bandeau des quatre cartes, liste par urgence | **Retirés** (CA29 d'US-218) |
| US-215 : dépôt de geste dans la file, notification, pastille de la pépinière, lecture seule, relecture au retour | **Déplacés** vers l'onglet Parcours, pas copiés |
| US-215 : `tests/test_us215_pepiniere_aujourdhui.py`, `pepiniere.aujourdhui.test.js` | **Adaptés**, pas supprimés en bloc : chaque test qui couvre un comportement conservé migre vers les tests de Parcours |
| US-061 : onglet « Lots » (cartes, famille, recherche, tri) | **Inchangé** en L2 ; repensé en registre en L3 |
| US-216 : fiche du lot | **Conservée** ; CA1 et CA19 livrés avec US-218 |
| US-217 : « Où les mettre » | **Conservé**, dans la fiche |
