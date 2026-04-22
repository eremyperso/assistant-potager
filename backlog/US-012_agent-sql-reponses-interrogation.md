**ID :** US-012
**Titre :** Répondre aux questions analytiques via un agent SQL sans appel Groq

**Story :**
En tant que jardinier
Je veux obtenir une réponse précise à mes questions sur mon historique (ex: "Combien de tomates récolté ?")
Afin d'avoir une information fiable, sans risque d'hallucination et sans consommer inutilement mon quota Groq

**Critères d'acceptance :**
- [ ] CA1 : "Combien de tomates ai-je récolté ?" retourne le total réel depuis la base de données
- [ ] CA2 : "Historique des arrosages courgettes" liste les 5 derniers événements correspondants
- [ ] CA3 : Aucun appel à `repondre_question()` (Groq) n'est effectué pour formuler la réponse
- [ ] CA4 : L'extraction d'intent (`extract_intent_query()`) consomme ≤ 100 tokens Groq
- [ ] CA5 : Si l'intent est non reconnu, le bot répond "Je n'ai pas compris, reformulez" sans erreur
- [ ] CA6 : La réponse est transmise par synthèse vocale (TTS) si activée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation — mode interrogation
- Fichier à créer : `llm/sql_agent.py` — classe `QueryAgent` + fonction `query_agent_answer()`
- Fichier à modifier : `llm/groq_client.py` ~ligne 44 — ajouter `extract_intent_query()`
- Fichier à modifier : `bot.py` ~ligne 1283 — refactorer `_ask_question()` pour n'utiliser que le SQL agent
- Migration BDD requise : non
- Dépendances : #010, #011
- Économie estimée : -4 900 tokens/question (de ~5 000 à ~100)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le bot reçoit la question "Combien de tomates ai-je récolté ?"
When _ask_question() est appelée
Then extract_intent_query() retourne {"action": "recolte", "culture": "tomate", "date_from": null}
And query_agent_answer() exécute une requête SQL SUM sur evenements
And la réponse affichée est "Total tomates recolte : X kg (N entrées)"
And aucun appel à repondre_question() (Groq) n'est effectué

Given le SQL agent reçoit un intent {"action": null, "culture": null, "date_from": null}
When query_agent_answer() est appelée
Then la réponse est "Je n'ai pas compris la question. Formulez autrement."
```

**Labels GitHub :** `us`, `sprint-2`, `sql-agent`, `hallucination-fix`, `tokens-groq`
