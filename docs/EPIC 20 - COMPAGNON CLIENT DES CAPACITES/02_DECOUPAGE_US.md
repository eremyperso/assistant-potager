# 02 — Découpage en US, effort et état

Modèle et effort : valeurs inscrites dans chaque fiche du backlog (« Modèle / effort conseillé »), au plus économique. Le modèle
désigne celui qui **écrit le code** dans Claude Code ; le compagnon lui-même tourne sur Mistral Small 4.

## 1. Les 16 US

| Lot | US | Titre | Pts | Modèle · effort | Migration | État | Jira |
|---|---|---|---|---|---|---|---|
| 0 | **US-336** | Constituer le jeu d'évaluation du compagnon | 5 | Sonnet 5.5 · medium | non | ✅ Livrée, non commitée ⚠️ numéro à régler | *(PIA-319 est une autre US-336)* |
| 0 | **US-337** | Lanceur d'évaluation commun, juge et rapport | 5 | Sonnet 5.5 · medium | non | ✅ Livrée ; CA8 : ligne de base G0 mesurée le 20/11 ([06](06_LIGNE_DE_BASE_G0.md)) ; CA0 : prototype reconstitué, hors dépôt | PIA-320, En cours |
| 1 | **US-338** | Extraire le registre de capacités en couche neutre ; le serveur MCP devient un adaptateur | 5 | Sonnet 5.5 · medium | non | ✅ Livrée le 20/11, non commitée (v3.135.0) | PIA-321, Revue en cours |
| 1 | **US-339** | Capacité `situation_culture` : « est-ce le moment ? » | 3 | Sonnet 5.5 · low | non | À faire | PIA-322 |
| 1 | **US-340** | Capacité `que_faire_maintenant` : « qu'est-ce que je fais au potager ? » | 3 | Sonnet 5.5 · low | non | À faire | PIA-323 |
| 1 | **US-341** | Rattacher la recherche de connaissance à une culture et dire quand le savoir manque | 3 | Sonnet 5.5 · low | non (colonne éventuelle à dire au cadrage) | À faire | PIA-324 |
| 1 | **US-351** | Lectures associations, bon moment pour semer, potager et abris (références humaines du 18/11) | 3 | Sonnet 5.5 · low | non | À faire (ajoutée le 20/11) | *(à créer)* |
| 2 | **US-342** | Boucle du compagnon (le modèle conduit) derrière un interrupteur, dans la PWA | 8 | **Opus 5.5 · high** | non | À faire | PIA-325 |
| 2 | **US-343** | Fil de conversation complet, borné et compacté | 5 | **Opus 5.5 · high** | **oui, probablement** (v81 ?) | À faire | PIA-326 |
| 3 | **US-344** | Écritures par le registre, carte et confirmation dans les deux canaux | 5 | Sonnet 5.5 · medium | non | À faire | PIA-327 |
| 3 | **US-345** | Corrections, annulations, rappels et carnet dans le registre | 3 | Sonnet 5.5 · medium | non | À faire | PIA-328 |
| 4 | **US-346** | Telegram, voix, messages spontanés et contexte d'écran sur la boucle | 5 | Sonnet 5.5 · medium | non | À faire | PIA-329 |
| 5 | **US-347** | Retirer l'ancien moteur de l'agent | 5 | Sonnet 5.5 · **high** | non | À faire | PIA-330 |
| savoir | **US-348** | Fiches agronomiques des cultures courantes manquantes, puis ingestion | 8 | Sonnet 5.5 · medium | non | À faire | PIA-331 |
| savoir | **US-349** | Compléter le référentiel là où la fiche culture affiche « non renseigné » | 3 | Sonnet 5.5 · low | non (données) | À faire | PIA-332 |
| — | **US-350** | Passerelle : `top_p` en échantillonnage glouton, contenu rendu en liste | 2 | **Haiku 5.5 · low** | non | À faire | PIA-333 |
| | **Total** | | **71** | | | | |

## 2. Ce que chaque US livre, en une phrase

