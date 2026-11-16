# Le compagnon, client de ses capacités

> **Statut** : proposition d'architecture du 14/11/2026, à valider. Elle révise
> [ARCHITECTURE_AGENT_INTERPRETEUR.md](ARCHITECTURE_AGENT_INTERPRETEUR.md) (§12 compris) sans en reprendre le
> cadre de départ.
> **Fondée sur** : la mesure d'agent d'abord du 01/11/2026 (décision D14,
> [ANALYSE_MESURE_AGENT_D_ABORD.md](../EPIC%20-%20COMPAGNON%20CONVERSATIONNEL/ANALYSE_MESURE_AGENT_D_ABORD.md)) et
> celle du 14/11/2026 sur quatre configurations
> ([RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md](RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md)).
> **Périmètre** : le compagnon conversationnel (PWA et Telegram) et le serveur MCP. Les commandes tapées, les
> boutons, l'exécution des écritures et la cascade de `/ask` ne sont pas touchés.
> **Rien n'est codé** : la migration (§6) passe d'abord par un jeu d'évaluation (§7), qui décide de chaque étape.

---

## 0. L'essentiel en une page

**Le constat.** Chaque révision de l'agent a gardé le principe posé le 10/10/2026 : « brancher un agent sur les
points d'entrée qui existent déjà, **sans refaire l'architecture** ». Le modèle reste donc un **traducteur vers les
commandes du bot**. Ses outils sont projetés depuis `FORMES_DICTABLES`. Sa mémoire est un texte recollé qui ne
garde pas ce qu'il a lu. Et une couche de code (cascade, filtres, 32 expressions régulières, réponses réécrites)
décide autour de lui. Chaque échec appelle une règle de plus, et une nouvelle formulation du même besoin retombe
dans une impasse.

