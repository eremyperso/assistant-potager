**ID :** US-295
**Titre :** Guider le modèle et le jardinier sur le canal MCP (ressources, prompts, mode d'emploi)
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier qui découvre le connecteur
Je veux que mon assistant sache comment parler à mon potager, que des demandes toutes prêtes me soient proposées, et qu'un mode d'emploi me dise ce qui marche et ce qui ne marche pas
Afin d'obtenir de bonnes réponses dès la première conversation et de ne pas chercher ce que le canal ne fait pas

**Contexte fonctionnel :**
Le modèle externe ne connaît pas notre domaine (végétatif / reproducteur, parcelles, pépinière par lot). On le lui dit par une ressource MCP et par les descriptions des outils. Les limitations L1 à L18 de l'étude sont expliquées au jardinier. Voir étude §5.3 et §8.

**Critères d'acceptance :**
- [ ] CA1 : La ressource `guide-du-potager` explique au modèle : le vocabulaire des gestes, la différence végétatif / reproducteur et ses conséquences sur le stock et le rendement, les dates au format ISO, « ne jamais inventer une parcelle : demander », « toujours présenter le récapitulatif avant de confirmer », « une destruction se fait dans l'application », « pour une question de jardinage, appeler `chercher_connaissance` et citer la source ».
- [ ] CA2 : La ressource `resume-du-potager` rend en une page : parcelles, cultures en place, lots en cours, zone climatique.
- [ ] CA3 : Quatre prompts sont proposés dans le client : « Bilan de la semaine », « Que semer ce mois-ci ? », « Préparer ma sortie au jardin », « Bilan de saison d'une culture ».
- [ ] CA4 : Une nouvelle fiche `data/connaissance/doc_app/assistants-ia-mcp.md` explique : connexion pas à pas pour Claude, ChatGPT et Le Chat, ce que l'assistant peut faire, les limitations en langage jardinier (pas de message spontané, pas de photo, pas de destruction, qualité selon l'assistant, données chez l'éditeur), la révocation. Elle est référencée dans la table du `README.md` de `doc_app` et ingérée.
- [ ] CA5 : Le compagnon (Telegram et PWA) répond juste à « je peux utiliser Claude avec mon potager ? » et « pourquoi ChatGPT ne peut pas supprimer ma parcelle ? » ; ces questions entrent dans `tests/corpus/us099_questions_fonctionnement.csv`.
- [ ] CA6 : Le guide utilisateur (manuel) reçoit un chapitre « Votre potager dans votre assistant IA », sous la limite de longueur Telegram par chapitre.
- [ ] CA7 : `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction assistant IA, documentation
- Migration BDD requise : non
- Dépendances : US-291 (US-292 et US-293 pour la partie écriture du guide)
- Exemples de référence : `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/EXEMPLES_UTILISATION.md`

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given un jardinier qui vient de connecter Le Chat à son potager
When il choisit le prompt "Préparer ma sortie au jardin"
Then Le Chat lit les échéances et la météo du potager
And propose une liste priorisée sans rien enregistrer
When le jardinier demande ensuite au compagnon Telegram "pourquoi Le Chat ne peut pas supprimer ma parcelle ?"
Then le compagnon répond qu'une suppression se confirme au bouton dans l'application, en citant la fiche assistants-ia-mcp
```

**Labels GitHub :** `us`, `mcp`, `documentation`, `corpus`
