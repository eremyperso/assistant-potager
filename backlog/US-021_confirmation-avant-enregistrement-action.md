**ID :** US-021  
**Titre :** Demander confirmation avant enregistrement d'une action en base

**Story :**  
En tant que jardinier  
Je veux que le bot me présente un résumé de l'action détectée et me demande de confirmer avant de l'enregistrer en base  
Afin d'éviter les enregistrements erronés qui m'obligent à corriger ou effacer après coup

**Critères d'acceptance :**
- [ ] CA1 : Après parsing d'une commande de type action (semis, plantation, mise en godet, récolte, perte, arrosage, désherbage, taille, paillage, tuteurage, fertilisation, observation), le bot affiche un résumé lisible de ce qu'il s'apprête à enregistrer
- [ ] CA2 : Le résumé est suivi de deux boutons inline : `✅ Confirmer` et `❌ Annuler`
- [ ] CA3 : L'enregistrement en base n'a lieu qu'après appui sur `✅ Confirmer`
- [ ] CA4 : Si l'utilisateur appuie sur `❌ Annuler`, aucun événement n'est créé et un message "Action annulée." est affiché
- [ ] CA5 : Si l'utilisateur ne répond pas dans un délai de 1 minute, l'action est automatiquement annulée et un message d'expiration est affiché
- [ ] CA6 : Les intents de type interrogation (INTERROGER, STATS, HISTORIQUE, PLAN) ne déclenchent PAS de confirmation — ils sont exécutés directement comme aujourd'hui
- [ ] CA7 : Le flux de confirmation est compatible avec les flux à étapes multiples existants (US-019 sélection variété, US-020 sélection lot) — la confirmation intervient en dernier, après toutes les sélections

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : non
- Dépendances : US-019, US-020 (la confirmation est l'étape finale, après les sélections de variété et de lot)
- Le résumé doit être en langage naturel, ex : "📝 Je vais enregistrer : **semis** de 20 graines de *courgette jaune* le 15 mars en parcelle Serre. C'est correct ?"
- Les données à afficher dans le résumé : type_action, culture, variété (si renseignée), quantité + unité (si applicable), date, parcelle
- L'état d'attente de confirmation peut s'appuyer sur le mécanisme `_GODET_PENDING` existant (ou un dictionnaire équivalent `_ACTION_PENDING`) avec TTL de 60 secondes

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scenario: Confirmation acceptée — action enregistrée
  Given je dis "j'ai semé 20 graines de courgette jaune en serre"
  When le bot parse la commande
  Then il affiche "📝 Je vais enregistrer : semis de 20 graines de courgette jaune le 27/04 en parcelle Serre. C'est correct ?"
  And deux boutons "✅ Confirmer" et "❌ Annuler" sont affichés
  When j'appuie sur "✅ Confirmer"
  Then l'événement est enregistré en base
  And le bot confirme "✅ Semis enregistré."

Scenario: Confirmation refusée — aucun enregistrement
  Given je dis "j'ai planté 3 tomates cerises"
  When le bot affiche le résumé avec les boutons de confirmation
  And j'appuie sur "❌ Annuler"
  Then aucun événement n'est créé en base
  And le bot répond "Action annulée."

Scenario: Expiration sans réponse
  Given le bot a affiché un résumé en attente de confirmation
  When 1 minute s'écoule sans interaction
  Then l'action en attente est supprimée
  And le bot envoie "⏱️ Confirmation expirée, action annulée."

Scenario: Interrogation — pas de confirmation
  Given je dis "combien de tomates ai-je récoltées ce mois-ci ?"
  When le bot détecte l'intent INTERROGER
  Then il répond directement sans afficher de bouton de confirmation
```

**Labels GitHub :** `us`, `sprint-9`, `ux`, `confirmation`, `enregistrement`
