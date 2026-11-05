---
id: SC-233
titre: US-284 D3 — une autre question efface la question en attente
tags: [us284, question-en-attente, recette]
parcelles: [Planche test, Plant tubercule]
---

PRÉREQUIS : deux parcelles aux noms voisins (comme SC-231). La question en attente du tour 1
doit être abandonnée quand le tour 2 parle d'autre chose, sans réclamer « Laquelle ? ».

## Tour 1 — la question en attente
> Supprime la planche

- aucune écriture
- aucun bouton

## Tour 2 — on change de sujet
> au fait, il pleut ?

- aucune écriture
- aucun bouton
- texte ne contient pas: Laquelle
- ? texte regex: (pluie|pleu|météo|meteo)
