**ID :** US-079
**Titre :** Vérifier la création automatique d'un ticket Jira depuis une US

**Story :**
En tant que Product Owner
Je veux qu'une US rédigée dans `backlog/` soit automatiquement créée comme ticket Jira en statut `To Do`
Afin de valider que le pipeline Orchestrateur → Persona PO → Suivi-US-Jira fonctionne de bout en bout avant de l'utiliser sur de vraies US

**Critères d'acceptance :**
- [ ] CA1 : Le fichier `backlog/US-079_test-creation-ticket-jira.md` est créé au format standard des US
- [ ] CA2 : Un ticket Jira est créé en statut `To Do` via `python tools/jira_tracker.py create-issue backlog/US-079_test-creation-ticket-jira.md`
- [ ] CA3 : Le ticket Jira créé reprend le titre et la story de cette US (pas de troncature, pas de champ vide)
- [ ] CA4 : Le lien/clé du ticket Jira créé (ex : `POT-XXX`) est confirmé dans le chat par l'agent Suivi-US-Jira

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : outillage / process interne (test d'intégration, pas une fonctionnalité applicative)
- Migration BDD requise : non
- Dépendances : aucune

**Estimation :** 1 point

**Scénario Gherkin :**
```gherkin
Given une US rédigée dans backlog/ au format standard avec un ID unique
When l'Orchestrateur déclenche la création du ticket Jira à partir de ce fichier markdown
Then un ticket Jira est créé en statut "To Do" dans le projet Jira configuré
And le ticket reprend fidèlement le titre et la story de l'US source
```

**Labels GitHub :** `us`, `test`, `process`
