**ID :** US-274
**Titre :** Retirer les chemins d'écriture sans confirmation
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant qu'administrateur
Je veux supprimer les anciens points d'API qui écrivent sans passer par une proposition confirmée
Afin qu'il n'existe plus qu'un seul chemin d'écriture (R2)

**Contexte fonctionnel :**
Lot 7 du cadrage, étape E6 de l'étude d'articulation. Concerne `/voice` (branches ACTION et INTERROGER), `/parse` et `classify_intent_pwa`.

**Critères d'acceptance :**
- [ ] CA1 : Un inventaire vérifie qu'aucun écran de `frontend/` ni de `static/` n'appelle encore ces points d'API.
- [ ] CA2 : Les points d'API listés sont retirés, avec leurs tests ; les fonctions devenues mortes aussi.
- [ ] CA3 : Un test vérifie qu'aucune route de l'API n'écrit un événement hors exécuteurs de proposition.
- [ ] CA4 : Les fiches de `data/connaissance/doc_app/` qui citent ces chemins sont corrigées.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (API)
- Migration BDD requise : non
- Dépendances : US-271 ; `static/` ne doit plus en dépendre
- Production conseillée : **Sonnet 5.5, effort `medium`** — suppression guidée par un inventaire ; l'effort sert à ne rien oublier dans `static/`.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le panneau compagnon de la PWA est livré
When l'administrateur appelle POST /parse
Then l'API répond 404
And la suite de tests reste verte
```

**Labels GitHub :** `us`, `compagnon`, `api`, `nettoyage`
