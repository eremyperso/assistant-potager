**ID :** US-250
**Titre :** Ne jamais ignorer en silence une partie de la phrase dictée
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon me signale un mot de ma phrase qu'il n'a pas su utiliser, au lieu de faire comme s'il avait tout compris
Afin de ne jamais confirmer une proposition qui a perdu une partie de ce que j'ai dit

**Contexte fonctionnel :**
Relevé du 22/10/2026 : « Mon tunnel est une pépinière chaud » a été proposé, confirmé puis exécuté en « pépinière, type non renseigné ». Le mot « chaud » a été jeté sans un mot, et la proposition annonçait une confiance totale. L'agent n'a jamais été consulté : une règle avait reconnu le début de la phrase. Le défaut n'est pas propre à « chaud » : toute règle qui comporte une précision facultative en fin de phrase (type de pépinière, exposition, sol, abri…) peut perdre ce qui suit sans le dire.

**Critères d'acceptance :**
- [ ] CA1 : Quand une phrase est reconnue mais qu'il reste des mots que la reconnaissance n'a pas utilisés, la proposition n'est jamais présentée comme entièrement comprise.
- [ ] CA2 : Dans ce cas, le compagnon pose une question courte qui cite le mot non compris et les valeurs qu'il connaît (« Je connais pépinière chaude ou froide, pas "chaud" : laquelle ? »), avec un bouton par valeur et un bouton « sans précision ».
- [ ] CA3 : Le choix d'un bouton produit la proposition habituelle, avec récapitulatif et confirmation ; rien n'est écrit avant la confirmation.
- [ ] CA4 : Les mots de politesse ou de liaison sans portée (« stp », « merci », « maintenant », « s'il te plaît ») ne déclenchent jamais la question.
- [ ] CA5 : Le contrôle vaut pour toutes les commandes reconnues, pas pour une seule : un test passe chaque règle avec un mot parasite en fin de phrase et vérifie qu'aucune ne le perd en silence.
- [ ] CA6 : Le journal de l'interpréteur consigne l'issue « précision demandée » et le mot non compris, pour mesurer la fréquence du cas.
- [ ] CA7 : Les phrases réelles du relevé rejoignent le corpus de l'interpréteur ; la fiche du corpus de fonctionnement qui décrit les commandes en une phrase est mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-172, US-236

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given une parcelle "tunnel chauffé"
When le jardinier écrit "Mon tunnel est une pépinière chaud"
Then le compagnon répond qu'il connaît "chaude" ou "froide" mais pas "chaud"
And il propose les boutons "Chaude", "Froide" et "Sans précision"
And aucune modification n'est enregistrée

When le jardinier écrit "mets la serre en pépinière stp"
Then le compagnon propose directement la commande, sans question
```

**Labels GitHub :** `us`, `agent-interpreteur`, `commandes`, `fiabilite`
