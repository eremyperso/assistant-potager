**ID :** US-263
**Titre :** Répondre en croisant les données du potager, la météo et la connaissance
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux poser une question qui mélange mon potager, la météo et le savoir agronomique
Afin d'avoir une réponse qui tient compte de ma situation, avec ses sources

**Contexte fonctionnel :**
Lot 3 du cadrage, étape 3 du §12.11. Exemple : « les limaces ont bouffé mes salades » → pluie des 3 derniers jours + fiche agronomique + parcelle concernée.

**Critères d'acceptance :**
- [ ] CA1 : Les outils de lecture `consulter_donnees`, `chercher_connaissance` et `meteo` sont au catalogue, en lecture seule.
- [ ] CA2 : Les chiffres cités dans la réponse sont ceux lus par les outils (contrôle sur le corpus de mesure).
- [ ] CA3 : Quand le corpus de connaissance est utilisé, la source est citée.
- [ ] CA4 : Les règles de prudence de `_PROMPT_FIXE_RAISONNEMENT` sont reprises : aucune dose, aucun produit de traitement.
- [ ] CA5 : Une question ne déclenche aucune écriture ; le compagnon peut seulement **proposer** de noter (« tu veux que je note les dégâts ? »).
- [ ] CA6 : Le code précharge en partie variable les cultures en place et la météo du jour (allègement du §4.5).
- [ ] CA7 : Mesure du lot 3 : chiffres cités = chiffres lus ; 0 dose ni produit.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-257
- Production conseillée : **Sonnet 5.5, effort `medium`** — branche des lectures qui existent déjà (cascade, RAG, Open-Meteo) sur le catalogue.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given 24 mm de pluie relevés sur les 3 derniers jours
And des laitues en place sur la planche Sud
When le jardinier écrit "les limaces ont bouffé toutes mes salades"
Then la réponse cite les 24 mm de pluie et une parade sans produit, avec sa source
And propose de noter les dégâts sans les enregistrer
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `rag`, `meteo`
