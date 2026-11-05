---
id: SC-261
titre: US-287 G1 — « annule » juste après un geste donne une carte d'annulation
tags: [us287, bascule, critique, recette, prerequis-conversation]
parcelles: [Serre]
---

PRÉREQUIS CRÉÉ PAR LE SCÉNARIO : une plantation confirmée (tours 1 et 2). Le tour 3 doit
proposer d'annuler CE geste ; la carte ne doit pas être confirmée ici.

## Tour 1 — mise en place : le geste
> j'ai planté 12 tomates dans la serre

- bouton: Confirmer

## Tour 2 — le confirmer
[clic] Confirmer

- ecriture: plantation

## Tour 3 — l'annulation
> annule

- aucune écriture
- texte regex: annul
- ? bouton: Confirmer
- ? outil: annuler_action
