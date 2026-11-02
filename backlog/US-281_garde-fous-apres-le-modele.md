**ID :** US-281
**Titre :** Garder les garde-fous après le modèle, dans le validateur
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux qu'une question ne me propose jamais de supprimer ou de modifier quoi que ce soit, et qu'une demande incomplète me vaille une question plutôt qu'une devinette
Afin de pouvoir parler librement au compagnon sans craindre une carte que je n'ai pas demandée

**Contexte fonctionnel :**
Mesure du 01/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md` §4). En mode `prioritaire`, à « est-ce que je peux supprimer la planche sud sans perdre mon historique ? », **les trois modèles mesurés proposent une carte de suppression**. En mode `actif`, la projection d'US-276 l'empêchait en retirant les outils d'écriture **avant** l'appel, sur une liste de mots : c'est précisément le genre de tri qui piège les phrases libres.
Cette US déplace la garde **après** le modèle : il voit tout, mais le validateur refuse ce qu'une question ou une demande incomplète ne peut pas produire. S'y ajoutent les devinettes relevées : « renomme la planche sud » → renommage vers rien ; « enlève la serre » → désactivation ; quatre créations dictées dont « Est », qui existe → recréation proposée dans un plan.

**Critères d'acceptance :**
- [ ] CA1 — Question : quand la phrase est interrogative (`projection.est_interrogative`, avec l'exception des demandes polies d'agir « peux-tu renommer… ») ou est un constat de problème (US-263 / CA5), toute écriture proposée est refusée, avec la raison « c'est une question ». Le modèle répond en texte. Le jardinier ne voit aucune carte.
- [ ] CA2 — Valeur indispensable manquante : un renommage sans nouveau nom, une création sans nom ou un rappel sans objet sont refusés (« il manque le nouveau nom »). Le modèle pose la question (consigne 11). Aucune carte incomplète n'est montrée.
- [ ] CA3 — Désactivation : `actif=false` sur une parcelle n'est accepté que si la phrase le dit (« désactive », « archive », « ne sert plus », « retire-la du potager »). « enlève la serre » est refusé et devient une question.
- [ ] CA4 — Parcelle existante : une création dont le nom normalisé est celui d'une parcelle active est refusée, y compris dans un plan de plusieurs créations. La raison revient au modèle, qui le dit (« Est existe déjà »). Le correctif du 28/10 (création sur un nom exact avec caractéristiques → modification) est gardé.
- [ ] CA5 — Ces règles valent dans les modes `actif` et `prioritaire`. En `actif`, la projection d'US-276 est gardée ; en `prioritaire`, ces règles la remplacent.
- [ ] CA6 — Chaque refus revient au modèle comme verdict (§12.4) ; le jardinier ne lit jamais « refusée » ni la raison brute (consigne 9).
- [ ] CA7 — Remesure sur Small 4, avec accord et en un seul passage : sur les deux corpus, **0 suppression proposée sans demande** et **0 écriture proposée sur une question** au jardinier. Rapport commité.
- [ ] CA8 — Tests sans modèle (passerelle simulée) : chaque phrase du contexte, plus les non-régressions « supprime la planche test » (proposée, bouton seul), « est-ce que tu peux renommer la parcelle tunnel en serre chaude ? » (proposée) et « la planche nord a 5 rangs » (règles, mode `actif`).

**Hors périmètre :**
- La réponse courte à une question de l'agent (« la planche test ») : US-284.
- Le contenu des réponses aux questions : US-282, US-283, US-285.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur (validation)
- Migration BDD requise : non
- Dépendances : US-280 (mode `prioritaire`, corpus de terrain)
- Code concerné : `app/services/agent/validation.py`, `app/services/agent/interpreteur_agent.py` (`Propositions.juger`), `app/services/agent/projection.py` (réutilisé, pas dupliqué)
- Production conseillée : **Opus 5.5, effort `high`**. C'est la garde de sécurité du mode `prioritaire`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given AGENT_MODE=prioritaire
When le jardinier écrit "est-ce que je peux supprimer la planche sud sans perdre mon historique ?"
And le modèle appelle supprimer_parcelle("Planche Sud")
Then le validateur refuse l'appel
And le jardinier lit une réponse en texte, sans carte

When le jardinier écrit "renomme la planche sud"
Then le jardinier lit "En quoi veux-tu la renommer ?"
And aucune carte n'est montrée
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `securite`
