# ÉPIC 21 — Recette du socle commun des vues (US-359)

Recette du 25/11/2026, branche `ergo_socle_commun`, v3.146.0. **Elle est partielle** : ce fichier dit ce qui a été
vérifié, comment, et surtout ce qui ne l'a pas été. La comparaison à l'œil, capture contre capture, des quatorze écrans
de la maquette reste à faire (voir « Ce qui n'a pas pu être fait »).

## Méthode

Pile isolée, comme dans `frontend/CLAUDE.md` : base SQLite jetable, API sur 8011, Vite sur 5173 ; les serveurs 3000
et 8000 de l'utilisateur n'ont pas été touchés. Le compte de recette est **vide** (un potager, aucune parcelle, aucune
culture).

Le navigateur de chrome-devtools était indisponible (son profil était déjà ouvert par une autre instance). La recette
est passée par Claude in Chrome : la fenêtre ne se redimensionnant pas, chaque écran a été chargé dans une **iframe de
375, 768 et 1440 px de large** (les requêtes de média répondent à la largeur de l'iframe), en thème clair puis sombre.

## CA1, CA2 — ce qui a été vérifié

Cinq écrans × trois largeurs × deux thèmes = 30 chargements : Tableau de bord, Plan, Cultures, Pépinière, Journal.

| Contrôle | Résultat |
|---|---|
| Débordement horizontal (`scrollWidth` > largeur) | aucun, aux 30 chargements |
| Thème sombre appliqué | oui, aux 15 chargements sombres |
| En-tête de page (`h1`) | présent : « Tableau de bord », « Plan des parcelles », « Mes cultures », « Ma pépinière », « Journal du potager » |
| Menu ⋯ dans la barre d'outils | présent sur Plan, Cultures, Pépinière, Journal ; absent du Tableau de bord (il n'a pas de barre d'outils, voulu) |
| Bouton **Noter** (seule porte) | présent sur les cinq écrans |
| Barre basse à 375 px | Accueil, Plan, Noter, Pépinière, Plus |

Gaston a été vérifié séparément pendant US-358, dans le DOM : ouverture sur la culture (« Vous êtes sur fève. Dites ce
que vous voyez, ou touchez une suggestion. »), suggestions selon l'étape, phrase d'ajout pré-écrite dans le champ,
bandeau « Céleri-rave · catalogue », « Pas encore » qui propose le report avant d'écrire.

Capture : [aide de la vue, Pépinière, 375 px](recette/aide-de-la-vue-pepiniere-375.png) — menu ⋯ › Aide de la vue, avec
la section du guide et « Demander à Gaston ».

## Ce qui n'a pas pu être fait

- **Comparaison à la maquette, écran par écran.** Aucune capture n'a été mise côte à côte avec la maquette
  (`maquette/`) : les contrôles ci-dessus sont des mesures du DOM, pas un jugement visuel.
- **Données réelles.** Avec un potager vide, les écrans montrent leurs états vides ; la frise des étapes, les cartes de
  culture, le registre des lots, les Récoltes par saison, les couleurs d'étape en clair et en sombre n'ont pas été vues
  remplies.
- **Écrans non parcourus ici** : Stocks, Récoltes par saison, Pépinière · Semer et Lots (onglets), fiche du lot, fiche
  commune, Gaston via Noter, Ajouter une culture. Leurs tests unitaires passent ; ils n'ont pas été regardés.
- **768 px** : seul le débordement a été mesuré.

À reprendre avec un potager rempli (le potager rempli du jeu d'évaluation, `tools/creer_potager_test_rempli.py`) et un
navigateur redimensionnable.

## Écarts connus (hérités des US précédentes)

- Le **fond photo du Plan** n'existe pas (US-335 absente) : le bandeau dit « Fond masqué · grille ».
- La mention **« Dicté / Écrit »** des notes n'est pas dite : le serveur ne garde pas l'origine d'une note ; seule la
  relecture du fil l'a en mémoire locale.
- La phrase « Votre châssis aura de la place après… » du Mot du Catalogue n'est pas écrite (aucune donnée).
- Le **Mot du Tableau de bord** ne dit pas « Voilez la mâche… » (aucune donnée sur la sensibilité au gel).
- La navigation annonce encore « Catalogue · à venir » (grisé) alors que l'onglet Catalogue existe dans Cultures.
- Le bouton **Semer** d'une tuile de l'onglet Semer ouvre désormais Gaston au lieu de déposer le geste dans la file
  (US-224) : c'est la porte voulue par US-358, mais le dépôt direct a disparu de cet écran.
- Le **Tableau de bord** n'a pas de menu ⋯, donc pas d'« Aide de la vue » : il n'a pas de barre d'outils.

## CA3 — nettoyage

`BoutonCompagnon`, `DateRefPicker`, `BarreActivitePlan`, `ModalPersonnaliserDashboard` et `useDashboardWidgets`
étaient déjà supprimés par US-353 et US-354 ; un test (`us359_recette_socle.test.js`) vérifie leur absence et
qu'aucun import ne les vise. `CarteProposition` est déjà la ligne de la carte « À enregistrer » (US-357).
**`MonthStrip` est conservé** : la fiche calendrier l'utilise encore. Aucun aperçu `_…Preview` ne vise un écran
disparu : tous montrent un composant encore utilisé. `npm run build` passe ; la suite front passe à 1245/1247, les deux
échecs (archivage des potagers) étant ceux de HEAD.

## CA4 à CA6 — guide, aide, corpus

- Guide (deux copies, `docs/MANUEL/` et `data/connaissance/guide user/`) : nouvelle section 4.5 « Les écrans, un par
  un », sections 4.3, 4.4, 8.8, 15.3, 17.6 quater et météo mises à jour ; plus aucune mention du médaillon, de
  « Parcourir » ni de la personnalisation du tableau de bord (testé).
- Aide de la vue : menu ⋯ › « Aide de la vue » ouvre une fenêtre par vue (Statistiques, Plan, Cultures, Pépinière,
  Stocks, Journal) qui renvoie à la section 4.5 du guide et propose « Demander à Gaston ».
- Corpus : fiches `compagnon-reponses-et-memoire`, `journal-et-corrections` et `cultures-familles-et-rotation`
  (nouvelle section « Ajouter à mon potager une culture du catalogue »), quatre questions de mesure ajoutées dont « où
  sont les exports ? » et « comment ajouter une culture du catalogue ? ». Corpus réingéré en dev et en test.
  `test_us099` et `test_us140` passent (108 tests). **Aucune mesure sur le vrai modèle** (pas d'accord).
