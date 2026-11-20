**ID :** US-345
**Titre :** Porter corrections, annulations, rappels et carnet dans le registre de capacités
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux pouvoir dire au compagnon à capacités « retiens que… », « rappelle-moi… », « corrige ce que tu as fait » ou « annule »
Afin de garder avec le nouveau moteur tout ce que l'agent actuel sait déjà faire

**Contexte fonctionnel :**
Lot 3, §4.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Les capacités `retenir_carnet`, `programmer_rappel`, `corriger_action` et `annuler_action` existent dans l'agent actuel (US-262, US-265, US-268) mais pas dans le registre. Elles y sont portées comme des propositions, selon les règles R1 à R5 d'US-338, et deviennent aussi disponibles pour le MCP si leur portée le permet.

**Critères d'acceptance :**
- [ ] CA1 : `retenir_carnet` propose une note de carnet ; elle s'écrit à la confirmation
- [ ] CA2 : `programmer_rappel` propose un rappel avec date et texte ; une date absente ou ambiguë est demandée, jamais inventée
- [ ] CA3 : `corriger_action` et `annuler_action` s'appuient sur les actions menées (`actions_menees`) ; seules les actions corrigeables ou annulables sont proposées ; une annulation destructrice ne se confirme qu'au bouton
- [ ] CA4 : Le registre expose ces capacités au MCP seulement si le test de parité et la portée MCP le permettent ; sinon la limite est documentée
- [ ] CA5 : Parité mesurée avec l'agent actuel sur les cas correspondants du jeu d'évaluation, avec accord sur le passage réel

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement
- Migration BDD requise : non
- Dépendances : US-344 ; US-262, US-265, US-268 ; US-337 pour la mesure
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le compagnon vient d'enregistrer un semis de 20 radis sur la planche nord
When le jardinier dit "non, c'était 12"
Then le compagnon propose de corriger la quantité du semis à 12
And la correction ne s'applique qu'après confirmation
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `enregistrement`
