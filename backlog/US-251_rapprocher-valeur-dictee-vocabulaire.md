**ID :** US-251
**Titre :** Rapprocher une valeur mal dite du vocabulaire connu et proposer la correction
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier qui dicte à la voix ou tape vite
Je veux que « pépinière chaud », « exposé plein sud », « sol argileuse » soient compris comme la valeur évidente qu'ils désignent
Afin de ne pas avoir à reformuler pour une faute d'accord, d'accent ou de pluriel

**Contexte fonctionnel :**
Suite d'US-250. Une partie des mots non compris sont en réalité des variantes évidentes d'une valeur connue : masculin pour féminin, accent absent, pluriel, faute de dictée. Les rejeter fait poser une question inutile ; les corriger en silence ferait écrire une valeur que le jardinier n'a pas vue. La correction est donc **proposée**, visible, et le jardinier reste libre de refuser et de reformuler.

**Critères d'acceptance :**
- [ ] CA1 : Chaque caractéristique réglable par une phrase (type de pépinière, exposition, ensoleillement, sol, abri, paillage…) dispose d'une seule liste de valeurs admises, partagée par la reconnaissance par règles et par l'agent.
- [ ] CA2 : Une valeur dite qui ne diffère d'une valeur admise que par le genre, le nombre, les accents ou la casse est rapprochée de cette valeur (« chaud » → chaude, « froid » → froide, « argileuse » → argileux).
- [ ] CA3 : Le récapitulatif montre la correction faite (« chaud → chaude ») avant la confirmation ; refuser n'écrit rien.
- [ ] CA4 : Une valeur qui pourrait se rapprocher de deux valeurs admises n'est jamais tranchée : la question d'US-250 est posée avec les deux.
- [ ] CA5 : Une valeur sans rapprochement possible (« tiède ») suit la question d'US-250, jamais une valeur devinée.
- [ ] CA6 : L'agent reçoit la même liste de valeurs admises : il ne propose jamais une valeur hors liste, et le validateur la refuse s'il le fait.
- [ ] CA7 : Aucun appel au modèle n'est nécessaire pour les rapprochements du CA2.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-250, US-235

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given une parcelle "tunnel chauffé"
When le jardinier écrit "Mon tunnel est une pépinière chaud"
Then le récapitulatif propose "tunnel chauffé : pépinière chaude (chaud → chaude)"
When le jardinier confirme
Then la parcelle est une pépinière chaude

When le jardinier écrit "ma serre est une pépinière tiède"
Then le compagnon demande "chaude" ou "froide"
```

**Labels GitHub :** `us`, `agent-interpreteur`, `commandes`, `referentiel`