**La preuve.** Sur le dialogue réel du 14/11 (« j'aimerai planter des salades », 7 tours) :
- avec la chaîne actuelle, Small 4 **et** Large 3 perdent l'intention et dérivent chacun vers une commande voisine ;
- avec les **lectures du serveur MCP** et l'**historique complet**, le **même** Small 4 tient le fil sur les
  7 tours, n'invente rien, écarte le hors-sujet, et consomme deux fois moins de jetons ;
- Claude avec le MCP fait de même et donne en plus le verdict de saison.

Le goulot n'est pas le modèle : c'est ce qu'on lui donne pour travailler.

**La proposition.**
1. **Une seule couche de capacités**, extraite du serveur MCP, que **deux clients** utilisent : le compagnon de
   l'application (Mistral Small 4) et les assistants extérieurs (Claude, Le Chat) par le MCP.
2. **Une capacité répond à une question de jardinier et rend un verdict** prêt à l'emploi, calculé par le même
   service que l'écran de la PWA. Ce n'est pas le miroir d'une commande.
3. **Le modèle conduit la conversation**, avec un historique complet (résultats d'outils compris), borné et commun
   à Telegram et à la PWA.
4. **Le code garde l'écriture, pas le langage** : le modèle propose, le code valide, le jardinier confirme, le code
   exécute. Cette chaîne est conservée telle quelle. Les règles de langage autour du modèle sont retirées.
5. **Aucune étape sans mesure** : un jeu d'évaluation (besoins × formulations × tours) est la condition de passage
   de chaque lot.

**Ce qu'on ne fait pas.** On ne balise pas un parcours par scénario (« planter X ») : un besoin exprimé autrement
retomberait dans la même impasse. On ne change pas de modèle pour compenser l'architecture.

---

## 1. Pourquoi réviser

### 1.1 Ce que vit le jardinier

Le 14/11/2026, un compte neuf avec une seule parcelle demande au compagnon de la PWA de planter des salades. En
sept tours, il n'obtient ni conseil ni proposition. Au tour 5, le compagnon lui demande quelle culture il veut
planter. Au tour 7, il répond avec un passage sur les tomates. Pourtant, la fiche Salade de la même PWA affiche la
bonne réponse : « Rien à semer ni planter ce mois-ci. Prochaine fenêtre : semer en pépinière de février à mars. »

### 1.2 Quatre causes de structure

| Cause | Où dans le code | Effet observé |
|---|---|---|
| **Les outils sont la grammaire des commandes.** « Aucun outil n'est écrit à la main », ils sont projetés depuis `FORMES_DICTABLES` | `app/services/agent/catalogue_outils.py` | Un besoin qui n'est pas une commande (« est-ce le moment ? ») n'a pas de chemin : le modèle prend la commande la plus proche (`programmer_rappel`, `modifier_parcelle`) |
| **La mémoire est du texte recollé, sans ce qui a été lu.** 10 échanges, 30 min, « les résultats des lectures ne sont pas conservés » (§12.5) ; ancre « phrase ; réponse ; réponse » | `app/services/agent/contexte_court.py`, `interpreteur_agent.py` l. 952-967 et 1137-1154 | L'intention disparaît dès qu'un tour se termine sans question en attente (échange 442) |
| **Le code interprète la langue autour du modèle.** Cascade, filtres, règles « demande nouvelle », « offre une action », « refus », 10 consignes conditionnelles, 20 US citées dans l'interpréteur | `app/services/agent/` (5 500 lignes, 32 expressions régulières), `interpreteur_commandes.py` | Deux systèmes lisent la même phrase ; quand ils divergent, le jardinier perd |
| **Le code réécrit la réponse du modèle.** Le résumé du premier passage devient le texte affiché | `app/services/agent/savoir.py::chercher_connaissance` (US-283) | Le passage sur la tomate est montré même quand le modèle a bien formulé sa recherche (Large 3, tour 1) |

À quoi s'ajoute une cause de contenu : **le savoir manque**. Les 20 fiches agronomiques couvrent 10 cultures,
et la recherche, en plein texte et sans notion de culture, laisse passer un passage hors sujet bien noté.

### 1.3 Pourquoi les correctifs ne convergent pas

D14 (01/11/2026) avait trouvé la bonne cause : « le code décide avant le modèle ». La réponse a été de mettre
l'agent en premier, **en gardant le catalogue des commandes et la mémoire courte**, puis d'ajouter des garde-fous
(US-281 à US-287). Chaque correctif était juste localement. Ensemble, ils ont épaissi la couche qui interprète
autour du modèle, c'est-à-dire la cause elle-même.

---

## 2. Ce que les mesures établissent

| Critère | Small 4 actuel | Large 3 actuel | Small 4 + capacités + historique | Claude + MCP |
|---|---|---|---|---|
| Intention gardée sur 7 tours | non | non | **oui** | **oui** |
| Dérive vers une commande hors sujet | oui | oui | **non** | **non** |
| Hors-sujet montré au jardinier | oui | oui (×2) | **non** | **non** |
| Verdict de saison au tour 1 | non | non | non (outil « indéterminé ») | oui |
| Jetons d'entrée, 7 tours | 108 894 | ≈ 158 000 | **51 211** | n/a |

Trois enseignements guident la suite :
- **l'architecture d'abord** : le même modèle change de comportement quand on change ses outils et sa mémoire ;
- **des verdicts, pas des données brutes** : un petit modèle ne reconstitue pas un verdict à partir de fenêtres de
  calendrier, un gros modèle si ; c'est au code de calculer le verdict, une fois, pour tous les clients ;
- **l'historique complet coûte moins qu'on le craignait** : 86 % des jetons d'entrée sont servis par le cache,
  parce que le préfixe (prompt, outils, début de conversation) ne bouge pas.

Ces résultats reposent sur un dialogue. Le §7 dit comment les confirmer avant d'écrire du code.

---

## 3. Les principes

| # | Principe | Ce qu'il exclut |
|---|---|---|
| P1 | **Une couche de capacités, deux clients.** Le compagnon et le serveur MCP appellent le même registre ; une amélioration profite aux deux | Un catalogue pour l'agent et un autre pour le MCP |
| P2 | **Une capacité répond à une question de jardinier et rend un verdict**, avec les données qui le fondent. Le verdict sort du service qui sert l'écran de la PWA : une seule source de vérité | Un outil par commande ; un outil qui rend des données brutes à interpréter |
| P3 | **Le modèle conduit la conversation.** Il choisit ses lectures, rédige sa réponse et pose ses questions | Une cascade qui décide avant lui ; un texte réécrit par le code |
| P4 | **L'historique complet, borné.** Phrases, appels d'outils, résultats et réponses, par jardinier et par potager, communs à Telegram et à la PWA | Une ancre concaténée ; une question en attente reconstituée par des règles |
| P5 | **Le code garde l'écriture, pas le langage.** Proposer → valider → confirmer → exécuter, inchangé ; les garde-fous portent sur les actions, jamais sur l'interprétation de la phrase | Des expressions régulières qui décident si une phrase est un refus, une offre ou une demande nouvelle |
| P6 | **Le savoir structuré d'abord.** Le référentiel (fenêtres, durées, familles, bioagresseurs) passe par les capacités ; le texte est rattaché à une culture ; un trou de couverture se dit | Une recherche en plein texte qui rend le meilleur passage, quelle que soit la culture |
| P7 | **La mesure décide.** Un lot n'avance que s'il améliore le jeu d'évaluation sans régression ; un raccourci déterministe ne reste que s'il bat le modèle à la mesure | Un correctif pour un scénario ; une livraison jugée sur un modèle simulé |

---

## 4. La structure cible

### 4.1 Vue d'ensemble

```
   PWA (panneau compagnon)      Telegram (texte, voix)        Claude, Le Chat…
            │                           │                            │
            └──────────┬────────────────┘                            │ MCP (OAuth, JSON-RPC)
                       ▼                                             ▼
          ┌──────────────────────────┐                  ┌─────────────────────────┐
          │  Boucle du compagnon     │                  │  Adaptateur MCP          │
          │  (Mistral Small 4)       │                  │  (serveur.py : quotas,   │
          │  prompt court, outils,   │                  │   portée, journal)       │
          │  historique complet      │                  └────────────┬────────────┘
          └───────┬──────────┬───────┘                               │
                  │          │ lit / écrit                           │
                  │          ▼                                       │
                  │   ┌───────────────┐                              │
                  │   │ Fil de        │                              │
                  │   │ conversation  │                              │
                  │   └───────────────┘                              │
                  ▼                                                  ▼
          ┌────────────────────────────────────────────────────────────────┐
          │                 Registre de capacités (unique)                  │
          │  Lectures à verdict   ·   Propositions d'écriture   ·  Décisions │
          └───────────────┬────────────────────────────┬───────────────────┘
                          ▼                            ▼
          Services métier de la PWA          Propositions → validateur →
          (confiance_semis, plan, stock,     confirmation (boutons PWA et
           pépinière, carnet, météo,         Telegram) → exécution →
           connaissance)                     actions menées
```

### 4.2 Le registre de capacités

**Point de départ.** Le registre existe : `REGISTRE` dans `app/services/mcp/serveur.py`, rempli par
`lectures.py` (9 lectures, US-291), `ecritures.py` (propositions, US-292) et `commandes.py` (US-293). Il est
aujourd'hui attaché au serveur MCP. Il devient un module neutre (`app/services/capacites/`, par exemple) ; le
serveur MCP n'en est plus qu'un adaptateur (OAuth, quotas, portée, journal `mcp_appels`).

**Règle d'écriture d'une capacité.**
- Elle porte le nom et la description d'une **question de jardinier** (« est-ce le moment pour cette culture ? »),
  pas d'une commande.
- Elle rend un **verdict** et les données qui le fondent. Exemple : `{"verdict": "pas ce mois-ci", "prochaine":
  "semis en pépinière, février à mars", "au_potager": "absente", "alternatives": […], "fenetres": […]}`.
- Le verdict sort du **service de l'écran** qui le montre déjà. Pour la saison, c'est
  `confiance_semis.confiances_du_plan`, que la fiche culture lit par `GET /plan/confiances/candidates`.
- Elle est testée une fois, pour les deux clients.
- Les champs saisis par le jardinier restent marqués comme données, avec l'`avertissement_donnees` actuel.

**Inventaire visé.** Il est à affiner au lot 1, mais toujours guidé par les questions des jardiniers.

| Capacité | Question de jardinier | Base existante |
|---|---|---|
| `situation_culture` | Est-ce le moment ? Où en est cette culture chez moi ? Quoi faire ensuite ? | `confiances_du_plan`, fiche culture (US-207), `voir_calendrier`, `voir_plan` |
| `que_faire_maintenant` | Qu'est-ce que je dois faire au potager ? Qu'est-ce que je peux semer ce mois-ci ? | `voir_echeances`, confiances par culture, « Aujourd'hui au potager » (US-328) |
| `voir_plan`, `voir_pepiniere`, `voir_stock`, `consulter_carnet`, `voir_statistiques`, `voir_meteo` | Les lectures du potager | MCP (US-291), inchangées |
| `chercher_connaissance` | Comment fait-on ? Qu'est-ce que c'est ? | MCP (US-291), à rattacher à une culture (§4.6) |
| `proposer_geste`, `proposer_commande`, `proposer_correction` | Note ce geste, fais ce changement, corrige ce que j'ai dit | MCP (US-292, US-293) → `gestes_conversation`, `propositions` |
| `confirmer_proposition`, `abandonner_proposition` | Oui / laisse tomber, par une phrase | MCP (US-292) |
| `retenir_carnet`, `programmer_rappel`, `corriger_action`, `annuler_action` | Retiens, rappelle-moi, corrige ce que tu as fait | Agent actuel (US-262, US-265, US-268), à porter dans le registre |

Une quinzaine de capacités au total, comme le plafond actuel, mais chacune répond à une question.

### 4.3 La boucle du compagnon

- **Un appel, des outils, un texte.** `tool_choice="auto"` : le modèle lit ce qu'il veut (plusieurs lectures si
  besoin), puis rédige sa réponse. Un nombre d'étapes maximal par tour (6 dans le prototype) protège de la boucle.
- **Le texte est celui du modèle.** Le code ajoute ce qui ne se rédige pas : la carte de proposition avec ses
  boutons, la source citée, le lien vers un écran (`ouvrir_dans_l_application`).
- **Un prompt court et générique** : rôle, date, règles de données (« lis avant de répondre, n'invente ni
  parcelle ni quantité »), règle d'écriture (« propose, l'application fait confirmer »), règles de prudence
  (jamais de dose ni de produit de traitement, reprises de `_PROMPT_FIXE_RAISONNEMENT`). Aucune consigne de
  scénario.
