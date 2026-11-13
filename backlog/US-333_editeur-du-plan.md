**ID :** US-333
**Titre :** Modifier le plan sur ordinateur : poser, dimensionner, orienter les parcelles
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier sur ordinateur ou tablette
Je veux poser mes parcelles sur le plan, les dimensionner, les tourner et indiquer le sens des rangs et le nord
Afin que le plan devienne une image fidèle de mon potager, sans avoir à dessiner librement

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Ordinateur · Modifier le plan (piste C) » et « Mettre en place le plan ». Cette US livre l'éditeur **sur fond neutre** (grille aimantée, piste A) ; le fond photo et le recalage en trois points sont l'objet d'US-335.

**Écran « Modifier le plan » :**

| Zone | Contenu |
|---|---|
| En-tête | « Modifier le plan », état du recalage, **Annuler** / **Enregistrer** |
| Colonne gauche | Fond du plan (US-335 ; ici « Sans fond »), **À placer · N** (parcelles sans position), **Nouvelle parcelle** (quatre formes : Planche, Bac, Pépinière, Serre), **Orientation** (rose des vents, huit directions, « Nord en haut du plan ») |
| Centre | le plan, parcelles posées, parcelle sélectionnée avec poignées de redimensionnement et de rotation, cotes (« 12 m », « 5 m », « −2,5° · aligné sur le potager »), barre flottante **Rangs ↔ / ↕ · Dupliquer · Retirer du plan** |
| Colonne droite | parcelle sélectionnée : forme, longueur, largeur, contrôle de cohérence de surface (« Surface posée 60 m², fiche parcelle 69 m² — Mettre la fiche à 60 m² »), sens des rangs, nombre de rangs, angle (celui du potager, déverrouillable pour une parcelle de travers), lien « Caractéristiques → » |

**Règles :**

| # | Règle |
|---|---|
| E1 | Les parcelles s'alignent sur l'angle du potager et s'**aimantent tous les 50 cm** ; **quatre formes seulement, pas de dessin libre** |
| E2 | Poser une parcelle existante : la glisser depuis « À placer » ; elle prend ses dimensions connues, sinon un carré déduit de sa superficie |
| E3 | Poser une **forme nouvelle** ouvre Gaston ; la parcelle n'est créée qu'après confirmation (US-332) |
| E4 | « Retirer du plan » efface la position, pas la parcelle : elle revient dans « À placer » |
| E5 | Les modifications ne sont écrites qu'à **Enregistrer**, en une fois ; **Annuler** ou quitter les abandonne, avec confirmation si quelque chose a changé |
| E6 | Réduire le nombre de rangs sous le nombre de rangs occupés est refusé avec l'explication |
| E7 | **Pas de modification du plan sur mobile** : l'entrée « Modifier le plan » n'y est pas proposée |

**Critères d'acceptance :**
- [ ] CA1 : L'éditeur s'ouvre depuis le plan (« Modifier le plan ») et depuis « Ajuster sur le plan » d'une parcelle, celle-ci sélectionnée
- [ ] CA2 : Poser, déplacer, redimensionner, tourner, dupliquer et retirer une parcelle respectent E1 à E4 ; toutes les valeurs se saisissent aussi au clavier dans la colonne droite
- [ ] CA3 : « Enregistrer » écrit en un seul appel la géométrie de toutes les parcelles modifiées et l'orientation du potager (US-326) ; un échec n'écrit rien et le dit
- [ ] CA4 : Le contrôle de cohérence de surface propose d'aligner la fiche ; il n'aligne jamais seul
- [ ] CA5 : La rose des vents fixe l'orientation du nord, reprise par le plan en lecture (US-327)
- [ ] CA6 : Le calcul de l'aimantation, des rotations et des cotes vit dans une lib sans React, couverte par `npm test`
- [ ] CA7 : Réservé à un membre éditeur ; absent sous 720 px de conteneur
- [ ] CA8 : Le guide utilisateur décrit la mise en place du plan ; corpus à jour
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence en desktop et 1024 px (tablette) ; vérification chrome-devtools

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : paramétrage (PWA ordinateur)
- Migration BDD requise : non au-delà d'US-326
- Dépendances : **US-326** (géométrie), **US-327** (plan) ; US-332 pour la création d'une forme nouvelle
- Point de vigilance : c'est le seul écran d'édition graphique de l'application ; prévoir l'annulation de la dernière action (Ctrl+Z) dès cette US si le coût est faible, sinon la noter en suite
- Modèle / effort conseillé : **Opus 5.5, `high`** — interactions directes (glisser, poignées, rotation), état d'édition transactionnel

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Poser la planche haricots
  Given la planche haricots est dans "À placer"
  When je la glisse sur le plan
  Then elle s'aligne sur l'angle du potager et s'aimante à 50 cm
  When j'enregistre
  Then elle est dessinée à cet endroit sur le plan en lecture

Scénario: Corriger la surface de la fiche
  Given la planche centrale est posée en 12 × 5 m et sa fiche indique 69 m²
  When je la sélectionne
  Then l'éditeur affiche "Surface posée 60 m², fiche parcelle 69 m²"
  And propose "Mettre la fiche à 60 m²"

Scénario: Pas d'édition sur mobile
  Given je suis sur le Plan, sur mon téléphone
  Then aucune entrée "Modifier le plan" n'est proposée
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `editeur`
