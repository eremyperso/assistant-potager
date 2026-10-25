**ID :** US-247
**Titre :** Restituer ce que j'ai fait sur une période
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux demander « qu'est-ce que j'ai fait hier ? » ou « qu'ai-je fait cette semaine ? »
Afin de retrouver le fil de mon travail au potager sans parcourir tout l'historique

**Contexte fonctionnel :**
Mesure du 21/10/2026 (US-243) : « qu'ai-je fait hier ? » et « qu'est-ce que j'ai fait cette semaine ? » ne trouvent aucun gabarit et partent au modèle, qui ne voit pas le journal en entier et résume au hasard.

**Critères d'acceptance :**
- [ ] CA1 : « qu'est-ce que j'ai fait <période> » liste les gestes enregistrés sur la période (« aujourd'hui », « hier », « cette semaine », « la semaine dernière », « ce mois-ci », une date), regroupés par jour.
- [ ] CA2 : Chaque ligne donne le geste, la culture, la quantité et la parcelle quand elles sont saisies.
- [ ] CA3 : Au-delà d'un plafond de lignes, la réponse résume par type de geste (« 12 arrosages, 3 récoltes… ») et renvoie vers l'historique du web.
- [ ] CA4 : Sans période citée (« qu'est-ce que j'ai fait ? »), la période par défaut est les 7 derniers jours, et la réponse le dit.
- [ ] CA5 : Une période sans geste est une réponse (« rien d'enregistré hier »), pas une remontée vers le modèle.
- [ ] CA6 : Une question de rappel de note (« qu'avais-je noté… ») reste servie par les notes du jardinier (pas de régression).
- [ ] CA7 : Réponse sans appel modèle, limitée au potager actif ; questions ajoutées au corpus d'US-243.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-243

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given hier un arrosage des tomates et une récolte de 2 kg de courgettes sur la parcelle SUD
When le jardinier demande "qu'est-ce que j'ai fait hier"
Then le bot liste l'arrosage des tomates et la récolte de 2 kg de courgettes sur SUD

Given aucun geste enregistré hier
When le jardinier demande "qu'ai-je fait hier ?"
Then le bot répond que rien n'est enregistré hier
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `journal`
