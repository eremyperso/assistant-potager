**ID :** US-266
**Titre :** Détecter ce qui mérite un message : le veilleur
**Épic :** ÉPIC 14 — Compagnon actif : profil, mémoire et initiative *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que l'application repère seule le gel sur mes cultures, un lot à repiquer ou une levée non notée
Afin que le compagnon puisse me prévenir au bon moment

**Contexte fonctionnel :**
Lot 5 du cadrage (§4.3, règle R7). Le veilleur **détecte sans modèle**. Cette US ne fait **aucun envoi** : les signaux sont en base et visibles dans les journaux.

**Critères d'acceptance :**
- [ ] CA1 : Chaque détecteur est une fonction pure (état du potager → signaux `theme, cle_unique, priorite, expire_le, donnees`).
- [ ] CA2 : Détecteurs livrés : gel ou canicule × cultures en place ; fortes pluies ou sécheresse sans arrosage noté ; échéance d'un lot de pépinière ; récolte imminente ; levée non notée ; fenêtre de semis qui s'ouvre ; bilan de la semaine (dimanche 18 h).
- [ ] CA3 : `cle_unique` empêche deux signaux pour un même fait (« gel:2026-10-28:parcelle-12 »).
- [ ] CA4 : `_alerte_recolte` est déplacée de `commandes_plan` vers un service, sans changement de comportement du bot.
- [ ] CA5 : La planification utilise la `job_queue` du bot (horaire, et quotidien pour le bilan) et boucle **potager par potager** sous `tenant_scope`.
- [ ] CA6 : Test d'AST : aucun module `app/services/compagnon/veilleur*.py` n'importe `llm` (R7).
- [ ] CA7 : Les relances de la file d'US-224 sont rattachées au veilleur comme thème « suivis », sans changement de comportement.
- [ ] CA8 : Les seuils de chaque détecteur viennent du référentiel (sensibilité au froid, `DureeCulturale`, `FenetreCulturale`), jamais d'un modèle ; chaque détecteur a ses tests unitaires.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse
- Migration BDD requise : oui (table des signaux et rappels, `potager_id` + RLS, purge à 30 jours)
- Dépendances : US-261
- Production conseillée : **Opus 5.5, effort `high`** — boucle multi-potager sous `tenant_scope` (risque de fuite entre potagers) et nombreux détecteurs ; les tests de chaque détecteur sont délégables à Sonnet 5.5.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given une prévision de -2 °C à 5 h demain
And 6 pieds de laitue en place sur la planche Est
When le veilleur passe
Then un signal "météo" de clé "gel:<date>:<parcelle>" est créé
And un second passage ne crée pas de doublon
And aucun message n'est envoyé
```

**Labels GitHub :** `us`, `compagnon`, `veilleur`, `proactivite`
