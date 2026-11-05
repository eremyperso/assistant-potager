---
id: SC-251
titre: US-286 F3, F6 — « vide le geste » et « qu'est-ce que j'ai en attente ? » sans rien en attente
tags: [us286, file-gestes, recette]
---

PRÉREQUIS : aucun, et c'est le point. Le passage commence par une remise à zéro : aucun geste
n'est en attente. Le bot doit le dire, sans rien écrire dans le carnet.

Non couverts ici (le harnais ne sait pas faire envoyer un message au bot de lui-même) :
F1, F4, F5, qui demandent un message envoyé par le bot avant la réponse du jardinier.

## Tour 1 — F3 : vider une file vide
> vide le geste

- aucune écriture
- aucun bouton
- ? texte regex: (rien|aucun|plus)

## Tour 2 — F6 : lister une file vide
> qu'est-ce que j'ai en attente ?

- aucune écriture
- ? texte regex: (rien|aucun|plus)
