**ID :** US-245
**Titre :** Lister les cultures en place et les variétés d'une culture
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux demander « qu'est-ce que je cultive en ce moment ? » ou « quelles variétés de tomate j'ai ? »
Afin d'avoir l'inventaire de mon potager en une phrase, sans ouvrir le plan ni chaque parcelle

**Contexte fonctionnel :**
Mesure du 21/10/2026 (US-243) : « quelles cultures j'ai en place ? », « qu'est-ce que je cultive en ce moment ? », « liste mes cultures », « quelles variétés de haricot j'ai ? » et « combien de variétés de haricots ? » ne trouvent aucun gabarit. Aujourd'hui, seule une question culture par culture (pieds actifs, stock) ou parcelle par parcelle (occupation) est couverte.

**Critères d'acceptance :**
- [ ] CA1 : « quelles cultures j'ai en place ? » et ses variantes listent les cultures qui ont au moins un pied en place dans le potager actif, avec le nombre de pieds et la ou les parcelles.
- [ ] CA2 : La pépinière est présentée à part (« en pépinière : … »), pour ne pas confondre un semis en godet avec une culture en terre.
- [ ] CA3 : Une culture végétative entièrement récoltée n'apparaît plus. Une culture reproductrice récoltée mais dont les pieds sont en place apparaît toujours : la cueillette ne retire pas le pied.
- [ ] CA4 : « quelles variétés de <culture> j'ai ? » liste les variétés enregistrées pour cette culture dans le potager, avec le nombre de pieds en place par variété ; une saisie sans variété apparaît en « variété non précisée ».
- [ ] CA5 : « combien de variétés de <culture> ? » donne le nombre de variétés distinctes.
- [ ] CA6 : Aucune culture en place est une réponse (« aucune culture en place pour l'instant »), pas une remontée vers le modèle.
- [ ] CA7 : Les chiffres sont ceux de l'écran de stock du web (une seule vérité).
- [ ] CA8 : Réponse sans appel modèle, limitée au potager actif ; questions ajoutées au corpus d'US-243.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-243

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given 12 pieds de tomate "Cœur de bœuf" et 6 pieds de tomate sans variété en place
And 30 pieds de haricot récoltés trois fois, toujours en place
And des carottes entièrement récoltées
When le jardinier demande "qu'est-ce que je cultive en ce moment"
Then le bot liste la tomate (18 pieds) et le haricot (30 pieds)
And la carotte n'apparaît pas

When le jardinier demande "quelles variétés de tomate j'ai ?"
Then le bot répond "Cœur de bœuf : 12 pieds" et "variété non précisée : 6 pieds"
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `cultures`
