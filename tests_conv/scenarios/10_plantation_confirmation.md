---
id: SC-010
titre: Plantation dictée — récapitulatif, puis écriture seulement après confirmation
tags: [critique, plantation]
passages: 3
seuil: 0.67
parcelles: [Serre]
---

Le geste est dicté en langage naturel. Le bot doit proposer un récapitulatif SANS rien
écrire, puis enregistrer au clic sur « Confirmer ».

À calibrer au premier passage réel : le libellé exact des boutons et du récapitulatif.

## Tour 1 — la dictée
> j'ai planté 12 tomates dans la serre

- bouton: Confirmer
- texte contient: tomate
- aucune écriture

## Tour 2 — la confirmation
[clic] Confirmer

- écriture: plantation
- événement: culture=tomate, quantite=12, parcelle=Serre
