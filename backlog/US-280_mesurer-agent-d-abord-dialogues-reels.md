**ID :** US-280
**Titre :** Mesurer l'agent d'abord sur des dialogues réels
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que porteur du produit
Je veux comparer, sur les phrases que j'ai réellement dites au compagnon, la cascade actuelle et une cascade où l'agent passe en premier
Afin de choisir l'architecture et le modèle sur des faits, et non sur une impression d'usage

**Contexte fonctionnel :**
Le 01/11/2026, après « vide le geste » → « oui » → « Salut Emmanuel ! », le jardinier a constaté qu'il devait employer des tournures guidées : d'autres mots le renvoyaient vers la documentation. La lecture des traces (`echanges_conversation`, `routage_logs`, potager 33, du 28/10 au 01/11) a montré que le code décidait avant le modèle, sur des listes de mots.
Cette US est **réalisée le 01/11/2026** (code non commité). L'analyse est dans `docs/EPIC - COMPAGNON CONVERSATIONNEL/ANALYSE_MESURE_AGENT_D_ABORD.md`. Il reste le CA6 : sans texte attendu, la mesure accepte une réponse fausse à une question, et le taux « bon outil » (81 %) surestime la justesse réelle (25 sur 43 à la lecture).

**Critères d'acceptance :**
- [x] CA1 — `AGENT_MODE=prioritaire` (défaut inchangé : `off`). `interpreteur_commandes._l_agent_d_abord` envoie toute phrase libre à l'agent avant les règles. `interpreteur_agent.proposer(prioritaire=True)` offre le catalogue complet, les outils de savoir et l'annulation dès qu'une action récente peut l'être, avec `PROMPT_FIXE_PRIORITAIRE`. Les règles servent de mode dégradé si l'agent est indisponible. `agent_actif()` remplace les tests `== "actif"` (corrections, conversation).
- [x] CA2 — Le corpus `tests/corpus/terrain_compagnon_2026_11.json` porte 35 dialogues réels (43 tours), chacun avec son échange d'origine et ce que le jardinier avait reçu.
- [x] CA3 — `tools/evaluer_dialogues.py` accepte `--mode`, `--corpus`, `--potager` et `--utilisateur` (vraies données en lecture seule). La grille du 01/11/2026 est dans `TARIFS_01_11_2026`. Les modèles par défaut du mode `prioritaire` sont `ministral-8b-2512`, `ministral-14b-2512` et `mistral-small-2603`.
- [x] CA4 — Deux couperets au jardinier : « confirmation sans proposition » et « salut en plein dialogue ». Les trois lectures du savoir ne comptent plus comme des écritures. Un `abandonner_proposition` suivi d'une écriture compte comme une correction.
- [x] CA5 — Trois passages, avec accord, au volume annoncé (coût réel : 0,29 $). Les trois rapports et l'analyse sont dans le dossier de l'épic.
- [x] CA6 — Texte attendu : un tour peut porter `attendu.texte_attendu`, une liste d'expressions dont au moins une doit figurer dans le texte lu par le jardinier. Les 16 questions du corpus de terrain en reçoivent une (TER-03 : « radis » ; TER-04 : « Lyon », jamais « mm de pluie sur les 3 derniers jours » ; TER-07 : la date du jour…). Une réponse en texte sans le texte attendu n'est pas un bon outil. Le rapport ajoute une colonne « réponses justes ».
- [x] CA7 — `pytest tests/test_agent_prioritaire.py` est vert ; `tests/test_us256_evaluer_dialogues.py` aussi (assertion DOU-2 adaptée au nouveau couperet, `test_us236` gardé grâce à `_l_agent_d_abord`).

**Hors périmètre :**
- Les corrections révélées par la mesure : US-281 à US-286.
- La bascule du bot : US-287.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur, outil de mesure
- Migration BDD requise : non
- Dépendances : US-256 (outil de mesure), US-257 (boucle), US-276 (projection, gardée en mode `actif`)
- Code concerné : `app/config.py`, `app/services/interpreteur_commandes.py`, `app/services/agent/interpreteur_agent.py`, `app/services/compagnon/corrections.py`, `tools/evaluer_dialogues.py`, `tests/corpus/terrain_compagnon_2026_11.json`, `tests/test_agent_prioritaire.py`
- Aucun changement de comportement pour le jardinier tant que `AGENT_MODE` n'est pas `prioritaire` : aucune fiche de `data/connaissance/` n'est rendue fausse
- Production conseillée : **Sonnet 5.5, effort `medium`** pour le CA6

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le corpus de terrain et les données du potager 33
When je lance "python tools/evaluer_dialogues.py --mode prioritaire --corpus tests/corpus/terrain_compagnon_2026_11.json --potager 33 --utilisateur 2"
Then chaque phrase va d'abord à l'agent
And aucune écriture n'est exécutée
And une réponse « Il est tombé 0.0 mm de pluie » à « Quelle météo sur Lyon ? » est comptée fausse
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `mesure`
