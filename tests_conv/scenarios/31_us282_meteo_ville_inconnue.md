---
id: SC-212
titre: US-282 B4, B5 — lieu flou ou inconnu, il demande une ville au lieu de répondre pour le potager
tags: [us282, meteo, recette]
---

PRÉREQUIS : aucun. Le défaut visé est le repli silencieux sur la météo du potager quand le
lieu n'est pas compris. « ton potager » est le libellé qui annonce cette météo-là.

## Tour 1 — B4 : un pays n'est pas une ville
> quelle météo en Belgique ?

- texte ne contient pas: ton potager
- aucune écriture
- ? texte regex: (ville|quelle)

## Tour 2 — B5 : une ville qui n'existe pas
> météo à Zzzzville

- texte ne contient pas: ton potager
- aucune écriture
- ? texte regex: (ville|trouv|connais)
