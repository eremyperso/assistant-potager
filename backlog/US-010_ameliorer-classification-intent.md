**ID :** US-010
**Titre :** Améliorer la classification d'intention pour distinguer questions et actions

**Story :**
En tant que jardinier
Je veux que mes questions vocales soient correctement reconnues comme des interrogations (et non comme des actions à enregistrer)
Afin de ne plus voir de fausses entrées créées en base de données quand je pose une question

**Critères d'acceptance :**
- [ ] CA1 : "Combien de tomates ai-je récolté ?" est classifié INTERROGER (jamais ACTION)
- [ ] CA2 : "Afficher les récoltes de carotte" est classifié INTERROGER
- [ ] CA3 : "Quand ai-je planté mes courgettes ?" est classifié INTERROGER
- [ ] CA4 : "J'ai récolté 2 kg de tomates" reste classifié ACTION
- [ ] CA5 : "Semé des carottes hier" reste classifié ACTION
- [ ] CA6 : Un message contenant "?" ET un mot-clé interrogatif n'est jamais classifié ACTION

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram — classification intent
- Fichier concerné : `bot.py` ~ligne 730 (`_CLASSIFY_PROMPT`) et ligne 762 (`classify_intent()`)
- Migration BDD requise : non
- Dépendances : aucune
- Le prompt doit inclure 30+ exemples de questions explicites avec contre-exemples ACTION

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le bot reçoit un message vocal transcrit "Combien de tomates ai-je récolté ?"
When classify_intent() analyse le message
Then la réponse est "INTERROGER"
And aucune entrée n'est créée dans la table evenements

Given le bot reçoit un message vocal transcrit "J'ai récolté 2 kg de tomates"
When classify_intent() analyse le message
Then la réponse est "ACTION"
And une entrée est créée dans la table evenements
```

**Labels GitHub :** `us`, `sprint-1`, `classification`, `hallucination-fix`