| US | Ce que le jardinier ou le produit voit après |
|---|---|
| 336 | Un jeu de 24 besoins × 5 à 7 formulations (134 cas), avec fiche de besoin et attendus ; le dialogue du 14/11 en cas n° 1 |
| 337 | Une commande qui joue ce jeu sur la chaîne actuelle, la boucle cible ou Claude + MCP, avec juge, trace complète et rapport avant / après |
| 338 | Rien de visible : le MCP continue de répondre à l'identique, mais sur un registre que le compagnon peut appeler (test de parité) |
| 339 | « Est-ce le moment de planter des salades ? » → un verdict (« pas ce mois-ci, prochaine fenêtre : semis en pépinière de février à mars »), le même que la fiche Salade de la PWA |
| 340 | « Qu'est-ce que je fais au potager ? » → une réponse tirée des échéances, des verdicts de saison et de « Aujourd'hui au potager » |
| 341 | Une question sur la salade ne rend jamais un passage sur la tomate ; sans fiche, la capacité le dit (« pas de fiche salade ») |
| 351 | Les associations, « le bon moment pour semer » et les abris du potager arrivent au compagnon par le même service que l'écran ; la ville du potager se règle dans « Modifier le potager », et le guide le dit |
| 342 | Dans la PWA, derrière `COMPAGNON_MOTEUR=capacites`, le compagnon garde le fil sur plusieurs tours, lit avant de répondre et ne redemande pas ce qui est dit |
| 343 | Le compagnon se souvient de ce qu'il a lu (résultats d'outils datés) ; les vieux tours sont résumés en « faits établis » |
| 344 | Le geste dit en conversation devient une proposition avec carte et boutons (PWA et Telegram), ou se confirme d'une phrase ; une destruction ne se confirme qu'au bouton |
| 345 | « Non, 3 rangs », « annule », « rappelle-moi demain », « retiens que… » passent par le registre, à parité avec l'agent actuel |
| 346 | Telegram (texte et voix), les messages spontanés et le contexte d'écran tournent sur la même boucle : un seul moteur |
| 347 | L'ancien moteur (catalogue projeté, contexte court, règles de langage) disparaît ; la documentation est mise à jour |
| 348 | Fiches de conduite et de problèmes pour salade, laitue, mâche, radis, épinard, poireau, oignon, pomme de terre, fraise, petit pois, betterave |
| 349 | La fiche culture n'affiche plus « non renseigné » pour la plantation, l'exposition, le besoin en eau |
| 350 | La passerelle accepte Large 3 (`top_p`) et Large 4 (contenu en liste) : on peut comparer des modèles |

## 3. Effort : où il se concentre

| Modèle · effort | US | Points | Part |
|---|---|---|---|
| **Opus 5.5 · high** | 342, 343 | 13 | 18 % |
| Sonnet 5.5 · **high** | 347 | 5 | 7 % |
| Sonnet 5.5 · **medium** | 336, 337, 338, 344, 345, 346, 348 | 36 | 51 % |
| Sonnet 5.5 · **low** | 339, 340, 341, 349, 351 | 15 | 21 % |
| Haiku 5.5 · low | 350 | 2 | 3 % |

- **Opus n'est requis que pour la boucle et le fil** (US-342, US-343) : ils remplacent le cœur de la conversation et portent le
  risque de régression. Fable n'est requis nulle part.
- **Sonnet high pour le retrait (US-347)** : une suppression large expose à du code mort ou à une dépendance oubliée.
- **Les capacités (339 à 341) sont petites** : elles réutilisent des services de l'écran (`confiances_du_plan`, fiche culture,
  « Aujourd'hui au potager »).
- **US-348 est la plus longue en volume (8 pts)** mais la moins risquée : de la rédaction de fiches et une ingestion, sans code
  métier. Elle demande en revanche une **relecture agronomique** de votre part (voir [05_BESOINS_ATTENDUS.md](05_BESOINS_ATTENDUS.md)).

## 4. Points par lot

| Lot | US | Points | Nature |
|---|---|---|---|
| 0 — Mesurer | 336, 337 | 10 | Outillage, aucun code produit |
| 1 — Capacités à verdict | 338 à 341, 351 | 17 | Extraction + trois capacités + trois lectures d'écran |
| 2 — Boucle et fil | 342, 343 | 13 | Cœur de la conversation (Opus) |
| 3 — Écritures | 344, 345 | 8 | Parité avec l'agent actuel |
| 4 — Telegram et le reste | 346 | 5 | Un seul moteur |
| 5 — Retrait | 347 | 5 | Code mort |
| Savoir (transverse) | 348, 349 | 11 | Contenu |
| Passerelle | 350 | 2 | Fiabilité |
| | | **71** | |
