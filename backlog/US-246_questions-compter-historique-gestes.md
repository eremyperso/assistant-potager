**ID :** US-246
**Titre :** Compter mes gestes et retrouver l'historique d'un type de geste
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux demander « combien de fois j'ai arrosé les tomates ce mois-ci ? » ou « quels traitements ai-je faits sur les tomates ? »
Afin de vérifier mon suivi (arrosage, traitements, pertes) à partir de mon journal, sans faire le compte moi-même

**Contexte fonctionnel :**
Mesure du 21/10/2026 (US-243) : seule la **dernière** occurrence d'un geste est couverte (« quand ai-je arrosé pour la dernière fois ? »). « combien d'arrosages ce mois-ci ? », « combien de fois j'ai arrosé les haricots ? », « quels traitements ai-je faits sur les haricots ? » et « combien de pertes de carottes ? » ne trouvent aucun gabarit. Ce sont pourtant des requêtes simples sur le journal.

**Critères d'acceptance :**
- [ ] CA1 : « combien de fois / combien de <geste> » donne le nombre d'événements de ce type, filtré par culture et par période quand elles sont citées (« ce mois-ci », « cette semaine », « en juillet », « cette année »).
- [ ] CA2 : Sans période citée, le compte porte sur la saison en cours, et la réponse le dit (« cette saison »).
- [ ] CA3 : « quels <gestes> ai-je faits sur <culture> » liste les occurrences par date décroissante, avec les détails saisis (produit de traitement, quantité, parcelle). La liste est plafonnée, avec le reste annoncé (« … et 4 autres »).
- [ ] CA4 : Pour une perte, le total de pieds perdus est donné en plus du nombre de saisies.
- [ ] CA5 : Les gestes reconnus sont ceux du référentiel d'actions du bot (arrosage, traitement, désherbage, paillage, taille, perte, observation…), y compris leurs synonymes.
- [ ] CA6 : Zéro occurrence est une réponse (« aucun arrosage de tomate enregistré ce mois-ci »), pas une remontée vers le modèle.
- [ ] CA7 : « quand ai-je arrosé pour la dernière fois ? » reste servie par la dernière occurrence (pas de régression).
- [ ] CA8 : Réponse sans appel modèle, limitée au potager actif ; questions ajoutées au corpus d'US-243.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-243

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given 4 arrosages de tomate en octobre et 2 en septembre
When le jardinier demande "combien de fois j'ai arrosé les tomates ce mois-ci"
Then le bot répond 4 arrosages de tomate en octobre

Given deux traitements au purin d'ortie sur les tomates
When le jardinier demande "quels traitements ai-je faits sur les tomates ?"
Then le bot liste les deux traitements avec leur date et le produit

Given aucun arrosage de courgette enregistré
When le jardinier demande "combien d'arrosages de courgette ?"
Then le bot répond qu'aucun arrosage de courgette n'est enregistré cette saison
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `journal`
