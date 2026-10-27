**ID :** US-256
**Titre :** Mesurer le compagnon conversationnel sur Ministral 3B, en plusieurs tours
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant qu'administrateur
Je veux rejouer des dialogues complets du compagnon sur le vrai modèle et lire, par catégorie, ce qu'il tient et ce qu'il rate
Afin de choisir le modèle sur preuve, et d'alléger la tâche du modèle avant de payer un modèle plus gros

**Contexte fonctionnel :**
Lot 0 du cadrage `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md` (§4.5, §7). Aucun rapport existant (US-233, US-235, INC-018) ne mesure `mistral/ministral-3b-latest`, modèle de référence retenu (décision D1). L'outil d'évaluation ne rejoue aujourd'hui que des phrases isolées ; le compagnon se juge sur des dialogues.

**Critères d'acceptance :**
- [ ] CA1 : L'outil d'évaluation rejoue des **dialogues à plusieurs tours** (phrase, réponse, clic ou phrase de suivi), et plus seulement des phrases isolées.
- [ ] CA2 : Le corpus couvre les dialogues du §12.2 de l'architecture, du §16.1 de l'étude d'articulation et du §1 du cadrage, rangés par catégorie (créations, plusieurs actions, négations, désignation d'une action `A1`…`A5`, questions croisées, doutes, conversation simple, hors catalogue, registres).
- [ ] CA3 : La mesure porte sur le **prompt livré** et le **catalogue livré**, avec une clé d'API **distincte** de celle du bot.
- [ ] CA4 : Ministral 3B est mesuré en référence ; `ministral-8b` et `mistral-small` ne sont mesurés que pour situer l'écart.
- [ ] CA5 : Le rapport donne, par catégorie : taux de bon outil, de bons paramètres, couperets (§12.10), latence p50/p95, jetons par message.
- [ ] CA6 : Pour chaque catégorie en échec, le rapport indique d'abord l'allègement du §4.5 qui le corrigerait (préchargement, catalogue projeté, tour de complément), et seulement ensuite le modèle qui le corrigerait, avec le surcoût chiffré.
- [ ] CA7 : Le rapport relève la grille tarifaire Mistral du jour et le fonctionnement du cache de prompt.
- [ ] CA8 : Les tests unitaires de l'outil simulent le modèle ; seule la mesure appelle le vrai modèle.
- [ ] CA9 *(ajouté le 27/10/2026 après la première mesure)* : Les dialogues sont rejoués par la cascade du bot (`interpreter`, mode `actif` : règles, garde de savoir, filtre des gestes, puis agent). Un tour que la cascade prend avant l'agent est noté sur son chemin et sorti des taux de l'agent. Les couperets se comptent à deux niveaux : ce que le modèle propose (une tendance), et ce qui arrive au jardinier après le validateur et la cascade (bloquant, code de sortie). Le couperet « phrase impérative rendue au routeur par mots-clés » devient mesurable.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (outillage d'évaluation)
- Migration BDD requise : non
- Dépendances : US-233, US-235
- Production conseillée : **Sonnet 5.5, effort `high`** — outillage sur un script existant ; l'effort élevé sert à l'interprétation du rapport et au rattachement de chaque échec à un allègement.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le corpus de dialogues du cadrage du compagnon
And une clé Mistral distincte de celle du bot
When l'administrateur lance l'évaluation sur ministral-3b-latest
Then un rapport par catégorie est produit
And chaque catégorie en échec propose un allègement avant un changement de modèle
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `evaluation`
