**ID :** US-334
**Titre :** Mettre en place le plan d'un potager nouveau ou existant
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier qui crée son potager dans l'application, ou qui l'utilise déjà
Je veux être guidé pour passer de ma liste de parcelles à un plan posé
Afin que le nouveau plan ne m'accueille ni vide ni faux le premier jour

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Mettre en place le plan » (fond, recalage, pose, orientation) et comparatif (« Mise en place : 5 min »). Deux points d'entrée existent :
- **Potager neuf** : l'assistant « Premier potager » de la PWA (US-058) crée le potager et ses parcelles par formulaire (`POST /parcelles`), sans position ;
- **Potager existant** : toutes ses parcelles sont sans position au jour de la livraison d'US-326.

Dans les deux cas, toutes les parcelles sont « à placer ».

**Règles :**

| # | Règle |
|---|---|
| M1 | Tant qu'aucune parcelle n'est placée, le Plan s'ouvre sur le **plan par zones** (US-327 / P10) surmonté d'un encart « **Mettre en place le plan** » : ce que ça apporte, la durée (« environ 5 minutes »), le bouton qui ouvre l'éditeur (US-333) — sur mobile : « à faire sur ordinateur » |
| M2 | Tant que certaines parcelles seulement sont placées, le plan dessine les placées et l'encart devient « N parcelles à placer » |
| M3 | L'assistant « Premier potager » se termine sur une proposition de mettre en place le plan maintenant ou plus tard ; ses dimensions saisies (superficie, longueur) sont reprises par l'éditeur |
| M4 | L'éditeur, ouvert la première fois, enchaîne : emprise du potager (longueur × largeur), orientation du nord, fond (US-335, ou « Sans fond »), pose des parcelles « À placer » |
| M5 | L'encart se masque définitivement une fois toutes les parcelles placées ; il se rouvre si une parcelle est retirée du plan ou créée sans position (par Telegram) |

**Critères d'acceptance :**
- [ ] CA1 : Un potager sans parcelle placée affiche le plan par zones et l'encart M1 ; un potager sans aucune parcelle affiche l'invitation à créer sa première parcelle (comportement existant de l'assistant)
- [ ] CA2 : Placement partiel : M2 est respecté, aucun rectangle n'est inventé pour une parcelle non placée
- [ ] CA3 : La dernière étape de l'assistant « Premier potager » propose « Mettre en place le plan » ; « Plus tard » mène au Plan avec l'encart
- [ ] CA4 : La première ouverture de l'éditeur enchaîne M4 ; chaque étape peut être passée
- [ ] CA5 : Une parcelle créée par Telegram arrive dans « À placer » et rouvre l'encart (M5)
- [ ] CA6 : Le guide utilisateur et la fiche d'aide de l'onboarding décrivent la mise en place du plan ; corpus vert
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et paramétrage (PWA, onboarding)
- Migration BDD requise : non
- Dépendances : **US-326**, **US-327**, **US-333** ; US-058 (premier potager, livrée)
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Premier jour d'un potager existant
  Given mon potager a 8 parcelles, aucune placée
  When j'ouvre le Plan sur ordinateur
  Then je vois mes parcelles en tuiles, dans l'ordre du chemin
  And l'encart "Mettre en place le plan · environ 5 minutes"

Scénario: Fin de l'assistant premier potager
  Given je viens de créer mon potager et 3 parcelles dans la PWA
  When j'arrive à la dernière étape de l'assistant
  Then il me propose de mettre en place le plan maintenant ou plus tard
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `onboarding`