- **Point d'entrée** : `app/services/compagnon/orchestrateur.py` (US-270) reste la porte unique des canaux. Sa
  fonction `distribuer` appelle la nouvelle boucle derrière un interrupteur (§6, lot 2). Les gardes de dialogue du
  canal (profil, carnet) et les commandes tapées restent devant.

### 4.4 Le fil de conversation

| Aspect | Aujourd'hui | Cible |
|---|---|---|
| Contenu | Phrase, texte du compagnon, noms des outils, question en attente | **Messages complets** : phrase, appels d'outils avec arguments, résultats, réponse |
| Résultats de lecture | Non conservés (§12.5) | Conservés, **datés**. Le prompt demande de relire avant d'écrire une donnée vieille de plus de quelques minutes |
| Bornes | 10 échanges, 30 min | Fenêtre glissante (par exemple les 12 derniers tours complets), les plus anciens **compactés** en un résumé des faits établis (culture, parcelle, date, ce qui manque) ; durée à arbitrer (§9) |
| Canaux | Commun Telegram et PWA | Inchangé : un fil par jardinier et par potager |
| Stockage | `echanges_conversation` (colonnes `outils`, `question`) | Même table, enrichie d'une colonne `messages` (JSON), ou une table dédiée : à trancher au lot 2 |

