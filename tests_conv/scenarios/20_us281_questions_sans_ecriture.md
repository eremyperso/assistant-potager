---
id: SC-201
titre: US-281 A1-A3 et A8 — questions et demandes incomplètes, aucune carte, aucune écriture
tags: [us281, garde-fous, recette]
parcelles: [Planche sud, Serre]
---

PRÉREQUIS : les parcelles « Planche sud » et « Serre » (créées avant le passage). Aucun
historique. Chaque tour doit rester en texte : pas de carte, pas d'écriture.

## Tour 1 — A1 : une question sur la suppression n'est pas une suppression
> est-ce que je peux supprimer la planche sud sans perdre mon historique ?

- aucun bouton
- aucune écriture

## Tour 2 — A2 : renommer sans nouveau nom, il demande le nom
> renomme la planche sud

- aucun bouton
- aucune écriture
- ? texte regex: (nom|appel)

## Tour 3 — A3 : « enlève » est ambigu, il demande ce qu'on veut
> enlève la serre

- aucun bouton
- aucune écriture

## Tour 4 — A8 : un symptôme appelle un conseil, pas une écriture
> mes tomates ont du mildiou

- aucun bouton
- aucune écriture
- ? texte contient: mildiou
