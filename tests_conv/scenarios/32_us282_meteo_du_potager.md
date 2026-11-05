---
id: SC-213
titre: US-282 B3, B6 — la météo du potager, annoncée comme telle
tags: [us282, meteo, recette, prerequis-localisation]
---

PRÉREQUIS NON GARANTI : le potager de test doit avoir une localisation (commune ou
coordonnées). Le harnais ne la sème pas : sans elle, le bot peut demander où se trouve le
potager. Les vérifications de contenu sont donc informatives ; seule l'absence d'écriture
est bloquante. À durcir une fois la localisation semée.

## Tour 1 — B3 : la pluie chez soi
> il a plu combien chez moi ces 3 derniers jours ?

- aucune écriture
- ? texte contient: potager
- ? texte regex: (mm|pluie)

## Tour 2 — B6 : le temps du jour sans lieu
> il fait quoi aujourd'hui ?

- aucune écriture
- ? texte regex: (°|degré|ensoleill|nuage|pluie)
