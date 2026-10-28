**ID :** US-268
**Titre :** Proposer et tenir des rappels de suivi
**Épic :** ÉPIC 14 — Compagnon actif : profil, mémoire et initiative *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux qu'après un semis le compagnon me propose de me rappeler de vérifier la levée à la bonne date
Afin de suivre mes cultures sans tenir moi-même un agenda

**Contexte fonctionnel :**
Lot 5 du cadrage (§1.2, R9). Le délai vient du référentiel, jamais du modèle. Un rappel est une écriture : il est confirmé.

**Critères d'acceptance :**
- [ ] CA1 : Après une action qui s'y prête (semis → levée, repiquage → reprise…), le compte rendu propose un rappel daté, la date étant calculée depuis `DureeCulturale`.
- [ ] CA2 : L'outil `programmer_rappel` est classé en écriture : le rappel n'est créé qu'après le clic « Oui, rappelle-moi » ou une phrase confirmée.
- [ ] CA3 : Le jardinier peut demander un rappel libre (« rappelle-moi de tailler les tomates samedi ») ; la date est résolue par le code.
- [ ] CA4 : À l'échéance, le veilleur produit un signal « rappels », distribué par les règles d'US-267.
- [ ] CA5 : `/rappels` liste les rappels à venir et permet d'en annuler un.
- [ ] CA6 : Pas de proposition de rappel si le thème « rappels » est coupé.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : non si la table des signaux et rappels d'US-266 les porte ; sinon oui
- Dépendances : US-266, US-267, US-264
- Production conseillée : **Sonnet 5.5, effort `medium`** — se branche sur la proposition, le veilleur et le distributeur déjà livrés.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier vient de confirmer un semis de radis le 27 octobre
Then le compagnon propose "Je te fais signe le 3 novembre ?" [Oui, rappelle-moi] [Pas la peine]
When il clique [Oui, rappelle-moi]
Then un rappel daté du 3 novembre est créé
And le 3 novembre un message lui demande où en est la levée
```

**Labels GitHub :** `us`, `compagnon`, `rappels`, `proactivite`
