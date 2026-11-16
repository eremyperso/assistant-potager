# Catalogue des fonctions de l'épic 19

*État au 16/11/2026. ✅ livrée (dans `dev`) · ⏳ non commencée. Chemins relatifs à la racine du dépôt.*

Quarante-trois fonctions, regroupées par domaine. La colonne « Où » donne le point d'entrée dans le code ;
`docs/domaines/plan-et-rangs.md` et `data/connaissance/doc_app/parcelles-et-plan.md` décrivent la conception et
l'usage.

## A. Étapes d'une culture et suivi

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F01 | **Étape courante d'une culture** : Semé → Levé → En récolte → Terminé (semis direct), Planté → En récolte → Terminé (plant), prévue ou déjà vue | US-320 | `app/services/etapes_culture.py` ; `cultures[].etapes` dans `GET /plan` | ✅ |
| F02 | **Étape prévue** d'après le calendrier recalé ; **« à confirmer »** dès que la date est atteinte, sans jamais avancer seule | US-320 | `etapes_culture.py` | ✅ |
| F03 | **Validation d'une étape par les gestes existants** : semis, levée, plantation, première récolte | US-320 | `app/services/evenements.py` | ✅ |
| F04 | **Fin de culture** : geste `fin_culture` (« arraché », « culture terminée », « rang libéré »), la culture est listée **« à libérer »** jusqu'à la libération du rang | US-320 | `parcelles[].a_liberer` ; `utils/actions.py` | ✅ |
| F05 | **Récolte végétatif / reproducteur** : un végétatif consomme les pieds (la récolte qui solde le stock termine la culture) ; un reproducteur additionne au rendement cumulé de la saison | US-320 | `etapes_culture.py` | ✅ |
| F06 | **« Pas encore »** : repousse le rappel de trois jours, sans rien écrire | US-320 | `POST /plan/etapes/pas-encore` | ✅ |
| F07 | **Langage visuel des étapes** : couleurs, pictogrammes, plein / hachuré / pastille / gris à libérer / pointillé, légende pleine et compacte, contrastes AA, thème sombre | US-321 | `frontend/src/lib/etapes.js` ; `components/ui/EtapeCulture.jsx` ; page de contrôle `/etapes` | ✅ |
| F08 | **Suivi d'une culture** (blocs S1 à S10) : localisation, place, étape, « à confirmer », cumul récolté, frise, origine, notes ; une seule lecture serveur | US-322 | `GET /plan/suivi` ; `app/services/suivi_culture.py` ; `components/SuiviCulture.jsx` ; `lib/suiviCulture.js` | ✅ |
| F09 | **Origine d'une culture** : Pépinière · lot #N (lien vers la fiche du lot), Achat, Semis direct | US-322 | `suivi_culture.py` | ✅ |

## B. Géométrie et plan sur vue du dessus

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F10 | **Géométrie enregistrée** : emprise, angle et nord du potager ; forme, position x / y, largeur, rotation, sens des rangs d'une parcelle ; position et longueur d'un rang. Superficie déduite de longueur × largeur | US-326 | `migrations/migration_v76.sql` ; `app/services/geometrie.py` ; `PATCH /plan/geometrie` | ✅ |
| F11 | **« Au rang 3 »** compris à la dictée ; la culture prend le premier rang libre sans rang dit ; le rang multiplicateur (« 4 salades sur 3 rangs ») est conservé | US-326 | `llm/parseur_deterministe.py` ; `app/services/repartition_rangs.py` | ✅ |
| F12 | **Plan vu du dessus** : parcelles à leur place, taille, rotation et échelle ; rangs en segments proportionnels, libellé selon la place, nom de parcelle en bouton ; en-tête « Au 12 novembre · 25 × 15 m » | US-327 | `frontend/src/views/PlanDessus.jsx` ; `components/PlanDessin.jsx` ; `lib/planDessus.js` ; page de contrôle `/plan-dessus` | ✅ |
| F13 | **Filtres du plan** : Tout · À confirmer · N · En récolte · Rangs libres (les segments hors filtre s'estompent) | US-327 | `filtres_plan` de `GET /plan` | ✅ |
| F14 | **Plan par zones** quand aucune parcelle n'est placée : une tuile par parcelle, dans l'ordre du chemin | US-327 | `lib/planDessus.js` | ✅ |
| F15 | **Lots de pépinière sur le plan** : vignettes (emoji, n° de lot, nom), sans étapes ; toucher un lot ouvre « Ma pépinière » | US-327 | `disposition.lots_en_cours` | ✅ |
| F16 | **Parcelle inactive grisée** : elle reste sur le plan avec son historique | US-327, US-332 | `parcelles_inactives` | ✅ |
| F17 | **Rose des vents et échelle « 5 m »** | US-327 | `components/PlanDessin.jsx` | ✅ |

## C. Aujourd'hui au potager

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F18 | **« Aujourd'hui au potager »** : listes **À confirmer · N**, **À libérer · N**, **À placer · N** (plants prêts d'un lot, cultures sans parcelle), température et alerte météo si disponibles | US-328 | `app/services/taches_plan.py` ; `components/AujourdhuiPotager.jsx` ; `lib/aujourdhui.js` | ✅ |
| F19 | **Placer une culture sur un rang libre** : glisser, ou au clavier (carte puis rang) ; rien n'est écrit, Gaston propose la carte de placement | US-328 | `app/services/compagnon/placement.py` ; champ `placement` de `POST /compagnon/messages` | ✅ |

