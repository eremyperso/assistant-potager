# Maquettes haute fidélité — écrans de l'activité Plan

Ce dossier porte les maquettes **gelées avant le code** au sens de la règle RT9
du plan des épics 9 à 12. Elles viennent du projet Claude Design
« potager 2026 » (`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`) et font foi sur le
rendu, là où les wireframes de `../wireframes/` font foi sur la structure et
les règles.

| Fichier | Source Claude Design | Gelée le | Écran | US |
|---|---|---|---|---|
| `Plan - Rangs et places.html` | `Plan - Rangs et places.html` | 23/09/2026 | Plan · Vue plan (niveau 1) | US-200, US-225, US-226, US-227, US-228 |

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
