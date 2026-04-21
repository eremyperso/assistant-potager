**ID :** US-011
**Titre :** Valider les actions parsées par Groq avant sauvegarde en base

**Story :**
En tant que jardinier
Je veux que le bot rejette silencieusement les résultats de parsing incohérents (hallucinations Groq)
Afin de ne jamais avoir de fausses entrées ou d'entrées vides enregistrées dans mon historique

**Critères d'acceptance :**
- [ ] CA1 : Une action dont le type n'est pas dans la whitelist canonique est rejetée (ex: "supergrossissage")
- [ ] CA2 : Une observation sans culture ET sans date est rejetée
- [ ] CA3 : Un JSON parsé dont le texte source contient 3 marqueurs de question ou plus est rejeté
- [ ] CA4 : Une quantité non numérique est rejetée
- [ ] CA5 : En cas de rejet, un message d'avertissement est loggé (niveau WARNING)
- [ ] CA6 : Les actions valides passent toujours la validation sans modification

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement — garde-fou post-parsing
- Fichier à créer : `utils/validation.py` — fonction `validate_parsed_action(parsed, texte_original)`
- Fichier à modifier : `bot.py` ~ligne 1063 (`_parse_and_save()`) pour intégrer l'appel
- Migration BDD requise : non
- Dépendances : #010 (la classification doit avoir été améliorée pour que la validation soit le dernier filet)
- La validation est en Python pur, sans appel Groq

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given Groq retourne {"action": "super_observation", "culture": "tomate"}
When validate_parsed_action() est appelée
Then la validation retourne (False, "Action inconnue ou hallucination Groq")
And aucune entrée n'est sauvegardée en base

Given Groq retourne {"action": "observation", "culture": "tomate", "date": null}
When validate_parsed_action() est appelée
Then la validation retourne (False, "Observation sans culture ou date")

Given Groq retourne {"action": "recolte", "culture": "tomate", "quantite": 2}
When validate_parsed_action() est appelée
Then la validation retourne (True, "Validation OK")
And l'entrée est sauvegardée normalement
```

**Labels GitHub :** `us`, `sprint-1`, `validation`, `hallucination-fix`
