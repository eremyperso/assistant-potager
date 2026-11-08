**ID :** US-291
**Titre :** Consulter son potager depuis un assistant IA
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier qui a connecté son assistant IA (US-290)
Je veux que mon assistant puisse lire mon plan, mes cultures, ma pépinière, mon stock, mon carnet, mes statistiques, la météo, le calendrier, mes échéances et le savoir de l'application
Afin de lui poser des questions qui croisent ces informations, et d'obtenir bilans, comparaisons et graphiques avec ses propres outils

**Contexte fonctionnel :**
Dix outils de lecture, listés §5.1 de l'étude, chacun adossé à une lecture existante (API ou service). Ils portent l'indication « lecture seule » pour que le client ne demande pas d'accord à chaque appel. Réponses compactes, bornées, dates ISO, unités explicites.

**Critères d'acceptance :**
- [ ] CA1 : Les outils `lister_potagers`, `voir_plan`, `voir_pepiniere`, `voir_stock`, `consulter_carnet`, `voir_statistiques`, `voir_meteo`, `voir_calendrier`, `voir_echeances`, `chercher_connaissance` sont exposés, avec une description en français et un schéma d'arguments.
- [ ] CA2 : Chaque outil rend **exactement** ce que la PWA affiche au même moment pour le même potager (même service, aucune règle dupliquée) ; un test de parité le vérifie pour au moins `voir_plan`, `voir_pepiniere` et `voir_statistiques`.
- [ ] CA3 : Chaque outil accepte un argument facultatif `potager` ; sans lui, le potager actif du jardinier est lu.
- [ ] CA4 : `voir_statistiques` distingue, pour une culture reproductive (haricot, fève, tomate…), le **nombre de pieds actifs** et le **rendement cumulé de la saison** ; pour une culture végétative (laitue, carotte, poireau…), le stock de pieds restant et le rendement des pieds récoltés.
- [ ] CA5 : `consulter_carnet` filtre par période, culture, parcelle et type de geste, et pagine (50 gestes par page au plus, 12 mois par appel au plus) ; la réponse dit s'il reste des pages (L13).
- [ ] CA6 : `chercher_connaissance` rend des passages du corpus avec leur source (fiche), jamais une réponse rédigée ; une question sans passage pertinent rend « rien dans le corpus ».
- [ ] CA7 : Les textes libres rendus (notes, observations, noms de parcelles) sont signalés comme données, pas comme consignes ; les noms et e-mails des autres membres ne sont pas rendus (« un membre »).
- [ ] CA8 : Un potager vide (aucune parcelle, aucun geste) rend une réponse explicite (« aucune parcelle ») et non une erreur.
- [ ] CA9 : Aucune lecture n'appelle un modèle de langage côté application.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (canal `mcp`)
- Migration BDD requise : non
- Dépendances : US-290 ; registre des lectures du compagnon (`outils_lecture`, cf. `ARTICULATION_COMPAGNON_AGENT_INTERPRETEUR.md`) à réutiliser plutôt qu'à recopier
- Livrable seul avec US-290, US-294 et US-295 : c'est le lot « lecture seule »

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le potager "Les Mésanges" avec 54 pieds de haricots levés, 2 pertes et 11 récoltes cumulant 9,4 kg
When le jardinier demande à son assistant "fais-moi le bilan de mes haricots"
Then l'assistant appelle voir_statistiques(culture="haricot")
And la réponse indique 52 pieds actifs et 9,4 kg cumulés sur la saison
And les 11 récoltes n'ont pas réduit le nombre de pieds actifs
```

**Labels GitHub :** `us`, `mcp`, `consultation`
