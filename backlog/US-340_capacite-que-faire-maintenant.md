**ID :** US-340
**Titre :** Répondre « qu'est-ce que je fais au potager ? » par la capacité que faire maintenant
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux demander au compagnon, ou à mon assistant IA, ce que je dois faire au potager et ce que je peux semer ce mois-ci
Afin d'avoir une liste de gestes concrets, la même que l'écran « Aujourd'hui au potager »

**Contexte fonctionnel :**
Lot 1, §4.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Les éléments existent séparément : échéances (`voir_echeances`), confiances par culture, écran « Aujourd'hui au potager » (US-328). Le compagnon doit recevoir un verdict déjà trié, pas trois lectures à recouper.

**Critères d'acceptance :**
- [ ] CA1 : La capacité rend, pour le potager actif et la date du jour, les gestes à faire (échéances, récoltes possibles, mises en godet, plantations), classés par urgence
- [ ] CA2 : Elle rend les cultures qu'il est temps de semer ou planter ce mois-ci, selon le climat du potager, avec la source de chaque verdict
- [ ] CA3 : La liste est calculée par le même service que l'écran « Aujourd'hui au potager » ; un test vérifie qu'ils concordent pour un même potager et une même date
- [ ] CA4 : Pour une culture reproductive en place, une récolte répétée est proposée comme une nouvelle cueillette, jamais comme la fin de la culture
- [ ] CA5 : Sur un potager neuf (rien en place), la capacité le dit et rend seulement les semis du mois
- [ ] CA6 : La capacité est visible du compagnon et du MCP ; mesurée avec accord sur les cas « que faire » et « que semer » du jeu d'évaluation

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-338, US-339 (verdict de saison par culture) ; US-328 (Aujourd'hui au potager) ; US-337 pour la mesure
- Modèle / effort conseillé : **Sonnet 5.5, `low`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le potager porte des haricots en place depuis juillet et une échéance d'arrosage aujourd'hui
When le jardinier demande "qu'est-ce que je dois faire au potager ?"
Then le compagnon cite l'arrosage du jour puis la cueillette des haricots
And la liste est la même que celle de l'écran "Aujourd'hui au potager"
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `mcp`, `calendrier`
