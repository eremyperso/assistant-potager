**ID :** US-013
**Titre :** Valider le fix hallucinations par une suite de tests automatisés

**Story :**
En tant que jardinier
Je veux m'assurer que le fix anti-hallucinations ne casse aucune fonctionnalité existante
Afin de déployer en production avec confiance et de détecter rapidement toute régression future

**Critères d'acceptance :**
- [ ] CA1 : `pytest tests/test_validation.py` passe à 100% — couvre les cas : action valide, action inconnue, observation sans date, texte-question rejeté
- [ ] CA2 : `pytest tests/` global passe à 100% sans régression sur les US précédentes (001–009)
- [ ] CA3 : Un test manuel Telegram confirme : 10 questions vocales → 0 entrée créée en base
- [ ] CA4 : Un test manuel Telegram confirme : 10 actions vocales → 10 entrées correctes en base
- [ ] CA5 : Les logs montrent "VALIDATION ÉCHOUÉE" sur les hallucinations rejetées (niveau WARNING)
- [ ] CA6 : La consommation Groq mesurée est ≤ 45 000 tokens/jour (vs ~94 000 avant le fix)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : qualité / déploiement
- Fichier à créer : `tests/test_validation.py` — tests unitaires `validate_parsed_action()`
- Migration BDD requise : non
- Dépendances : #010, #011, #012 (toutes les US du sprint doivent être complètes)
- Les tests utilisent SQLite in-memory (pas de PostgreSQL requis)

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given les US-010, US-011 et US-012 sont implémentées
When pytest tests/test_validation.py est exécuté
Then tous les cas de test passent : action valide, action inconnue, observation sans date, question rejetée

Given le bot est déployé avec le fix v2.1
When 10 questions vocales sont envoyées via Telegram
Then 0 nouvelle entrée apparaît dans la table evenements
And chaque question reçoit une réponse textuelle (via SQL agent)

Given le bot est déployé avec le fix v2.1
When 10 actions vocales sont envoyées via Telegram
Then 10 entrées correctes sont créées dans la table evenements
```

**Labels GitHub :** `us`, `sprint-2`, `tests`, `hallucination-fix`, `validation`