La crainte du §12.5 (« une donnée lue il y a dix minutes est relue plutôt que crue ») reste fondée pour
l'**écriture**. Le validateur relit toujours en base au moment de proposer et d'exécuter. Elle ne justifie pas
de priver le modèle de ce qu'il a lu pour **comprendre** la phrase suivante.

### 4.5 L'écriture : ce qui ne change pas

Le chemin d'écriture actuel est sûr et partagé par les canaux. Il est conservé tel quel :
- `proposer_*` crée une proposition (`gestes_conversation` pour un geste, `propositions` pour une commande) ;
- le contrôle (`svc_gestes_dits.controler`, validateur des commandes) refuse une parcelle inconnue, une date
  future, une quantité non dite, et rend la question à poser ;
- la carte de proposition part dans les deux canaux (`deux_canaux.apres_creation`) ;
- le jardinier confirme au bouton, ou par une phrase via `confirmer_proposition` ;
- l'exécution écrit et inscrit l'action menée (`actions_menees`), ce qui permet de la corriger ou de l'annuler ;
- une action destructrice ne se confirme qu'au bouton.

### 4.6 Le savoir

- **Structuré d'abord.** Les questions de saison, de durée, de rotation ou d'association passent par les
  capacités qui lisent le référentiel. Le référentiel connaît déjà salade, laitue, radis, poireau…
