# Maquettes haute fidélité — écrans des épics 9 à 12

Ce dossier porte les maquettes **gelées avant le code** au sens de la règle RT9
du plan des épics 9 à 12. Elles viennent du projet Claude Design
« potager 2026 » (`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`) et font foi sur le
rendu, là où les wireframes de `../wireframes/` font foi sur la structure et
les règles.

| Fichier | Source Claude Design | Gelée le | Écran | US |
|---|---|---|---|---|
| `Plan - Rangs et places.html` | `Plan - Rangs et places.html` | 23/09/2026 | Plan · Vue plan (niveau 1) | US-200, US-225, US-226, US-227, US-228 |
| `Cultures - Ecran et fiche.html` | `Cultures - Ecran et fiche.html` | 25/09/2026 | Cultures · écran et fiche culture | US-204, US-205, US-206, US-207 |

## Ce que la maquette du 25/09 ajoute au wireframe v1

Elle fait foi sur le **rendu** et sur le **full responsive** de l'ÉPIC 11 :

1. **Écran** — grille de cartes en container queries (1 / 2 / 3 colonnes à 520 et
   900 px de conteneur, contenu plafonné à 1320 px) et **deux formes de barre
   d'outils** : large (date, recherche, tri, mois, familles, légende dépliée) ou
   étroite à 375 px (onglets pleine largeur, panneaux repliables *Filtres* — avec
   compteur et « Tout effacer » — et *Légende*). Cinq états rejoués.
2. **Fiche** — trois dispositions : feuille plein écran (375), modale centrée
   (768), **panneau latéral de 560 px** (1180). Container query interne à 400 px
   pour la grille *Référentiel*, pied persistant (sources + Fermer), badge de
   contexte « depuis <parcelle> · rang N ». Sept états rejoués.
3. **Quatrième pastille de phase « En pépinière »** et pastilles pointillées
   « pas au potager » / « suggestion — pas au potager ».

⚠️ Contrairement à la maquette du 23/09, celle-ci **n'est pas autonome** : elle
charge six fichiers `.jsx` frères, présents dans ce dossier. Ouvrir le HTML par
`file://` peut être bloqué par la politique CORS du navigateur ; servir le dossier
(`python -m http.server`) suffit.

## Ce que la maquette du 23/09 ajoute au wireframe v3

1. La parcelle porte une **longueur** unique, base de calcul de tous ses rangs
   (US-225). La largeur s'en déduit et ne s'affiche que pour mémoire.
2. Un rang n'est plus un trait de longueur relative : c'est une **piste de
   places**, `places = ⌊ longueur × 100 ÷ espacement sur le rang ⌋`
   (US-226, US-227), remplie de pictogrammes de culture et de places
   restantes en creux (US-228).
3. La longueur relative du wireframe v3 devient le **mode dégradé** : c'est ce
   que la maquette dessine pour une parcelle sans longueur, avec « N places ? ».

Ouvrir le fichier dans un navigateur suffit : aucune dépendance, données
d'exemple en dur dans le `<script>` final.
