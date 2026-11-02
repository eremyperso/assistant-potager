**ID :** US-287
**Titre :** Basculer le bot en agent d'abord sur Mistral Small 4
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux parler au compagnon avec mes mots, sans tournure guidée, et qu'aucun mot-clé ne détourne ma phrase
Afin d'avoir le même niveau de service pour toutes les opérations de mon potager

**Contexte fonctionnel :**
Décision D14 du 02/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md`). L'agent d'abord devient la cible, avec Mistral Small 4 (`mistral-small-2603`) en référence : même justesse que le 8B et le 14B, p95 de 2,6 s contre 8,6 et 10,5 s, et le moins cher grâce au cache.
La bascule n'a lieu qu'une fois les corrections livrées et mesurées. Elle doit aussi traiter les raccourcis à mots-clés que `app/bot/messages.py` place **avant** l'interpréteur (annuler, godets, déplacer, note), qui prennent encore des phrases libres.

**Critères d'acceptance :**
- [ ] CA1 — Préalable : US-281 à US-286 livrées. La remesure des deux corpus sur Small 4 franchit les seuils de l'analyse (§7) : 0 suppression proposée sans demande ; 0 écriture proposée sur une question ; au moins 90 % de réponses justes aux questions sur le texte attendu ; au moins 90 % de bon outil sur les commandes ; p95 de 4 s au plus. Le rapport est commité.
- [ ] CA2 — Réglages : `GROQ_MODEL_AGENT` et `GROQ_MODEL_COMPAGNON_SIGNAL` passent à `mistral/mistral-small-2603`, et `AGENT_MODE=prioritaire` en dev. La prod suit après une semaine d'usage réel sans couperet relevé au journal.
- [ ] CA3 — Raccourcis de `app/bot/messages.py` placés avant l'interpréteur : chacun est soit couvert par un outil de l'agent (annuler → `annuler_action` ; godets → `lire(quoi="lot")` ou `afficher`), soit gardé avec sa raison écrite dans le code. « Déplacer une culture » et la note guidée reçoivent un outil, ou restent gardés avec leur raison. En mode `prioritaire`, aucun autre mot-clé ne prend une phrase libre avant l'agent. Les gardes de dialogue en cours (correction, note, profil, carnet) ne changent pas.
- [ ] CA4 — Mode dégradé vérifié : sur quota ou panne de Mistral, `_l_agent_d_abord` rend la main aux règles d'aujourd'hui, et le jardinier lit une réponse. Test.
- [ ] CA5 — Coût suivi une semaine dans `conso_tokens` ; le relevé (jetons par message, part du cache, coût par jour) entre dans le rapport.
- [ ] CA6 — Documentation : fiches `compagnon-telegram.md` et `compagnon-reponses-et-memoire.md`, guide utilisateur (les deux copies), `docs/CONFIGURATION/SETUP.md`, `.env.example`, `docs/domaines/commandes-bot.md`. `pytest tests/test_us099_corpus_fonctionnement.py` reste vert, puis le corpus est réingéré.

**Hors périmètre :**
- Retirer du code les étages du mode `actif` : ils restent le mode dégradé.
- La PWA (US-271) : elle suivra par l'orchestrateur commun.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : bot Telegram, agent interpréteur, configuration
- Migration BDD requise : non
- Dépendances : US-281, US-282, US-283, US-284, US-285, US-286
- Code concerné : `app/bot/messages.py`, `app/services/agent/catalogue_outils.py`, `.env.dev`, `.env.prod` (réglages)
- Production conseillée : **Opus 5.5, effort `high`** pour le CA3

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given AGENT_MODE=prioritaire et GROQ_MODEL_AGENT=mistral/mistral-small-2603
When le jardinier écrit "effacer mon carnet"
Then la phrase va à l'agent, et non au raccourci « annuler la dernière saisie »

Given Mistral répond 429
When le jardinier écrit "crée la parcelle Est"
Then les règles proposent "/parcelle ajouter Est"
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `configuration`
