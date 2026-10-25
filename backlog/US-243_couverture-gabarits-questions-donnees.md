**ID :** US-243
**Titre :** Mesurer la couverture des gabarits sur les questions portant sur mes données
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant qu'administrateur
Je veux un jeu de questions de référence sur les données du potager, avec le taux de questions servies par un gabarit chiffré
Afin de voir les trous de couverture avant que le jardinier ne les rencontre, et d'empêcher qu'une évolution fasse reculer ce taux

**Contexte fonctionnel :**
Relevé du 21/10/2026 : « combien de parcelle ? » et « quel est mon potager actif ? » n'ont trouvé aucun gabarit. La question est partie à la requête SQL écrite par le modèle, puis au modèle de réponse, qui a rendu « Je ne trouve rien d'enregistré » suivi d'une généralité. Environ 3 800 jetons pour une mauvaise réponse, là où un gabarit répond juste pour 0 jeton.
Une mesure sur 40 questions courantes donne **17 questions servies par un gabarit sur 40**. Pire : 3 questions sur les caractéristiques d'une parcelle reçoivent une réponse **à côté** (la liste des cultures de la parcelle).
Cette US pose l'instrument de mesure ; les US-244 à US-249 comblent les trous qu'il révèle.

**Critères d'acceptance :**
- [ ] CA1 : Un corpus de référence d'au moins 60 questions sur les données du potager existe, chacune associée à la famille de gabarit attendue, ou à « aucune » quand la question relève d'un autre étage (savoir, calendrier).
- [ ] CA2 : Le corpus couvre les formulations orales et sans ponctuation (dictée vocale), les fautes courantes (« combien de parcelle »), et des questions pièges qui ne doivent PAS être servies par un gabarit (questions de savoir citant une parcelle ou une culture).
- [ ] CA3 : Un test automatique rejoue le corpus et calcule trois taux : bien servies, non servies, **mal servies** (famille différente de l'attendue).
- [ ] CA4 : Le test échoue si une question attendue sur une famille est servie par une autre famille (mal servie), quel que soit le taux global.
- [ ] CA5 : Le test échoue si le taux de questions bien servies descend sous un seuil fixé, relevé à chaque US qui ajoute une famille.
- [ ] CA6 : Le rejeu ne fait aucun appel modèle et tourne sans base PostgreSQL.
- [ ] CA7 : Le résultat (taux et liste des questions non servies) est lisible en une commande, pour orienter les prochaines familles.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse
- Migration BDD requise : non
- Dépendances : aucune — à livrer en premier, les US-244 à US-249 y ajoutent leurs questions

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given le corpus de référence des questions sur les données
When le rejeu de couverture est lancé
Then il affiche le taux de questions bien servies, non servies et mal servies
And il échoue si une question est servie par une autre famille que celle attendue
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `tests`