- **Texte rattaché à une culture.** `chercher_connaissance` reçoit (ou repère) la culture visée et ne rend que les
  passages de cette culture, ou des passages généraux. Un passage d'une autre culture n'est jamais rendu.
- **Couverture explicite.** Sans fiche, la capacité le dit (« pas de fiche salade ») et rend ce que le référentiel
  sait. Le modèle peut alors donner un conseil général **en le signalant** (arbitrage §9).
- **Combler les trous.** Fiches de conduite et de problèmes pour les cultures courantes absentes (salade et
  laitue, mâche, radis, épinard, poireau, oignon, pomme de terre, fraise, petit pois, betterave), puis ingestion.
  Compléter le référentiel là où la fiche culture affiche « non renseigné » (fenêtre de plantation de la salade,
  exposition, besoin en eau).

### 4.7 Coût, latence, modèle

- **Modèle de référence** : Mistral Small 4 (`mistral-small-2603`), comme D14. Le prototype ne justifie pas d'en
  changer.
- **Jetons** : 51 211 en entrée pour les 7 tours du prototype, dont 86 % en cache, contre 108 894 pour la chaîne
  actuelle. À confirmer sur le jeu d'évaluation, avec la croissance de l'historique sur des conversations longues.
- **Latence** : 0,9 à 3,3 s par tour dans le prototype, dans la plage actuelle.
- **Passerelle** : deux incompatibilités relevées le 14/11 (`top_p` en échantillonnage glouton pour Large 3,
  `content` en liste pour Large 4). À corriger pour pouvoir comparer des modèles, sans changer celui de référence.

---

## 5. Ce qu'on garde, ce qu'on retire

