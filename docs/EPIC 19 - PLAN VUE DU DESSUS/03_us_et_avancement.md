# Les US de l'épic 19 et leur avancement

*État au 16/11/2026. Fiches : `backlog/US-320_…` à `backlog/US-335_…`. Fonctions : voir `02_fonctions.md`.*

**Légende** — ✅ livrée, dans `dev` · 🔒 bloquée · « Revue en cours » = statut Jira (aucune US n'est encore « Terminée »).

## 1. Tableau de bord

| Ordre | US | Titre | Pts | Modèle · effort conseillé | Jira | Version | État |
|---|---|---|---|---|---|---|---|
| 1 | **US-320** | Suivre les étapes d'une culture, prévues puis validées | 8 | Opus 5.5 · high | PIA-304 | v3.128.0 | ✅ |
| 2 | **US-321** | Dessiner l'étape d'une culture avec un langage visuel commun | 3 | Sonnet 5.5 · medium | PIA-305 | v3.128.0 | ✅ |
| 3 | **US-326** | Enregistrer la géométrie du potager, des parcelles et des rangs | 8 | Opus 5.5 · high | PIA-306 | v3.128.0 | ✅ |
| 4 | **US-327** | Afficher le plan du potager vu du dessus | 8 | Sonnet 5.5 · high | PIA-307 | v3.128.0 | ✅ |
| 5 | **US-322** | Ouvrir le suivi d'une culture depuis le plan | 5 | Sonnet 5.5 · medium | PIA-308 | v3.128.0 | ✅ |
| 6 | **US-323** | Transmettre à Gaston ce que le jardinier a sous les yeux | 5 | Opus 5.5 · high | PIA-309 | v3.128.0 | ✅ |
| 7 | **US-324** | Noter ce que je vois avec Gaston, d'un seul bouton | 8 | Opus 5.5 · high | PIA-310 | v3.128.0 | ✅ |
| 8 | **US-325** | Placer « Noter » au centre de la barre basse mobile | 2 | Sonnet 5.5 · medium | PIA-311 | v3.128.0 | ✅ |
| 9 | **US-328** | Lister ce qui est à confirmer, à libérer et à placer aujourd'hui | 5 | Sonnet 5.5 · high | PIA-312 | v3.128.0 | ✅ |
| 10 | **US-329** | Parcourir le plan sur mobile dans l'ordre du chemin | 5 | Sonnet 5.5 · medium | PIA-313 | v3.128.0 | ✅ |
| 11 | **US-330** | Ouvrir le détail d'une parcelle dans le plan | 8 | Sonnet 5.5 · high | PIA-314 | v3.128.0 | ✅ |
| 12 | **US-331** | Lire et modifier les caractéristiques d'une parcelle dans le plan | 3 | Sonnet 5.5 · medium | PIA-315 | v3.128.0 | ✅ |
| 13 | **US-332** | Créer, rendre inactive ou supprimer une parcelle avec Gaston | 5 | Opus 5.5 · high | PIA-316 | v3.128.0 | ✅ |
| 14 | **US-333** | Modifier le plan sur ordinateur : poser, dimensionner, orienter | 8 | Opus 5.5 · high | PIA-317 | v3.128.0 | ✅ |
| 15 | **US-334** | Mettre en place le plan d'un potager nouveau ou existant | 3 | Sonnet 5.5 · medium | PIA-318 | **v3.129.0** | ✅ |
| 16 | **US-335** | Poser le plan sur une photo du potager vue du dessus | 8 | Opus 5.5 · high | *à créer* | — | 🔒 P2 (RGPD) |
| | | **Total** | **92** | | | | **84 livrés · 8 restants** |

Production de référence : Opus pour ce qui écrit des données ou touche la boucle de l'agent (50 pts), Sonnet
`high` pour 21 pts, Sonnet `medium` pour 21 pts. Fable n'est requis pour aucune US.

## 2. Dépendances

```
US-320 étapes ─┬─► US-321 langage visuel ─┐
               │                           ├─► US-327 plan ─┬─► US-322 suivi ───────┐
US-326 géométrie ───────────────────────────┘                ├─► US-328 Aujourd'hui ─┤─► US-329 plan mobile
                                                             │                       │
US-323 contexte ─► US-324 Noter ─► US-325 barre basse                                ┘

US-327 + US-322 ─► US-330 détail parcelle ─► US-331 caractéristiques
US-323 + US-326 ─► US-332 créer / inactiver / supprimer ─► US-333 éditeur ─► US-334 mise en place
                                                                        └─► US-335 photo (bloquée P2)
```

## 3. Détail par US

Pour chaque US : ce qui est livré, l'écart éventuel avec la fiche, ce qui reste. Source : fiches du backlog,
notes de livraison, `PATCH_NOTES.md`, contrôle du code.

### US-320 — Étapes d'une culture · PIA-304 · 8 pts

- **Livré** : étapes courantes, prévues, à confirmer, validées par les gestes ; fin de culture ; « Pas encore » ;
  rendement cumulé des reproducteurs ; « à libérer ». Tests : `tests/test_us320_etapes_culture.py`.
- **Écarts** : arbitrage P3 — **pas d'étape « En croissance » ni « En fleur »** (la fiche les prévoyait) ;
  « arraché » = fin de culture, sauf « arraché par … » = perte. **Aucune migration propre** : « Pas encore » réutilise
  le rappel d'US-266. L'historique « arraché » déjà enregistré en perte n'a pas été repris.
- **Reste** : rien de vérifié sur Telegram (phrases d'étape) ni avec le vrai modèle. Une fin de culture ambiguë
  n'est refusée qu'à l'écriture, après la confirmation.

### US-321 — Langage visuel des étapes · PIA-305 · 3 pts

- **Livré** : `lib/etapes.js`, `components/ui/EtapeCulture.jsx`, tokens `--etape-*` clair et sombre, légende pleine
  et compacte, page de contrôle `/etapes`. Tests : `frontend/src/lib/etapes.test.js` (22 tests, contrastes AA).
- **Reste** : la section « Langage visuel commun » de la maquette n'a pas été vue au moment du codage — **couleurs et
  pictogrammes à comparer à la maquette**.

### US-322 — Suivi d'une culture · PIA-308 · 5 pts

- **Livré** : `GET /plan/suivi`, `SuiviCulture.jsx`, blocs S1 à S10, bouton Photo désactivé. Tests :
  `tests/test_us322_suivi_culture.py`, `lib/suiviCulture.test.js`.
- **Écart** : l'icône micro d'une note dictée n'est jamais affichée, faute de donnée « note dictée ».

### US-323 — Contexte d'écran pour Gaston · PIA-309 · 5 pts

- **Livré** : contexte (culture, parcelle, rang) accepté par `POST /compagnon/messages`, 404 pour un identifiant
  étranger, barre « À propos de », migration **v77**. Tests : `tests/test_us323_contexte_ecran.py`,
  `lib/contexteCompagnon.test.js`.
- **Reste** : **CA7 — mesure sur le vrai modèle non faite** (accord du responsable produit requis).

### US-324 — Noter avec Gaston · PIA-310 · 8 pts

- **Livré** : raccourcis, cartes note / note + étape / récolte / rang libéré, « Retour au plan ». « Fleur » reste une
  observation (P3). Tests : `tests/test_us324_noter_gaston.py`, `lib/noter.test.js`.
- **Reste** : **recette sur le vrai modèle non faite** ; phrases d'étape sur Telegram non vérifiées (CA8).

### US-325 — « Noter » au centre de la barre basse · PIA-311 · 2 pts

- **Livré** : `NAV_MOBILE` et `barreBasse()` dans `navigation.js`, pastille de la sélection, arbitrage P1 tranché
  (Cultures sous Plus). Sur mobile, fermer la feuille du suivi garde la sélection. Tests : `frontend/src/navigation.test.js`.

### US-326 — Géométrie du potager · PIA-306 · 8 pts

- **Livré** : migration **v76**, `app/services/geometrie.py`, `PATCH /plan/geometrie`, « au rang 3 » au parseur
  déterministe. Arbitrages P4 et P7. Tests : `tests/test_us326_geometrie_plan.py`.
- **Écart** : un rang ne se partage entre cultures que si la parcelle a une longueur, sinon une culture par rang.
- **Reste** : **US-203 (PIA-155) absorbée mais pas fermée dans Jira** ; rien vérifié sur Telegram ni avec le vrai modèle.

### US-327 — Plan vu du dessus · PIA-307 · 8 pts

- **Livré** : `PlanDessus.jsx`, `PlanDessin.jsx`, `lib/planDessus.js`, filtres, plan par zones, rose des vents,
  page `/plan-dessus`. `GET /plan` sert aussi `lots_en_cours`, `parcelles_inactives`, `filtres_plan`. Tests :
  `tests/test_us327_plan_vue_du_dessus.py`, `lib/planDessus.test.js`.
- **Écart** : l'ancienne vue (`PlanVue.jsx`, `CartePlanParcelle.jsx`, `RangPlan.jsx`) est **supprimée** ; les places
  quittent le plan (régression annoncée dans les patch notes).
- **Reste** : comparaison point par point à la maquette.

### US-328 — Aujourd'hui au potager · PIA-312 · 5 pts

- **Livré** : `taches_plan.py`, `placement.py`, listes À confirmer / À libérer / À placer, placement par glisser ou
  clavier via Gaston, plantation depuis un lot. Tests : `tests/test_us328_aujourdhui_au_potager.py`,
  `lib/aujourdhui.test.js`.
- **Note** : le placement se construit **sans modèle** ; la recette sur le vrai modèle n'est donc pas requise.

### US-329 — Plan mobile · PIA-313 · 5 pts

- **Livré** : `PlanMobile.jsx`, `lib/planMobile.js`, `ParcellePlan mini`, bascule à 720 px de conteneur. Recette
  faite à 375, 768 et 1280 px. Tests : `lib/planMobile.test.js`.
- **Ajout hors fiche** (13/11) : le mini-plan était plafonné à 200 px de haut et illisible ; l'échelle suit
  maintenant la largeur de l'écran, et le bouton **« Agrandir »** ouvre un plan plein écran (`PlanAgrandi.jsx`).
  Écarté : le glissement vertical dans un cadre à hauteur fixe (conflit avec le défilement de la page).

### US-330 — Détail d'une parcelle dans le plan · PIA-314 · 8 pts

- **Livré** : `DetailParcelle.jsx` (D1 à D6), bascule Plan | Liste, état exact conservé, liens directs, anciens
  liens redirigés ; **onglet « Parcelles » supprimé** (`views/Plan.jsx` retiré). Tests :
  `lib/parcelleDansPlan.test.js`. Vérifié à 1280 et 375 px (pas à 768).
- **Écart** : l'onglet Rotation renvoie à une « vue détaillée dans la tuile Rotation (à venir) », qui n'existe pas encore.

### US-331 — Caractéristiques d'une parcelle · PIA-315 · 3 pts

- **Livré** : lecture et modification par `PATCH /parcelles/{id}`. Tests : `tests/test_us331_caracteristiques_plan.py`.
- **Écart** : le type **« Châssis »** est absent de la liste (elle vient de `geometrie.FORMES`, faute de migration).

### US-332 — Créer, inactiver, supprimer avec Gaston · PIA-316 · 5 pts

- **Livré** : `retrait_parcelle.py` (bilan, inactiver, réactiver, supprimer une parcelle vide), `plan_gaston.py`.
  Tests : `tests/test_us332_retrait_parcelle.py`.
- **Changement de comportement à connaître** : rendre inactive (`actif = false`) **ne détache plus les gestes** (US-009
  les passait en « Non localisé ») ; `resolve_parcelle` ne rend plus une parcelle inactive ; `/parcelle supprimer`
  d'une parcelle qui a vécu est refusé et propose l'inactivation.
- **Reste** : intentions créer / inactiver / supprimer non vérifiées sur Telegram.

### US-333 — Éditeur du plan · PIA-317 · 8 pts

- **Livré** : `EditeurPlan.jsx`, `lib/editeurPlan.js`, `POST /plan/edition` (tout ou rien), bouton « Modifier le plan »
  (≥ 720 px, éditeur seulement). Tests : `tests/test_us333_edition_plan.py`, `lib/editeurPlan.test.js`.
- **Limites connues** : « Dupliquer » et « Poser au centre » superposent sans chercher de place libre ; l'éditeur
  montre le plan droit (l'angle du potager n'est pas appliqué à l'édition) ; recette à 1280 et 1024 px seulement
  (à 375 px le bouton est absent, par conception).

### US-334 — Mise en place du plan · PIA-318 · 3 pts · livrée le 14/11

- **Livré** : encart « Mettre en place le plan », assistant en quatre étapes passables, fin de l'assistant « Premier
  potager », message sur téléphone, adresse `/?vue=plan-vue&editeur=oui`. Commit `020287f`, v3.129.0. Tests :
  `lib/miseEnPlace.test.js`.
- **Reste** : l'étape « fond » de l'assistant ne propose que « Sans fond » tant qu'US-335 n'est pas livrée.

### US-335 — Photo de fond et recalage · aucun ticket · 8 pts

- **Non commencée.** Dépend d'US-326, US-327, US-333 (livrées) **et de l'arbitrage RGPD P2** : une photo de potager
  est une donnée personnelle. À prévoir : migration (source du fond, trois points de recalage, opacité), stockage
  privé aux membres, purge avec le potager (US-084), mention dans les conditions d'usage et la politique de
  confidentialité, éventuellement vue aérienne (source, licence et coût à documenter avant).

## 4. Migrations

| Migration | US | Contenu | Dev | Production |
|---|---|---|---|---|
| `migration_v76.sql` (+ rollback) | US-326 | Emprise, angle, nord du potager ; forme, x, y, largeur, rotation, sens des rangs des parcelles ; position et longueur d'un rang | jouée (déploiement) | **non** |
| `migration_v77.sql` (+ rollback) | US-323 | `echanges_conversation.contexte` (JSONB), sous la RLS existante | jouée (déploiement) | **non** |

Les numéros v73 à v75 appartiennent à la branche du pilotage LLM (épic 18) : leur absence est volontaire.

## 5. Incidents rencontrés

| Date | Incident | Cause | Résolution |
|---|---|---|---|
| 13/11 | Déploiement dev en échec à l'ingestion du corpus ; sur dev, le suivi d'une culture affichait « Unexpected token '<', "<!doctype"… is not valid JSON » | La section 4 du guide dépassait 4 096 caractères (limite Telegram) ; le workflow s'est arrêté **avant** le redémarrage, donc le nouveau front tournait avec l'ancienne API | Sous-section 4.4 passée en niveau 2 (`1eb6e66`), puis redéploiement vert (PR #194) |
| 13/11 | Test US-304 en échec | Il cherchait « ### 17.6 ter », passé en « ## » par un correctif précédent | Test aligné sur le titre de niveau 2 (`1eb6e66`) |

## 6. Écarts entre la fiche et le livré

1. **P3** : pas d'« En croissance » ni d'« En fleur » — les fiches US-320 (CA2, E4) et US-321 (V1) les décrivent encore.
2. **US-320** : « Migration : oui » dans la fiche, **aucune migration propre** dans le livré.
3. **US-331** : liste des types sans « Châssis ».
4. **US-329** : plan agrandi et échelle sur la largeur ajoutés, hors fiche.
5. **US-332** : inactiver ne détache plus les gestes (changement de comportement d'US-009).
6. **US-322** : pas d'icône « note dictée ».

→ À reporter dans les fiches du backlog à la clôture de l'épic.

## 7. Reste à faire

| # | Action | Responsable |
|---|---|---|
| 1 | Comparer les écrans livrés à la maquette (US-321 à US-334) | produit + QA |
| 2 | Recette sur le vrai modèle d'US-323 (CA7) et d'US-324, avec accord et volume annoncé | produit |
| 3 | Vérifier sur Telegram : phrases d'étape, « au rang 3 », créer / inactiver / supprimer | QA |
| 4 | Trancher **P2** (RGPD de la photo), puis créer le ticket Jira et réaliser **US-335** | produit |
| 5 | Fermer US-203 (PIA-155) dans Jira ; passer les US recettées de « Revue en cours » à « Terminé » | produit |
| 6 | Mettre à jour les fiches du backlog selon la section 6 | dev |
| 7 | Promouvoir en production : PR `dev` → `main`, migrations v76 et v77 comprises | dev |
