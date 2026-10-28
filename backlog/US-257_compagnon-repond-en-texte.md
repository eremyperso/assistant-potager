**ID :** US-257
**Titre :** Laisser le compagnon répondre en texte et poser ses vraies questions
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon me réponde avec des phrases rédigées, me pose une vraie question quand il doute et me dise ce qu'il ne sait pas faire
Afin de ne plus lire « Rien n'a été fait. Redis ta demande en précisant »

**Contexte fonctionnel :**
Lot 1 du cadrage (étape 2 du §12.11 de l'architecture). L'agent livré est un aiguilleur : il ne rédige jamais, et le bot affiche des textes figés. L'agent passe en boucle conversationnelle (`tool_choice="auto"`) : il peut répondre en texte, appeler un outil de lecture, ou proposer une écriture que le validateur juge. **Absorbe US-250** (aucun mot perdu, plusieurs écritures par réponse).

**Critères d'acceptance :**
- [ ] CA1 : L'agent peut répondre en texte libre, sans outil, à une phrase simple (« merci », « bonjour »).
- [ ] CA2 : Quand il doute, il pose une question rédigée qui nomme les choix (« la planche Nord ou la Sud ? ») ; les outils `poser_question`, `demander_precision` et `hors_perimetre` sont retirés au profit du texte et de `manque_catalogue`.
- [ ] CA3 : Le verdict du validateur revient au modèle, qui se corrige dans la même boucle ; le nombre de tours est borné.
- [ ] CA4 : Une phrase à plusieurs actions produit toutes les propositions ; si une partie de la phrase n'est reprise par aucun appel (chiffres ou mots d'action non repris), la boucle redonne un tour (US-250).
- [ ] CA5 : Un contrôle déterministe rejette tout texte qui annonce une action non exécutée (« c'est fait », « j'ai noté ») et le remplace par le récapitulatif du code.
- [ ] CA6 : Plus aucun texte figé de l'aiguilleur n'est affiché par le bot ; le repli vers le routeur par mots-clés est supprimé pour une phrase impérative et conservé pour `/ask`.
- [ ] CA7 : Le comportement reste réversible par `AGENT_MODE`.
- [ ] CA8 : Un rapport d'évaluation sur le vrai modèle (US-256) atteint le critère du lot 1 : couperets à 0, 2 actions sur 2 pour les phrases doubles, naturel ≥ 2,5/3 sur 30 dialogues relus.
- [ ] CA9 : Les fiches de `data/connaissance/doc_app/` décrivant les réponses du compagnon sont mises à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : US-256 ; absorbe US-250
- Production conseillée : **Opus 5.5, effort `xhigh`** — cœur du moteur : boucle, validateur et contrôle des annonces mensongères portent les couperets. Conception et validateur avec Opus ; tests répétitifs et fiches du corpus délégables à Sonnet 5.5.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given le compagnon en AGENT_MODE=actif
When le jardinier écrit "crée la planche nord 8 m avec 4 rangs et mets la serre en pépinière froide"
Then deux propositions sont présentées à confirmer
And aucun texte n'annonce une action avant la confirmation

When le jardinier écrit "supprime la planche"
Then le compagnon demande laquelle en nommant les planches existantes
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `conversation`
