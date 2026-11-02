**ID :** US-283
**Titre :** Séparer, dans la recherche de l'agent, l'application et le jardinage
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux qu'une question de jardinage reçoive un conseil de jardinage, et une question sur l'application une réponse sur l'application
Afin de ne plus recevoir un passage du guide sur le plan d'occupation quand je demande comment devenir autonome en tomates

**Contexte fonctionnel :**
Mesure du 01/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md` §4). À « pour mon objectif d'autonomie, que dois-je privilégier ? », Small 4 recopie un passage sur la répartition des cultures dans le plan, tiré du guide de l'application ; le 8B recopie un passage sur la maturité des tomates. À « est-ce que je peux semer des tomates ce week-end ? », Small 4 répond par les plants étiolés.
`chercher_connaissance` interroge un seul ensemble mêlé. `knowledge_documents.source` distingue pourtant « Guide de l'Assistant Potager », « Assistant Potager — rédaction interne » (fiches agronomiques) et « ton carnet du potager ». La base de dev contient aussi des documents « Assistant Automobile — rédaction interne » (« Règles de sécurité automobile »), qui ne devraient jamais remonter. L'outil rend le meilleur passage même quand il est hors sujet, et le modèle le recopie.

**Critères d'acceptance :**
- [ ] CA1 — `chercher_connaissance` prend `domaine` (obligatoire) : `application` (le guide, `doc_app`), `jardinage` (les fiches agronomiques) ou `carnet` (les notes du jardinier). `connaissance.rechercher` filtre sur `knowledge_documents.source`, par une liste blanche par domaine.
- [ ] CA2 — Seuil : sous `RAG_SEUIL_CONFIANCE`, l'outil rend « rien de fiable » (`TEXTE_SANS_DONNEE`) au lieu du meilleur passage. Le modèle le dit et propose ce qui s'en approche.
- [ ] CA3 — Synthèse : un texte qui reprend plus de 25 mots consécutifs d'un passage est renvoyé une fois au modèle (« reformule en deux ou trois phrases, en citant la source »), puis remplacé par le texte du code.
- [ ] CA4 — Aucune source hors du domaine du potager n'est jamais rendue. L'origine des documents « Assistant Automobile » en base de dev est identifiée (test d'ingestion ?) et ils sont retirés ; l'ingestion refuse une source hors liste.
- [ ] CA5 — Le préchargement (US-263) et la cascade des questions du mode `actif` ne changent pas.
- [ ] CA6 — Remesure sur Small 4, avec accord et en un seul passage : TER-11, TER-12, TER-13 et TER-35 sont justes sur le texte attendu (US-280 / CA6).
- [ ] CA7 — La table « ce qui rend une fiche fausse » de `data/connaissance/doc_app/README.md` est relue ; les fiches touchées sont corrigées ; `pytest tests/test_us099_corpus_fonctionnement.py` et `pytest tests/test_us140_corpus_agronomique.py` restent verts.
- [ ] CA8 — Tests sans modèle : un domaine par question, le seuil, la recopie, et une source hors liste jamais rendue.

**Hors périmètre :**
- Enrichir le corpus agronomique (US-140) : cette US trie et filtre, elle n'ajoute aucune fiche.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur (outils de savoir), RAG
- Migration BDD requise : non (le filtre lit `knowledge_documents.source`) ; un nettoyage des données de dev
- Dépendances : US-280 ; US-098 et US-140 (corpus)
- Code concerné : `app/services/agent/savoir.py` (`chercher_connaissance`), `app/services/agent/catalogue_outils.py` (schéma), `app/services/connaissance.py` (`rechercher`), `tools/` d'ingestion
- Production conseillée : **Opus 5.5, effort `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
When le jardinier écrit "pour mon objectif d'autonomie, que dois je privilégie ?"
Then l'agent appelle chercher_connaissance(domaine="jardinage")
And aucun passage du guide de l'application n'est rendu
And la réponse est une synthèse en deux ou trois phrases, avec sa source

When le jardinier écrit "comment fonctionne le carnet ?"
Then l'agent appelle chercher_connaissance(domaine="application")
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `rag`
