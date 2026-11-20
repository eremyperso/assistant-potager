**ID :** US-341
**Titre :** Rattacher la recherche de connaissance à une culture et dire quand le savoir manque
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon ne me réponde qu'avec des passages sur la culture dont je parle, et qu'il me dise quand l'application n'a pas de fiche
Afin de ne plus recevoir un conseil sur les tomates quand je parle de salades

**Contexte fonctionnel :**
Lot 1, P6 et §4.6 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le 14/11/2026, au tour 7, le compagnon a répondu avec un passage sur les tomates : la recherche, en plein texte et sans notion de culture, laisse passer un passage hors sujet bien noté, et le code (US-283) réécrit la réponse avec le résumé du premier passage. `RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` le confirme : en configuration B, Large 3 avait bien formulé sa recherche (« quand et comment planter des salades en novembre, en climat océanique ? ») et c'est `savoir.chercher_connaissance` qui a affiché le passage tomate, deux fois. En configuration C, le même passage a été écarté et signalé par le modèle dès que le code ne réécrivait plus.

**Critères d'acceptance :**
- [ ] CA1 : La capacité reçoit la culture visée, ou la repère dans la question ; elle ne rend que des passages de cette culture ou des passages généraux
- [ ] CA2 : Un passage d'une autre culture n'est jamais rendu, quelle que soit sa note
- [ ] CA3 : Sans fiche pour la culture, la réponse le dit explicitement (« pas de fiche salade ») et rend ce que le référentiel sait de cette culture (fenêtres, durées, famille)
- [ ] CA4 : La réponse affichée est celle du modèle ; le code n'y substitue plus le résumé d'un passage, il ajoute seulement la source citée
- [ ] CA5 : Le domaine (application / jardinage) d'US-283 est conservé
- [ ] CA6 : Une carte de couverture (cultures avec ou sans fiche de conduite et de problèmes) est produite pour orienter US-348
- [ ] CA7 : Mesuré avec accord sur le jeu d'évaluation : critère « hors-sujet montré » à 0

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non (sauf si le rattachement d'un passage à une culture exige une colonne : à dire au cadrage technique)
- Dépendances : US-338 ; US-283 (connaissance application et jardinage) ; US-337 pour la mesure
- Arbitrage **A2** : le compagnon peut-il donner un conseil général hors corpus, signalé comme tel ? (proposition : oui, jamais pour une dose ni un traitement)
- Si la fiche `doc_app` du compagnon change, la réingérer
- Modèle / effort conseillé : **Sonnet 5.5, `low`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given l'application n'a aucune fiche de conduite pour la salade
And elle a une fiche bien notée sur la conduite des tomates
When le jardinier demande "comment je fais pour mes salades ?"
Then aucun passage sur la tomate ne lui est montré
And le compagnon dit qu'il n'a pas de fiche salade
And il donne ce que le référentiel sait de la salade
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `connaissance`, `rag`
