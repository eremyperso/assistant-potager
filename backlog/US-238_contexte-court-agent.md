**ID :** US-238
**Titre :** Corriger ou prolonger la dernière demande sans la redire
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux répondre « non, l'autre » ou « et la planche sud aussi » juste après une proposition du bot
Afin de corriger ou d'étendre ma demande comme dans une conversation, sans répéter toute la phrase

**Contexte fonctionnel :**
Phase 5 de l'architecture. **US optionnelle** : à engager seulement si le journal de production d'US-235 à US-237 montre des reformulations fréquentes juste après une proposition.

La complétion d'un argument manquant (« quelle variété ? » → « cœur de bœuf ») existe déjà (CA13 d'US-172) et n'est pas concernée. Cette US traite la **correction** et l'**extension** d'une proposition.

**Critères d'acceptance :**
- [ ] CA1 : La proposition en attente et les deux ou trois derniers échanges sont transmis à l'agent sous forme résumée et structurée, jamais l'historique complet
- [ ] CA2 : « Non, l'autre » après un choix entre parcelles voisines propose l'autre candidate ; s'il y en a plusieurs, le bot demande laquelle
- [ ] CA3 : « Et la planche sud aussi » après une proposition de modification donne un plan à deux étapes (US-237), soumis à une nouvelle confirmation
- [ ] CA4 : La nouvelle proposition remplace l'ancienne ; l'ancienne est journalisée `abandonnee` et ses boutons ne valident plus rien (US-234)
- [ ] CA5 : Hors du délai d'une proposition en attente, une phrase est traitée comme une demande nouvelle
- [ ] CA6 : Le contexte reste propre à un jardinier et à un potager ; il n'est jamais partagé entre deux membres

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-237
- Corpus : `data/connaissance/doc_app/compagnon-telegram.md`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le bot me propose de passer "Planche nord" à 6 rangs
When je réponds "et la planche sud aussi"
Then le bot propose un plan de 2 étapes : "Planche nord" et "Planche sud" à 6 rangs
And un seul bouton "Tout confirmer"
```

**Labels GitHub :** `us`, `agent-interpreteur`, `bot`, `llm`
