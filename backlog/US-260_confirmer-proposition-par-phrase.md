**ID :** US-260
**Titre :** Confirmer, corriger ou abandonner une proposition par une phrase
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux répondre « vas-y », « non 4 rangs » ou « laisse tomber » à une proposition
Afin de ne pas être obligé de chercher le bouton, surtout à la voix

**Contexte fonctionnel :**
Lot 2 du cadrage, arbitrage B3 de l'architecture. La confirmation par phrase passe **uniquement** par un outil validé contre l'identifiant de la proposition en cours.

**Critères d'acceptance :**
- [ ] CA1 : Les outils `confirmer_proposition(id)` et `abandonner_proposition(id)` existent ; le validateur refuse un identifiant qui n'est pas celui de la proposition en attente.
- [ ] CA2 : « non 4 rangs » crée une nouvelle proposition ; l'ancienne passe à `remplacee` (F3).
- [ ] CA3 : Une commande **destructrice** (suppression, archivage) ne se confirme **qu'au bouton** ; une phrase reçoit une invitation à cliquer.
- [ ] CA4 : Une phrase ambiguë (« ok » sans proposition en attente, ou deux propositions candidates) n'exécute rien et le compagnon demande laquelle.
- [ ] CA5 : Une confirmation par phrase d'une proposition déjà traitée répond où et quand elle l'a été, sans seconde exécution.
- [ ] CA6 : Mesure du lot 2 : 0 confirmation par une phrase pour une destruction ; 0 second geste créé sur une phrase de correction.
- [ ] CA7 : La fiche de `data/connaissance/doc_app/` sur la confirmation est mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-259
- Production conseillée : **Sonnet 5.5, effort `high`** — logique courte mais garde-fou de sécurité (CA3) ; l'effort élevé sert à couvrir les cas négatifs.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given une proposition en attente "semis radis planche Sud 2 rangs"
When le jardinier écrit "non 4 rangs"
Then une nouvelle proposition "4 rangs" est présentée et l'ancienne est remplacée

Given une proposition en attente "supprimer la planche Nord"
When le jardinier écrit "vas-y"
Then rien n'est supprimé
And le compagnon l'invite à confirmer avec le bouton
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `confirmation`
