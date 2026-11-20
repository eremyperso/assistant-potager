**ID :** US-348
**Titre :** Rédiger et ingérer les fiches agronomiques des cultures courantes manquantes
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon sache conduire les cultures que je fais le plus souvent (salade, radis, poireau, pomme de terre…)
Afin d'avoir un conseil fondé sur l'application, et non un passage sur une autre culture ou une réponse vide

**Contexte fonctionnel :**
Volet savoir (transverse), §4.6 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Les 20 fiches agronomiques actuelles couvrent 10 cultures. Peut commencer tout de suite, sans dépendance au reste de l'épic ; la carte de couverture d'US-341 sert de liste de contrôle si elle est livrée avant.

**Cultures à couvrir (au minimum) :**

| Culture | Type d'organe | Fiches |
|---|---|---|
| Salade / laitue | végétatif | conduite + problèmes |
| Mâche | végétatif | conduite + problèmes |
| Radis | végétatif | conduite + problèmes |
| Épinard | végétatif | conduite + problèmes |
| Poireau | végétatif | conduite + problèmes |
| Oignon | végétatif | conduite + problèmes |
| Betterave | végétatif | conduite + problèmes |
| Pomme de terre | végétatif | conduite + problèmes |
| Petit pois | reproducteur, semis en pleine terre | conduite + problèmes |
| Fraise | reproducteur, plants | conduite + problèmes |

**Critères d'acceptance :**
- [ ] CA1 : Chaque culture du tableau a une fiche de conduite et une fiche de problèmes, au format des fiches existantes, rattachées à leur culture
- [ ] CA2 : Chaque fiche dit le cycle de vie de la culture (semis, mise en godet, plantation, récolte) et, pour une culture reproductive, que la récolte est répétée sur le même pied
- [ ] CA3 : Aucune fiche ne donne de dose ni de produit de traitement ; les sources sont citées
- [ ] CA4 : Les fiches sont ingérées dans le corpus ; la recherche rattachée à une culture (US-341) les retrouve pour leur culture et seulement pour elle
- [ ] CA5 : La carte de couverture est mise à jour
- [ ] CA6 : Les cas « culture sans fiche » du jeu d'évaluation sont revus : ceux devenus couverts changent d'attendu, d'autres cultures non couvertes les remplacent

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (connaissance)
- Migration BDD requise : non
- Dépendances : aucune bloquante ; US-341 (rattachement à une culture), US-336 (jeu d'évaluation)
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given les fiches de conduite et de problèmes du poireau sont ingérées
When le jardinier demande "quand butter mes poireaux ?"
Then le compagnon répond à partir de la fiche poireau et cite sa source
And aucun passage d'une autre culture n'est montré
```

**Labels GitHub :** `us`, `sprint-X`, `connaissance`, `rag`, `contenu`
