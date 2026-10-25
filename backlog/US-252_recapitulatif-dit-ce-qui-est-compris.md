**ID :** US-252
**Titre :** Faire dire au récapitulatif ce qui a été compris, corrigé et supposé
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux lire, avant de confirmer, la part de ma phrase que le compagnon a interprétée à ma place
Afin de confirmer en connaissance de cause et de repérer une erreur avant qu'elle soit enregistrée

**Contexte fonctionnel :**
Relevé du 22/10/2026 : « mon tunnel » a été rapproché de la parcelle « tunnel chauffé », et « chaud » a été jeté ; le récapitulatif n'en disait rien, la confirmation a été donnée sur une proposition incomplète. Le jardinier confirme vite : ce qui n'est pas écrit dans le récapitulatif n'est pas vu.

**Critères d'acceptance :**
- [ ] CA1 : Le récapitulatif distingue ce qui a été dit tel quel, ce qui a été **rapproché** (nom de parcelle, valeur corrigée par US-251) et ce qui a été **supposé** par défaut (« type non précisé »).
- [ ] CA2 : Un nom de parcelle rapproché est montré avec le mot dit (« tunnel → tunnel chauffé »).
- [ ] CA3 : Une précision absente qui laisse une caractéristique vide est nommée (« type de pépinière non précisé »), avec la façon de la donner.
- [ ] CA4 : Le récapitulatif reste court : au plus une ligne par élément rapproché ou supposé, rien quand tout a été dit tel quel.
- [ ] CA5 : La même présentation vaut pour une commande reconnue par règle et pour une proposition de l'agent, y compris un plan de plusieurs commandes.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-250, US-251, US-237

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given une parcelle "tunnel chauffé"
When le jardinier écrit "mon tunnel est une pépinière"
Then le récapitulatif affiche "tunnel → tunnel chauffé"
And il affiche "type de pépinière non précisé (chaude ou froide)"
```

**Labels GitHub :** `us`, `agent-interpreteur`, `commandes`, `ux-telegram`