## D. Plan sur mobile

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F20 | **Plan mobile « dans l'ordre du chemin »** : un seul écran (mini-plan, légende compacte, boutons « à confirmer » / « à libérer », une carte par parcelle, une ligne de 54 px par culture, lots de pépinière). Bascule par largeur de conteneur < 720 px | US-329 | `components/PlanMobile.jsx` ; `lib/planMobile.js` | ✅ |
| F21 | **Mini-plan à l'échelle de la largeur** de l'écran (hauteur bornée à 55 % de l'écran) | US-329 | `lib/planMobile.js` (`echelleMiniPlan`, `hauteurMaxMiniPlan`) | ✅ |
| F22 | **Plan agrandi** : bouton « Agrandir », plein écran, noms lisibles, déplacement au doigt, zoom + / − (3 crans) ; toucher une parcelle revient à sa carte | US-329 | `components/PlanAgrandi.jsx` | ✅ |
| F23 | **Aller à la carte d'une parcelle** touchée : défilement, mise en évidence, focus et annonce aux lecteurs d'écran | US-329 | `PlanMobile.jsx` (`allerA`) | ✅ |

## E. Gaston : contexte et « Noter »

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F24 | **Contexte d'écran transmis à Gaston** : culture, sinon parcelle, sinon tout le potager ; identifiants vérifiés côté serveur (404 sinon) ; gardé avec l'échange | US-323 | `app/services/compagnon/contexte_ecran.py` ; `migrations/migration_v77.sql` | ✅ |
| F25 | **Barre de contexte du panneau** : « À propos de : … », croix pour la retirer, « Préciser » sans contexte | US-323 | `components/PanneauCompagnon.jsx` ; `lib/contexteCompagnon.js` | ✅ |
| F26 | **« Noter » avec raccourcis** selon la situation : « [Étape] vue » / « Pas encore », « Récolte » / « Culture terminée », « Rang libéré », « Arrosé » / « Paillé » / « Désherbé » | US-324 | `app/services/compagnon/noter.py` ; `lib/noter.js` | ✅ |
| F27 | **Cartes de confirmation** (note, note + étape, étape, récolte, rang libéré) par le flux de propositions existant ; après confirmation, Gaston dit ce qui change et propose « Retour au plan » | US-324 | `noter.py` | ✅ |
| F28 | **Bouton « Noter » au centre de la barre basse mobile**, pastille de la sélection courante | US-325 | `frontend/src/navigation.js` ; `components/BottomNav.jsx` | ✅ |
| F29 | **Navigation mobile réorganisée** : Accueil · Plan · Noter · Pépinière · Plus (Cultures sous Plus) | US-325 | `navigation.js` | ✅ |

## F. La parcelle dans le plan

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F30 | **Détail d'une parcelle** (D1 à D6) : en-tête, géométrie, onglets En place / Lots, Caractéristiques, Rotation, Entretien ; panneau de droite sur ordinateur, feuille plein écran sur mobile | US-330 | `components/DetailParcelle.jsx` | ✅ |
| F31 | **Bascule « Plan \| Liste »** avec la même sélection ; la liste inclut les parcelles non placées | US-330 | `views/PlanDessus.jsx` | ✅ |
| F32 | **Liens directs et anciens liens redirigés** : `/?vue=plan&parcelle=12` ; l'ancien onglet « Parcelles » n'existe plus | US-330 | `lib/intentions.js` (`VUES_REDIRIGEES`) | ✅ |
| F33 | **Caractéristiques d'une parcelle** : lire et modifier exposition, sol, abri, paillage, type de pépinière, nombre de rangs ; dimensions et statut verrouillés ; confirmation en quittant | US-331 | `DetailParcelle.jsx` ; `PATCH /parcelles/{id}` | ✅ |
| F34 | **Créer une parcelle avec Gaston** : nom unique proposé, dimensions, géométrie enregistrée en même temps | US-332 | `app/services/plan_gaston.py` | ✅ |
| F35 | **Rendre inactive / réactiver** : bilan des cultures et de l'historique, parcelle grisée mais conservée ; les gestes ne sont plus détachés | US-332 | `app/services/retrait_parcelle.py` | ✅ |
| F36 | **Supprimer une parcelle vide** (suppression réelle) ; refusée pour une parcelle qui a vécu, Gaston propose l'inactivation | US-332 | `retrait_parcelle.py` | ✅ |

## G. Éditeur du plan et mise en place

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F37 | **Éditeur du plan** (ordinateur, membre éditeur) : poser, déplacer, redimensionner, tourner, dupliquer, retirer ; aimantation tous les 50 cm ; quatre formes (planche, bac, pépinière, serre) ; saisie au clavier | US-333 | `components/EditeurPlan.jsx` ; `lib/editeurPlan.js` | ✅ |
| F38 | **Enregistrement du plan en un appel**, tout ou rien | US-333 | `POST /plan/edition` ; `geometrie.enregistrer_plan` | ✅ |
| F39 | **Orientation du nord** (rose des vents, huit directions) reprise par le plan en lecture | US-333 | `EditeurPlan.jsx` | ✅ |
| F40 | **Contrôle de cohérence de surface** : propose d'aligner la fiche, n'aligne jamais seul | US-333 | `lib/editeurPlan.js` | ✅ |
| F41 | **Encart « Mettre en place le plan · environ 5 minutes »**, puis « N parcelles à placer » ; se masque quand tout est posé, revient si une parcelle est retirée ou créée sans position | US-334 | `lib/miseEnPlace.js` ; `views/PlanDessus.jsx` | ✅ |
| F42 | **Assistant de mise en place** en quatre étapes passables (emprise, nord, fond, pose) ; fin de l'assistant « Premier potager » qui propose « maintenant » ou « plus tard » ; adresse `/?vue=plan-vue&editeur=oui` | US-334 | `components/AssistantMiseEnPlace.jsx` ; `ProposerMiseEnPlace.jsx` ; `views/Onboarding.jsx` | ✅ |

## H. Photo de fond

| ID | Fonction | US | Où | |
|---|---|---|---|---|
| F43 | **Photo du potager en fond** : import (ordinateur), recalage en trois points (échelle et angle), opacité 30 / 60 / 100 %, bascule « Fond masqué \| Fond 60 % », suppression, purge avec le potager | US-335 | à créer (migration prévue) | ⏳ bloquée par P2 |

## Transverses

- **Lecture seule** : un membre en lecture n'a ni « Noter », ni « Modifier », ni création / retrait de parcelle.
- **Accessibilité** : chaque segment est un bouton au nom accessible complet (« Fève, Levé, prévu, à confirmer,
  Planche centrale rang 6 ») ; cibles de 44 px sur mobile ; focus rendu à la fermeture d'une fenêtre ; Échap.
- **Responsive** : bascule mobile / ordinateur par largeur de **conteneur** (720 px), jamais par largeur d'écran.
- **Corpus** : chaque livraison met à jour `parcelles-et-plan.md` et le guide utilisateur (2 copies).
