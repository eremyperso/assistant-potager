---
id: SC-203
titre: US-281 A5 — créer quatre planches dont une existe déjà
tags: [us281, garde-fous, recette]
parcelles: [Est]
---

PRÉREQUIS : la parcelle « Est » existe déjà (c'est le piège). Les trois autres n'existent pas.
La vérification fine (« Est » signalée existante, trois autres proposées, pas de recréation)
se lit dans la transcription du rapport : le texte du bot n'est pas figé.

## Tour 1 — la demande de quatre planches
> crée les planches Nord, Sud, Est, Ouest

- aucune écriture
- ? texte regex: (existe|déjà|deja)
- ? texte contient: Nord
- ? texte contient: Ouest
