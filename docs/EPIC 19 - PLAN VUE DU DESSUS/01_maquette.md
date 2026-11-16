# La maquette « Plan - Pistes » : ce qui est prévu

*Source : projet Claude Design « potager 2026 », fichier `Plan - Pistes.html` (absent de `compat.json`).*

> **Limite de cette synthèse.** La maquette n'est pas dans le dépôt. Ce document reprend ce que les 16 fiches du
> backlog en citent (section « Contexte fonctionnel » et tableaux de règles). Il n'a pas été relu contre la
> maquette elle-même. Ne pas repartir de « Plan - Rangs et places » (US-200 / US-228) : un premier jet fondé sur
> elle a été jugé hors sujet et supprimé.

## 1. Le constat de la maquette

La vue « rangs et places » **montre le modèle de données au lieu du potager**. Cause première relevée :
aucune position ni taille relative de parcelle n'était enregistrée. D'où :

- une **géométrie enregistrée** (US-326) ;
- un **plan sur vue du dessus** qui remplace l'ancienne vue (US-327) ;
- les « places » qui quittent le plan et passent **dans le suivi de culture** (US-322).

## 2. Les trois pistes comparées

| Piste | Idée | Rôle retenu |
|---|---|---|
| **A** — Plan aimanté sur grille | Parcelles posées sur une grille neutre | **Repli sans fond** : c'est ce que livrent US-327 et US-333 (« Fond masqué ») |
| **B** — Plan par zones | Une tuile par parcelle, dans l'ordre du chemin | Affichage tant qu'**aucune parcelle n'est placée** (règle P10) |
| **C** — Plan sur vue du dessus *(retenue)* | Parcelles à leur place sur le plan, éventuellement posé sur une photo recalée | Cible. **Coût annoncé : élevé** (import, stockage, recalage de la photo) → US-335 |

## 3. Principes de la maquette

1. **Ce qui manque devient une tâche.** Une culture sans parcelle est listée « À placer », jamais dessinée.
2. **Toute écriture passe par Gaston.** Un geste sur le plan n'écrit rien : il ouvre le compagnon avec le
   contexte, qui propose une carte à confirmer. Exceptions assumées : les caractéristiques d'une parcelle
   (paramétrage, US-331) et l'enregistrement de l'éditeur du plan (US-333).
3. **Un seul langage visuel** pour l'étape d'une culture, partout : plan, liste mobile, suivi.
4. **Un seul écran sur mobile** : plus d'onglets « Tournée » et « Plan ».
5. **Pas de modification du plan sur mobile** : on lit sur le téléphone, on pose sur l'ordinateur.
6. **Une seule source pour la géométrie** (garde-fou G1) : la superficie se déduit de longueur × largeur.

## 4. Les écrans et sections, avec l'US qui les porte

| Section de la maquette | Contenu | US |
|---|---|---|
| Langage visuel commun · Lire une étape | Couleurs, pictogrammes, plein / hachuré / pastille / pointillé, légende | US-321 |
| Une culture qui évolue : la fève du rang 6 | Cycle d'une culture, du semis à la fin | US-320 |
| Plan sur vue du dessus (ordinateur) | Plan à gauche, panneau de droite | US-327 |
| Panneau de droite sans sélection : « Aujourd'hui au potager » | Tâches du jour | US-328 |
| Panneau de droite, écrans mobiles « 3 · Toucher une culture » et « 6 · Fiche culture » | Suivi d'une culture | US-322 |
| « Noter ouvre Gaston avec le contexte » | Contexte d'écran transmis à Gaston | US-323 |
| « Noter et Gaston : un seul chemin », écrans mobiles 4 et 5 | Raccourcis, cartes, confirmation | US-324 |
| « Barre d'onglets : actuelle et proposée » | Bouton « Noter » au centre | US-325 |
| Encart « Impact données » | Géométrie, rang et part d'une culture | US-326 |
| « Mobile · Plan dans la navigation actuelle », écrans 1 et 2 | Mini-plan + parcelles dans l'ordre du chemin | US-329 |
| « Parcelle dans le Plan : fusionner la vue Parcelles » | Détail d'une parcelle D1 à D6 | US-330 |
| Onglet « Caractéristiques » | Lecture et modification | US-331 |
| « Rendre inactive ou supprimer… ouvre Gaston » ; « Poser une forme nouvelle ouvre Gaston » | Créer / inactiver / supprimer | US-332 |
| « Ordinateur · Modifier le plan (piste C) » | Éditeur du plan | US-333 |
| « Mettre en place le plan » · comparatif « Mise en place : 5 min » | Guide de mise en place | US-334 |
| « Fond atténué à 60 % » | Photo de fond recalée | US-335 |

## 5. Les règles de la maquette, par écran

### 5.1 Le plan sur vue du dessus (US-327)

