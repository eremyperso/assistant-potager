**ID :** US-261
**Titre :** Retenir les actions menées pour pouvoir les désigner
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon sache ce qu'il vient d'enregistrer pour moi, quel que soit le canal
Afin de pouvoir parler de « mon dernier semis » ou « ce que je viens de noter » sans le décrire

**Contexte fonctionnel :**
Lot 2 du cadrage, §16 de l'étude d'articulation (cas C8 à C10). La mémoire des actions est écrite par le **chemin d'exécution**, jamais par le modèle.

**Critères d'acceptance :**
- [ ] CA1 : Chaque écriture exécutée (exécuteurs de commande et enregistrement des gestes) crée une entrée : nature, référence en base, résumé, valeurs avant / après, canal, statut.
- [ ] CA2 : Le modèle ne peut pas créer d'entrée : aucun outil ne l'écrit (test sur le catalogue).
- [ ] CA3 : Les 5 dernières actions des 24 h sont fournies en partie variable sous les références `A1`…`A5`, balisées comme données.
- [ ] CA4 : L'outil de lecture `lire(quoi="actions")` donne les actions au-delà des 5 premières.
- [ ] CA5 : Une action faite dans un canal est désignable depuis l'autre (C9, test).
- [ ] CA6 : Les actions d'un potager ne sont jamais visibles depuis un autre (RLS, test).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement
- Migration BDD requise : oui (table des actions menées, `potager_id` + RLS)
- Dépendances : US-259
- Production conseillée : **Sonnet 5.5, effort `medium`** — écriture d'une trace à des points d'exécution connus ; peu de décisions de conception.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier vient de confirmer un semis de radis puis un arrosage
When il écrit une nouvelle phrase au compagnon
Then le contexte de l'agent contient A1 "arrosage" et A2 "semis radis"
And aucune action n'a été écrite par le modèle
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `memoire`
