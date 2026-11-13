**ID :** US-325
**Titre :** Placer « Noter » au centre de la barre basse mobile
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier sur mon téléphone
Je veux un bouton « Noter » toujours au centre de la barre basse
Afin de pouvoir enregistrer ce que je vois depuis n'importe quel écran, d'un pouce

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Barre d'onglets : actuelle et proposée ». « Noter » n'est pas une section : c'est une **action**, toujours active.

| | Accueil | Plan | **centre** | 4ᵉ | Plus |
|---|---|---|---|---|---|
| Actuelle | Accueil | Plan | Cultures | Pépinière | Plus |
| Proposée | Accueil | Plan | **Noter** | Pépinière | Plus (Cultures, Stocks, Journal) |

**Règles :**
- La sélection courante (culture ou parcelle) s'affiche en **pastille** sur le bouton (emoji de la culture, épingle de parcelle, micro sinon) et devient le contexte de Gaston (US-323)
- Sur une parcelle pépinière, « Noter » renvoie vers « Ma pépinière » : « Les lots de la pépinière se notent dans Ma pépinière »
- Pour garder cinq places, **Cultures passe sous « Plus »** avec Stocks et Journal — variante : garder Cultures et passer Pépinière sous « Plus » (arbitrage **P1**)

**Critères d'acceptance :**
- [ ] CA1 : La barre basse mobile porte Accueil, Plan, Noter, Pépinière (ou Cultures selon P1), Plus ; « Plus » ouvre les sections restantes
- [ ] CA2 : « Noter » est mis en avant visuellement et n'est jamais l'onglet « courant » ; il ouvre Gaston (US-324)
- [ ] CA3 : La pastille suit la sélection courante de l'écran Plan ; sans sélection, Gaston s'ouvre sur « Tout le potager »
- [ ] CA4 : La navigation de bureau est inchangée
- [ ] CA5 : Cibles de 44 px, `aria-label` « Noter, avec Gaston », focus visible ; la déclaration des sections reste dans `frontend/src/navigation.js`, couverte par `npm test`
- [ ] CA6 : Le guide utilisateur et la fiche d'aide de navigation décrivent la nouvelle barre ; corpus à jour
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (PWA, navigation)
- Migration BDD requise : non
- Dépendances : **US-324** (Noter) ; arbitrage **P1** à trancher avant de démarrer
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Noter depuis le plan avec une culture choisie
  Given je suis sur le Plan, sur mobile, la fève sélectionnée
  When je regarde la barre basse
  Then le bouton central "Noter" porte la pastille 🫘
  When je le touche
  Then Gaston s'ouvre à propos de la fève

Scénario: Cultures sous Plus
  Given l'arbitrage P1 retient "Cultures sous Plus"
  When je touche "Plus"
  Then je vois Cultures, Stocks et Journal
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `navigation`