| # | Règle |
|---|---|
| P1 | Chaque parcelle placée est dessinée à sa position, sa taille et sa rotation, toutes à la même échelle ; le cadre suit l'emprise |
| P2 | Les rangs suivent le sens des rangs ; chaque rang est découpé en segments, un par culture, proportionnels à leur part ; un segment libre est en pointillé |
| P3 | Un segment porte la couleur de l'étape et, selon la place : emoji + nom + pictogramme, emoji + pictogramme, pictogramme seul, rien. Rangs en travers : nom écrit à la verticale |
| P4 | Étape prévue : segment hachuré ; pastille orange si à confirmer |
| P5 | Le nom de la parcelle est un bouton posé dessus ; serre, planche, bac et butte ont chacun leur fond |
| P6 | Une parcelle pépinière affiche ses lots en vignettes, sans étapes ni actions ; toucher un lot ouvre sa fiche dans « Ma pépinière » |
| P7 | Une parcelle inactive reste sur le plan, grisée |
| P8 | Filtres : Tout · À confirmer · N · En récolte · Rangs libres — les segments hors filtre s'estompent, rien ne disparaît |
| P9 | Rose des vents orientée selon le nord ; échelle « 5 m » ; légende des étapes sous le plan |
| P10 | Une parcelle non placée n'est pas dessinée : listée « À placer ». Aucune placée → plan par zones |
| P11 | En-tête : « Au 12 novembre » (date de référence), fond utilisé, emprise « 25 × 15 m » |

### 5.2 Le langage visuel (US-321)

| # | Règle |
|---|---|
| V1 | Familles de couleur franches : sable (Semé), vert tendre (Levé, Planté), vert franc (En croissance), jaune (En fleur), orange (En récolte), gris (Terminé) |
| V2 | Un pictogramme par étape ; la couleur aide, le pictogramme et le libellé font foi |
| V3 | **Plein** = validée · **hachuré** = prévue, pas encore vue |
| V4 | **Pastille orange** = date prévue atteinte, à confirmer |
| V5 | **Gris hachuré** = terminée, rang à libérer |
| V6 | **Contour pointillé** = rang libre |
| V7-V8 | L'orange de la récolte est la couleur la plus visible ; lisible en niveaux de gris |

### 5.3 Les étapes d'une culture (US-320)

| # | Règle |
|---|---|
| E1 | Une étape porte un code, une date, un statut (`prevue` / `validee`) et une source (`jardinier`, `compagnon`, `calendrier`) |
| E2 | Une étape prévue vient du calendrier recalé ; sans calendrier, aucune étape n'est prévue |
| E3 | Date prévue atteinte → **« à confirmer »**. Elle n'avance jamais seule : seul un geste confirmé la valide |
| E4 | `semis` → Semé · `levee` → Levé · `plantation` → Planté · première `recolte` → En récolte |
| E5 | Végétatif : la récolte consomme les pieds ; la dernière qui solde le stock → Terminé |
| E6 | Reproducteur : la récolte ne consomme pas les pieds ; elle s'ajoute au rendement cumulé |
| E7 | « Pas encore » repousse le rappel de trois jours, sans rien valider |
| E8 | Culture Terminée dont le rang n'est pas libéré → listée **« à libérer »** |
| E9 | Aucune étape ne se calcule côté écran : `GET /plan` et le suivi fournissent tout |

### 5.4 Le suivi d'une culture (US-322) — blocs S1 à S10

En-tête · Localisation (« Planche centrale, rang 3 — Voir la parcelle → ») · Ligne de place (pieds, mètres
occupés, espacement, mètres libres ou « ⚠ +N ») · Étape courante · Bandeau « à confirmer » · Bouton **Noter** ·
Récolté (cumul de saison) · Frise des étapes (passées, courante, prochaine) · Origine (Pépinière · lot #18 /
Achat / Semis direct) · Notes datées. Un bloc sans donnée est **absent**, jamais vide. Le bouton Photo est
visible, désactivé, « bientôt disponible ».

### 5.5 Aujourd'hui au potager (US-328) — A1 à A5