| Élément | Sort | Raison |
|---|---|---|
| Validateur des écritures, propositions, confirmation, exécution, actions menées | **Gardé** | Le cœur sûr de l'architecture actuelle (§2.2, §3.5, §3.7) |
| Passerelle (`llm/passerelle.py`), `conso_tokens`, pilotage LLM (épic 18) | **Gardé** | Journal, coût et provenance des appels |
| Registre et lectures MCP (US-290 à US-297) | **Gardé, extrait** en couche neutre | Ce sont déjà des capacités |
| Orchestrateur (US-270) | **Gardé, simplifié** | Porte unique des canaux |
| Commandes tapées, boutons, parseur de gestes déterministe | **Gardés** | Raccourcis certains ; le parseur reste seulement s'il bat la boucle à la mesure (P7) |
| Catalogue projeté des commandes (`catalogue_outils.py`) | **Retiré** de l'interface du modèle | Remplacé par le registre ; les formes dictables restent pour les commandes tapées |
| Contexte court, ancre, question en attente (`contexte_court.py`, parties d'`interpreteur_agent.py`) | **Retiré** | Remplacé par le fil complet |
| Règles de langage autour du modèle (`_demande_nouvelle`, `offre_une_action`, `refuse_la_question`…) | **Retirées** au fil des mesures | Le modèle lit l'historique ; le code garde l'écriture |
| Texte réécrit par le code (relances, résumé de passage d'US-283) | **Retiré** | La réponse est celle du modèle ; le code ajoute cartes, sources, liens |
| Cascade des questions (`/ask`, repli si le modèle est indisponible) | **Gardée** hors du compagnon | Aucune raison d'y toucher ici |

Le retrait est le **dernier** lot : l'ancien moteur reste en place derrière l'interrupteur tant que le nouveau n'a
pas passé la mesure.

---

## 6. Migration

### 6.1 Les lots

| Lot | Contenu | Sortie |
|---|---|---|
| **0. Mesurer** | Jeu d'évaluation (§7) ; lanceur commun capable de jouer la chaîne actuelle et la boucle cible (le prototype du 14/11 en est le point de départ) ; ligne de base de la chaîne actuelle | Un chiffre de départ par critère |
| **1. Capacités à verdict** | Registre extrait en couche neutre, MCP en adaptateur (contrat externe inchangé) ; `situation_culture`, `que_faire_maintenant` ; `chercher_connaissance` rattaché à une culture | Le MCP et le prototype en profitent aussitôt ; mesure |
| **2. Boucle et fil** | Boucle du compagnon derrière `COMPAGNON_MOTEUR=capacites` (PWA d'abord) ; fil de conversation complet et compacté | Le jeu d'évaluation passe sur la PWA de dev |
| **3. Écritures** | Propositions par le registre, cartes et boutons PWA et Telegram, confirmation par phrase, corrections et annulations | Parité avec l'agent actuel sur les écritures |
| **4. Telegram et le reste** | Telegram sur la nouvelle boucle ; voix (US-298 à US-305) ; messages spontanés (US-267) ; contexte d'écran (US-323) | Les deux canaux sur un seul moteur |
| **5. Retrait** | Ancien moteur, catalogue projeté, contexte court et règles retirés ; documentation mise à jour | Le code mort disparaît |
| **Savoir** (transverse) | Fiches des cultures courantes, compléments du référentiel, carte de couverture | Peut commencer tout de suite, sans dépendance |

### 6.2 Découpage indicatif en US

| US (provisoire) | Lot | Pts | Modèle | Effort |
|---|---|---|---|---|
| Jeu d'évaluation : besoins, formulations, attendus, données de test | 0 | 5 | Sonnet | moyen |
| Lanceur d'évaluation commun (chaîne actuelle et boucle cible), juge et rapport | 0 | 5 | Sonnet | moyen |
| Registre de capacités neutre, MCP en adaptateur | 1 | 5 | Sonnet | moyen |
| Capacité `situation_culture` (verdict de saison partagé avec la fiche culture) | 1 | 3 | Sonnet | faible |
| Capacité `que_faire_maintenant` | 1 | 3 | Sonnet | faible |
| Connaissance rattachée à une culture, couverture explicite | 1 | 3 | Sonnet | faible |
| Boucle du compagnon derrière un interrupteur (PWA) | 2 | 8 | **Opus** | élevé |
| Fil de conversation complet, borné et compacté | 2 | 5 | **Opus** | élevé |
| Écritures par le registre, cartes et confirmation dans les deux canaux | 3 | 5 | Sonnet | moyen |
| Corrections, annulations, rappels et carnet dans le registre | 3 | 3 | Sonnet | moyen |
| Telegram, voix, messages spontanés et contexte d'écran sur la nouvelle boucle | 4 | 5 | Sonnet | moyen |
| Retrait de l'ancien moteur | 5 | 5 | Sonnet | élevé |
| Fiches agronomiques des cultures courantes manquantes + ingestion | savoir | 8 | Sonnet | moyen |
| Compléments du référentiel (plantation, exposition, eau…) | savoir | 3 | Sonnet | faible |
| Passerelle : `top_p` en échantillonnage glouton, `content` en liste | — | 2 | Haiku | faible |

**Synthèse de production** : 68 points environ. Opus n'est requis que pour la boucle et le fil (lot 2), qui
remplacent le cœur de la conversation et portent le risque de régression. Le reste relève de Sonnet. Fable n'est
requis nulle part. Haiku suffit pour la passerelle.

---

## 7. Évaluation : condition de passage

### 7.1 Le jeu

- **Une vingtaine de besoins courants** : planter ou semer une culture, savoir si c'est le moment, que semer ce
  mois-ci, que faire au potager, arroser ou non, noter un geste (semis, plantation, récolte, perte), corriger ce
  qui a été noté, lire son stock ou son carnet, comprendre un symptôme, trouver une fonction de l'application.
- **Chaque besoin en 5 à 10 formulations** : directe, familière, incomplète, avec faute, en deux temps (« oui »,
  « la planche sud », « demain »), avec une culture absente du savoir.
- **En plusieurs tours**, avec un utilisateur simulé qui répond aux questions du compagnon à partir d'une fiche de
  besoin (culture, parcelle, quantité, date).
- **Deux jeux de données** : un potager neuf (une parcelle, rien en stock) et un potager rempli (potager 33 en
  lecture seule, comme la mesure du 01/11).
- Le dialogue du 14/11 en est le premier cas.

### 7.2 Les critères

| Critère | Mesure | Seuil de passage (à confirmer) |
|---|---|---|
| Utile au premier tour | Le premier texte répond au besoin ou pose la seule question nécessaire | ≥ 80 % |
| Aboutit | Bonne réponse ou bonne proposition en 3 tours au plus | ≥ 85 % |
| Intention gardée | Jamais une question sur une valeur déjà dite | 100 % |
| Rien d'inventé | Parcelle, culture, quantité ou date jamais inventées | 100 % |
| Écriture sûre | Aucune écriture sans confirmation, aucune destruction non demandée | 100 % |
| Hors-sujet montré | Aucun passage d'une autre culture présenté comme réponse | 0 |
| Latence | p95 par tour | ≤ 4 s |
| Coût | Jetons d'entrée par tour, part servie par le cache | Au plus celui de la chaîne actuelle |

Les critères de sens (« utile », « aboutit ») sont notés par un juge (un modèle plus fort, avec une grille), et un
échantillon est relu par un humain. Les traces complètes (appels, arguments, résultats, textes) sont conservées
pour chaque passage.

### 7.3 La règle

Chaque lot se mesure avant et après, sur le même jeu, avec la chaîne actuelle comme témoin. Un lot qui dégrade un
critère à 100 % ne passe pas. Chaque passage sur le vrai modèle se fait avec accord, volume et coût annoncés.

---

## 8. Risques et parades

| Risque | Parade |
|---|---|
| L'historique complet fait grossir les prompts | Fenêtre glissante, compaction des anciens tours, résultats tronqués ; le cache absorbe le préfixe (86 % mesuré) ; coût suivi par critère |
| Un petit modèle raisonne mal sur des données brutes | Capacités à verdict (P2) ; c'est le code qui calcule, le modèle qui explique |
| Un texte de jardinier détourne le modèle (injection par les données) | `avertissement_donnees` sur chaque résultat ; aucune écriture sans proposition validée et confirmée ; destruction au bouton seulement |
| Régression pendant la migration | Interrupteur `COMPAGNON_MOTEUR`, ancien moteur conservé jusqu'au lot 5, jeu d'évaluation comme témoin |
| Le MCP et le compagnon divergent | Registre unique (P1) ; un test de parité vérifie que les deux clients voient les mêmes capacités |
| Particularités des fournisseurs (`top_p`, contenu en liste…) | Passerelle corrigée et couverte par un test par fournisseur ; modèle de référence inchangé |
| Le jeu d'évaluation devient lui-même une cible de réglage | Formulations tenues à part des exemples du prompt ; un tiers des cas renouvelé à chaque mesure |

---

## 9. Arbitrages à faire

| # | Question | Proposition |
|---|---|---|
| A1 | Cette révision remplace-t-elle le §12 d'ARCHITECTURE_AGENT_INTERPRETEUR.md ? | Oui, avec un renvoi dans l'en-tête de l'ancien document ; ses §2.2, §3.5 et §3.7 (sécurité de l'écriture) restent la référence |
| A2 | Le compagnon peut-il donner un conseil général hors corpus ? | Oui, signalé comme tel (« ne vient pas de l'application »), jamais pour une dose ni un traitement |
| A3 | Durée du fil de conversation | 12 tours complets, compaction au-delà ; reprise possible le lendemain sur le résumé |
| A4 | Modèle de référence | Small 4, à reconfirmer sur le jeu d'évaluation |
| A5 | Parseur de gestes déterministe devant la boucle | Gardé tant qu'il bat la boucle à la mesure (P7) |
| A6 | Ordre des canaux | PWA d'abord (lot 2), Telegram au lot 4 |
| A7 | Les US en cours sur l'ancien moteur (US-281 à US-287 et suivantes, non commitées) | Les terminer seulement si elles servent le lot 0 ou la sécurité de l'écriture ; sinon les geler |

---

## 10. Ce qui reste de l'ancien document

Les principes d'ARCHITECTURE_AGENT_INTERPRETEUR.md qui restent la référence :
- **« Le modèle propose, le code dispose »** (§2.2) ;
- **le validateur** (§3.5) ;
- **la confirmation liée à sa proposition** (§3.7) ;
- **l'évaluation sur le vrai modèle comme condition de livraison** (§12.10).

Ce qui est abandonné :
- **le cadre de départ** : traduire une phrase en commandes existantes, sans refaire l'architecture ;
- **le catalogue projeté** comme interface du modèle ;
- **la mémoire sans résultats de lecture** (§12.5).
