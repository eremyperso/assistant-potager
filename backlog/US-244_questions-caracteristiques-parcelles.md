**ID :** US-244
**Titre :** Répondre aux questions sur mes parcelles et leurs caractéristiques
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux demander combien j'ai de parcelles, lesquelles sont des pépinières, et quelles sont les caractéristiques d'une parcelle (sol, rangs, longueur, exposition, ensoleillement, paillage, abri)
Afin d'obtenir la valeur enregistrée, exacte et immédiate, au lieu d'une liste de cultures sans rapport ou d'une réponse inventée

**Contexte fonctionnel :**
Mesure du 21/10/2026 (US-243) : « quel est le type de sol de la parcelle NORD ? », « combien de rangs a la parcelle NORD ? » et « quelle est l'exposition de la parcelle NORD ? » sont aujourd'hui servies par la famille « occupation de la parcelle » : le jardinier reçoit la liste des cultures en place. C'est le seul cas mesuré où la réponse est **fausse**, et non simplement absente.
« quelles sont mes pépinières ? » et « quelles parcelles sont paillées ? » ne trouvent aucun gabarit.
La liste et le nombre de parcelles (« combien de parcelle ? ») ont été couverts par un correctif le 21/10/2026, à rattacher à cette US.

**Critères d'acceptance :**
- [ ] CA1 : « combien de parcelles ? », « affiche mes parcelles », « quelles sont mes parcelles ? » donnent le nombre et la liste des parcelles actives du potager, les pépinières signalées comme telles. *(livré le 21/10/2026)*
- [ ] CA2 : « quelles sont mes pépinières ? » liste les seules parcelles pépinières, avec leur type (chaude / froide) quand il est renseigné.
- [ ] CA3 : Une question sur une caractéristique d'une parcelle nommée (type de sol, nombre de rangs, longueur, exposition, ensoleillement, paillage, abri, pépinière oui/non) rend la valeur enregistrée de cette caractéristique, et uniquement celle-là.
- [ ] CA4 : Une caractéristique non renseignée est dite comme telle (« le type de sol de NORD n'est pas renseigné »), avec la commande pour la renseigner. Ce n'est jamais une valeur par défaut ni une estimation.
- [ ] CA5 : « quelles parcelles sont paillées / sous abri / à l'ombre ? » liste les parcelles qui portent cette caractéristique.
- [ ] CA6 : Ces questions ne sont plus servies par l'occupation de la parcelle ; « qu'y a-t-il sur la parcelle NORD ? » continue, elle, de lister les cultures.
- [ ] CA7 : Une question de savoir citant une parcelle (« comment amender le sol de la parcelle NORD ? ») n'est pas servie par ces gabarits.
- [ ] CA8 : Réponse sans appel modèle, limitée au potager actif.
- [ ] CA9 : Les questions de ces familles sont ajoutées au corpus d'US-243 et y sont bien servies.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-243 ; US-230 (caractéristiques de parcelle modifiables), US-239 (ensoleillement)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "NORD" de type de sol "Argileux" avec 6 rangs et des cultures en place
When le jardinier demande "quel est le type de sol de la parcelle NORD ?"
Then le bot répond que le sol de NORD est argileux
And il ne liste pas les cultures en place

Given la parcelle "SUD" sans type de sol renseigné
When le jardinier demande "quel sol a la parcelle SUD"
Then le bot répond que le type de sol de SUD n'est pas renseigné
And il indique la commande pour le renseigner
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `parcelles`