En-tête (date, température, alerte météo) · **À confirmer · N** · **À libérer · N** · **À placer · N**
(plants prêts d'un lot, cultures dites sans parcelle) · Aide « Glissez sur un rang libre du plan ». Le
glisser-déposer **n'écrit rien** : il ouvre Gaston avec la carte de placement.

### 5.6 Le plan sur mobile (US-329) — M1 à M6

Barre (date, emprise) · **Mini-plan** réduit sans libellés (toucher une parcelle fait défiler jusqu'à sa carte) ·
Légende compacte · Boutons « N à confirmer » / « N à libérer » · **Dans l'ordre du chemin** : une carte par
parcelle (nom, rangs, « Détail »), une ligne de 54 px par culture (« R3 », barre d'étape, emoji + nom, « En
récolte depuis le 20 oct. », pastille) · Pépinière : une ligne par lot, vers « Ma pépinière ».
Bascule par largeur de **conteneur** (< 720 px), jamais par largeur d'écran.

### 5.7 Gaston et « Noter » (US-323, US-324, US-325)

- **Contexte (C1-C6)** : par priorité culture, sinon parcelle, sinon tout le potager ; barre « À propos de : … »
  avec croix pour la retirer ; envoyé sous forme d'**identifiants**, vérifiés côté serveur ; une phrase qui nomme
  une autre culture l'emporte.
- **Raccourcis** : étape à confirmer → « [Étape] vue » + « Pas encore » · en récolte → « Récolte », « Culture
  terminée » · terminé → « Rang libéré » · parcelle ou potager → « Arrosé », « Paillé », « Désherbé ».
- **Cartes** : Note · Note + étape · Étape · Récolte · Rang libéré. **Rien n'est écrit avant « Confirmer ».**
  Après confirmation, Gaston dit ce qui a changé et propose « Retour au plan ».
- **Barre basse mobile** : Accueil · Plan · **Noter** (au centre, mis en avant, jamais « courant ») · Pépinière
  ou Cultures · Plus.

### 5.8 La parcelle dans le plan (US-330, US-331)

| # | Contenu |
|---|---|
| D1 | En-tête : pictogramme, nom, « Planche · 60 m² · 8 rangs » |
| D2 | Géométrie : « Sur le plan : 12 × 5 m, rangs dans la longueur » + « Ajuster sur le plan » |
| D3 | Onglet **En place** : « 7 rangs occupés sur 8 · 1 à confirmer », une ligne par culture, rangs libres (pépinière : onglet **Lots**) |
| D4 | Onglet **Caractéristiques** : type, exposition, sol, abri, paillage, pépinière ; superficie / longueur / largeur **verrouillées** (« défini sur le plan ») ; statut « se change avec Gaston » |
| D5 | Onglet **Rotation** (contenu d'US-231) |
| D6 | Onglet **Entretien** (journal du sol d'US-232) + bouton **Noter** |

La fusion supprime l'onglet « Parcelles », avec trois garde-fous : une seule source pour la géométrie, la
sélection partagée entre plan et liste, les anciens liens redirigés.

### 5.9 Créer, inactiver, supprimer (US-332)

Créer une parcelle = poser une forme dans l'éditeur, qui **ouvre Gaston** ; la parcelle n'existe qu'après
confirmation. Pour une parcelle avec cultures ou historique, Gaston propose de la **rendre inactive**
(grisée, historique conservé, réactivable), jamais de la supprimer ; la suppression n'est proposée que pour
une parcelle **vide**. Pour une pépinière, la vérification porte sur ses lots.

### 5.10 L'éditeur du plan (US-333) — ordinateur seulement

Colonne gauche : fond du plan · **À placer · N** · **Nouvelle parcelle** (Planche, Bac, Pépinière, Serre) ·
Orientation (rose des vents, huit directions). Centre : le plan, poignées de redimensionnement et de rotation,
cotes, barre flottante (rangs ↔ / ↕, dupliquer, retirer). Colonne droite : forme, longueur, largeur, contrôle de
cohérence de surface, sens des rangs, nombre de rangs, angle.

| # | Règle |
|---|---|
| E1 | Alignement sur l'angle du potager, aimantation **tous les 50 cm**, **quatre formes seulement**, pas de dessin libre |
| E2 | Poser une parcelle existante : la glisser depuis « À placer » ; dimensions connues, sinon un carré déduit de la superficie |
| E3 | Poser une forme nouvelle ouvre Gaston |
| E4 | « Retirer du plan » efface la position, pas la parcelle |
| E5 | Écriture **à « Enregistrer » seulement**, en une fois ; Annuler abandonne |
| E6 | Réduire le nombre de rangs sous le nombre de rangs occupés est refusé avec explication |
| E7 | Pas de modification sur mobile |

### 5.11 La mise en place (US-334)

| # | Règle |
|---|---|
| M1 | Aucune parcelle placée : plan par zones + encart « Mettre en place le plan · environ 5 minutes » |
| M2 | Placement partiel : les placées sont dessinées, l'encart devient « N parcelles à placer » |
| M3 | L'assistant « Premier potager » se termine sur « mettre en place le plan maintenant ou plus tard » |
| M4 | Première ouverture de l'éditeur : emprise → orientation du nord → fond → pose des parcelles ; chaque étape peut être passée |
| M5 | L'encart se masque quand tout est posé et se rouvre si une parcelle est retirée ou créée sans position (Telegram) |

### 5.12 La photo de fond (US-335)

| # | Règle |
|---|---|
| F1 | Trois fonds : Photo importée · Vue aérienne (si retenue) · Sans fond |
| F2 | Import sur ordinateur seulement, photo **privée** au potager |
| F3 | **Recalage en trois points** : l'échelle et l'angle du potager en découlent |
| F4 | Opacité 30 / 60 (défaut) / 100 % ; contour blanc des parcelles |
| F5 | En lecture : bascule « Fond masqué \| Fond 60 % » |
| F6-F7 | Mobile : le mini-plan affiche le fond, sans import ; supprimer la photo retombe sur « Sans fond » |

### 5.13 La géométrie (US-326) — garde-fous G1 à G6

G1 une seule source (superficie = longueur × largeur) · G2 une superficie déclarée est conservée jusqu'à la
pose, l'écart est signalé · G3 le rang d'une culture est une **position** · G4 rang partagé (arbitrage P4) ·
G5 le « rang multiplicateur » de la dictée est conservé (« 4 salades sur 3 rangs ») · G6 `GET /plan` expose la
géométrie et n'invente rien pour une parcelle non placée.
