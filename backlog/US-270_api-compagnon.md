**ID :** US-270
**Titre :** Ouvrir le compagnon à l'API
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon de la PWA comprenne et réponde exactement comme celui de Telegram
Afin de ne pas avoir deux assistants qui se contredisent

**Contexte fonctionnel :**
Lot 6 du cadrage (§4.1, §4.6) ; étapes E0 et E1 et règles R3, R5 de l'étude d'articulation. L'orchestrateur `app/services/compagnon/` reçoit la phrase quel que soit le canal.

**Critères d'acceptance :**
- [ ] CA1 : `POST /compagnon/messages` transmet une phrase à l'orchestrateur et renvoie la réponse et les propositions éventuelles.
- [ ] CA2 : `POST /compagnon/propositions/{id}/confirmer` (et abandonner) consomme la proposition de façon atomique (règles d'US-259).
- [ ] CA3 : Un point d'API donne l'historique des échanges récents et des cartes en cours.
- [ ] CA4 : La distribution du bot (phrase → traitement) est extraite dans l'orchestrateur ; le bot l'appelle sans changement visible (E1).
- [ ] CA5 : `/ask` passe par la cascade commune (E0).
- [ ] CA6 : Test de parité : un corpus commun donne le même résultat par l'API et par le bot (R3, R5).
- [ ] CA7 : Le potager du compte connecté est appliqué (RLS) ; aucune donnée d'un autre potager n'est renvoyée.
- [ ] CA8 : Aucune logique métier dans les routes FastAPI.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation, enregistrement (API)
- Migration BDD requise : non
- Dépendances : US-269, US-259
- Production conseillée : **Sonnet 5.5, effort `high`** — routes simples, mais l'extraction de la distribution du bot et le test de parité demandent de la rigueur.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un jardinier authentifié sur la PWA
When il envoie "j'ai semé des radis sur la planche sud 2 rangs" à POST /compagnon/messages
Then la réponse contient une proposition identique à celle que le bot aurait faite
```

**Labels GitHub :** `us`, `compagnon`, `api`
