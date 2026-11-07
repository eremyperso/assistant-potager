**ID :** US-289
**Titre :** Confirmer une commande dans la PWA, sans passer par Telegram
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier qui parle à Gaston dans la PWA
Je veux confirmer au bouton (ou d'un « vas-y ») une commande comprise — créer ou modifier une parcelle, corriger un geste — dans le panneau lui-même
Afin de ne pas devoir ouvrir Telegram pour une action que le compagnon a déjà comprise

**Contexte fonctionnel :**
D3 du cadrage ne levait l'arbitrage A16 que pour les **gestes**. Une commande dite dans la PWA est comprise par le même orchestrateur, rangée en base, mais sa carte sortait `confirmable=False` (« se confirme dans Telegram ») parce qu'une commande s'exécute par son **handler Telegram**. Seules `/parcelle ajouter|modifier` (US-237) et les corrections (US-262) ont un exécuteur de service sans `Update` : ce sont elles qui sont ouvertes ici (lot 1). Les autres formes gardent leur handler et se confirment dans Telegram, la carte le dit.

**Critères d'acceptance :**
- [x] CA1 : La carte d'une commande ou d'un plan dont toutes les formes ont un exécuteur de service est `confirmable` ; les autres restent à Telegram, avec leur motif.
- [x] CA2 : Confirmer dans la PWA sort la proposition de l'attente de façon atomique (règles d'US-259), journalise, puis exécute par `agent/executeurs` ou `corrections.executer` — jamais par un handler du bot. La seconde confirmation (PWA ou Telegram) n'écrit rien.
- [x] CA3 : Un refus du service (lecture seule, valeur invalide, parcelle disparue) est dit avec sa raison, la carte passe en « ⚠️ Non exécuté », rien n'est écrit.
- [x] CA4 : Un plan s'exécute étape par étape (arrêt à la première en échec), avec le compte rendu ✅ ❌ ⏭ d'US-237.
- [x] CA5 : « Vas-y » confirme une commande à exécuteur, hors action destructrice (bouton seul, US-260 / CA3) ; la carte déjà affichée change d'état, elle n'est pas dupliquée.
- [x] CA6 : Les écrans se relisent après une commande exécutée (comme après un geste).
- [ ] CA7 *(lot suivant)* : Les autres formes qui écrivent (`/parcelle renommer|supprimer`, `association saisir`, `carnet retenir`, `rappel programmer`, `culture *`, `calendrier zone|fenetre|delai`) reçoivent un exécuteur de service appelé aussi par leur handler (test de parité, comme CA8 d'US-237). Inventaire dans `menu_commandes.FORMES_DICTABLES` (`confirmation=True`).
- [ ] CA8 *(lot suivant)* : Une commande destructrice (`/parcelle supprimer`) se confirme au bouton dans la PWA.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction compagnon (PWA), commandes
- Migration BDD requise : non
- Dépendances : US-237, US-262, US-270, US-271
- Fichiers : `app/services/compagnon/echange_pwa.py` (`s_execute_dans_la_pwa`, `_confirmer_commande`, `_jouer_commande`, `_decider`), `frontend/src/lib/compagnon.js`
- Fiche du corpus : `data/connaissance/doc_app/compagnon-reponses-et-memoire.md` (US-099 / CA9)

**Estimation :** 5 points (lot 1 livré ; lot suivant à estimer après inventaire)

**Scénario Gherkin :**
```gherkin
Given le jardinier dit "passe la sud à 2 rangs" dans le panneau de la PWA
Then une carte de commande apparaît, avec [Confirmer]
When il appuie sur [Confirmer]
Then la parcelle Sud passe à 2 rangs, sans Telegram, et la carte affiche "✅ Confirmé"
When il clique ensuite [Confirmer] dans Telegram
Then il lit "Déjà confirmé dans l'application" et rien n'est écrit deux fois
```

**Labels GitHub :** `us`, `compagnon`, `pwa`, `commandes`
