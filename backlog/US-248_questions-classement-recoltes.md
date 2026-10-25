**ID :** US-248
**Titre :** Classer mes récoltes et donner le total de la saison
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux demander « quelle culture a le plus produit ? » ou « combien de kg ai-je récoltés cette année ? »
Afin de faire le bilan de ma saison et de savoir ce qui vaut la peine d'être replanté

**Contexte fonctionnel :**
Mesure du 21/10/2026 (US-243) : « quelle est ma meilleure récolte ? », « quelle culture a le plus produit ? » et « combien de kg récoltés cette année ? » ne trouvent aucun gabarit. Le rendement par culture et le rendement global existent, mais leurs formulations reconnues sont trop étroites et aucun classement n'est proposé.

**Critères d'acceptance :**
- [ ] CA1 : « quelle culture a le plus produit ? » et « quelle est ma meilleure récolte ? » rendent le classement des cultures par poids récolté sur la période (saison en cours par défaut), du plus au moins productif, plafonné aux premières lignes.
- [ ] CA2 : « combien de kg ai-je récoltés <période> ? » donne le poids total récolté toutes cultures confondues sur la période.
- [ ] CA3 : Les récoltes comptées en pièces ou en bottes ne sont jamais additionnées aux kilos : elles sont présentées à part, avec leur unité.
- [ ] CA4 : Pour une culture reproductrice, toutes les cueillettes de la saison sont cumulées ; le nombre de pieds n'entre pas dans le classement.
- [ ] CA5 : Aucune récolte sur la période est une réponse, pas une remontée vers le modèle.
- [ ] CA6 : Les totaux sont identiques à ceux des statistiques du web (une seule vérité).
- [ ] CA7 : Réponse sans appel modèle, limitée au potager actif ; questions ajoutées au corpus d'US-243.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse
- Migration BDD requise : non
- Dépendances : US-243

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given cette saison 3,7 kg de courgettes en 2 récoltes, 1,9 kg de haricots en 3 cueillettes et 12 carottes en pièces
When le jardinier demande "quelle culture a le plus produit cette année ?"
Then le bot classe la courgette (3,7 kg) avant le haricot (1,9 kg)
And il présente les 12 carottes à part, en pièces

When le jardinier demande "combien de kg ai-je récoltés cette année ?"
Then le bot répond 5,6 kg
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `statistiques`
