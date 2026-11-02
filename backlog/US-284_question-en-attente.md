**ID :** US-284
**Titre :** Garder en attente la question que pose le compagnon
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux répondre d'un mot à la question du compagnon (« la planche test », « oui »)
Afin qu'il fasse ce que je lui avais demandé, sans me faire tout répéter

**Contexte fonctionnel :**
Mesure du 01/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md` §4), et traces du 28/10 (#14 à #16). « Supprime la planche » → « Laquelle : planche test ou plant tubercule ? » → « la planche test » → le compagnon **redemande** « Tu veux supprimer la planche test ? ». Les trois modèles mesurés font de même.
Une proposition en attente est un état (US-238, US-259) : le modèle la reçoit, et le validateur ancre sur « phrase d'origine ; réponse ». Une **question** de l'agent n'est pas un état : la réponse courte arrive seule, sans verbe ni demande, et rien ne peut en faire une proposition. C'est la même famille que le « oui » sans suite du 01/11, quand la promesse était en texte.

**Critères d'acceptance :**
- [ ] CA1 — Quand l'agent termine par une question en texte alors que la phrase demandait d'agir (demande d'agir reconnue, ou écriture refusée pour un nom ou une valeur manquants, US-281), le code garde une **question en attente** dans la conversation en base (US-259) : la phrase d'origine, la question et les choix nommés. Elle dure 10 minutes.
- [ ] CA2 — La phrase suivante est lue avec elle. Le modèle reçoit « question en attente : … » en partie variable, et le validateur ancre sur « phrase d'origine ; réponse », comme pour une proposition en attente. « la planche test » après « Supprime la planche » donne la proposition de supprimer PLANCHE TEST (bouton seul, comme toute suppression).
- [ ] CA3 — « oui », « vas-y » ou « d'accord » en réponse à une question qui offrait une action donnent la proposition de cette action (une carte), jamais un salut ni une nouvelle question.
- [ ] CA4 — Une nouvelle demande ou une phrase sans rapport efface la question en attente. Une question en attente ne fait jamais écrire seule : elle prépare une proposition, que le jardinier confirme.
- [ ] CA5 — Le corpus de terrain gagne les dialogues « question → réponse courte » et « question → oui » (TER-29, TER-30, DOU-1 d'US-256). Remesure sur Small 4, avec accord et en un seul passage : tous justes.
- [ ] CA6 — Tests sans modèle : réponse courte, « oui », phrase sans rapport, expiration.
- [ ] CA7 — La fiche `data/connaissance/doc_app/compagnon-reponses-et-memoire.md` dit qu'une réponse d'un mot à une question du compagnon suffit. `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Hors périmètre :**
- Les choix en boutons sous la question : à ouvrir si la remesure montre que le texte ne suffit pas.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur (conversation)
- Migration BDD requise : à décider au développement (une colonne de conversation, ou une ligne de proposition de nature « question »)
- Dépendances : US-281 (refus pour valeur manquante) ; US-259 (conversation en base), US-260 (confirmer par une phrase)
- Code concerné : `app/services/agent/contexte_court.py`, `app/services/agent/interpreteur_agent.py`, `app/services/compagnon/conversations.py`
- Production conseillée : **Opus 5.5, effort `high`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le potager contient "planche test" et "plant tubercule"
When le jardinier écrit "Supprime la planche"
Then le compagnon demande laquelle, en nommant les deux parcelles
When le jardinier écrit "la planche test"
Then le bot propose de supprimer PLANCHE TEST, au bouton seul
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `conversation`
