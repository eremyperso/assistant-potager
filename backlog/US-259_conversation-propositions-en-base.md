**ID :** US-259
**Titre :** Garder la conversation et les propositions en base, communes aux canaux
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon se souvienne de ce qu'on vient de se dire et de ce qu'il m'a proposé, même après un redémarrage et quel que soit le canal
Afin de pouvoir répondre « vas-y » ou « non, 4 rangs » sans tout redire

**Contexte fonctionnel :**
Lot 2 du cadrage (§3, §4.7), étape 4 du §12.11. Aujourd'hui, les propositions vivent en mémoire du processus (`_INTERP_PENDING`, `_sessions`, contexte court d'US-238), et la file d'US-224 (`gestes_intentions`) est un second magasin d'attente. Deux magasins seraient deux moteurs : une **seule table de propositions**, dont le geste en file est une nature parmi d'autres.

**Critères d'acceptance :**
- [ ] CA1 : Les 10 derniers échanges (texte du jardinier, texte du compagnon, outils appelés, proposition en attente, signal d'origine) sont gardés en base par jardinier et par potager, sur 30 minutes glissantes ; purge à 30 jours.
- [ ] CA2 : Les propositions sont en base avec les états `en_attente`, `confirmee`, `abandonnee`, `perimee`, `remplacee`.
- [ ] CA3 : La consommation d'une proposition est **atomique** : deux confirmations simultanées n'exécutent qu'une fois (règle d'US-234, test de concurrence).
- [ ] CA4 : La proposition porte **son** `potager_id`, et l'exécution arme ce potager, quel que soit le potager actif du canal qui confirme (F5).
- [ ] CA5 : Une proposition de conversation vit 30 min ; une proposition notifiée prend la durée de la file d'US-224 (3 jours, avec avertissement avant purge) (F4).
- [ ] CA6 : `gestes_intentions` devient une nature de proposition ; les gestes en attente sont migrés ; relances (`relances_file`), lien `?start=` et expiration sont repris **sans changement visible** pour le jardinier.
- [ ] CA7 : `_INTERP_PENDING`, `_sessions` et le contexte court d'US-238 sont retirés au profit de ces tables.
- [ ] CA8 : Une proposition en attente survit à un redémarrage du bot et reste confirmable.
- [ ] CA9 : Les tables portent `potager_id` et une politique RLS ; aucune donnée d'un autre potager n'est lue (test).
- [ ] CA10 : Les tests existants d'US-224, US-234 et US-238 restent verts, adaptés seulement là où le stockage change.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : oui (tables des échanges et des propositions, reprise de `gestes_intentions`, rollback)
- Dépendances : US-257, US-224, US-234
- Production conseillée : **Opus 5.5, effort `xhigh`** — migration de données vivantes, atomicité, RLS et fusion de deux magasins : une erreur de conception ici crée le « second moteur » que le cadrage interdit.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given une proposition "semis radis planche Sud 2 rangs" en attente
When le bot redémarre
And le jardinier clique "Confirmer"
Then le semis est enregistré une seule fois

Given un geste en attente dans la file d'US-224 avant la migration
When la migration est appliquée
Then le geste apparaît comme proposition de nature "geste" et sa relance part comme avant
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `memoire`, `migration`
