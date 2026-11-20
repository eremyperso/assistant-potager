# 01 — Analyse : de l'agent interpréteur au compagnon client des capacités

Synthèse des deux documents d'architecture et de la mesure du 14/11/2026. On n'y recopie pas le détail : chaque section renvoie
à son paragraphe source.

## 1. Le chemin parcouru

| Date | Étape | Ce qu'elle a décidé | Source |
|---|---|---|---|
| 10/10/2026 | **Agent interpréteur** | « Brancher un agent sur les points d'entrée qui existent déjà, sans refaire l'architecture » : le modèle traduit une phrase en commandes du bot. Outils projetés depuis `FORMES_DICTABLES` | ARCHITECTURE_AGENT_INTERPRETEUR §0, §3.3 |
| 10-11/10 | Garanties d'écriture | **« Le modèle propose, le code dispose »** : validateur, confirmation liée à sa proposition. Ces garanties sont la partie saine de l'architecture | §2.2, §3.5, §3.7 |
| 23/10 | **Agent conversationnel** | L'agent livré est un aiguilleur (il ne rédige rien). Il devient conversationnel : il consulte, propose, rend compte. La contrainte d'économie de jetons est levée | §12 |
| 01/11 | **D14, « l'agent d'abord »** | Bonne cause trouvée (« le code décide avant le modèle »), mais réponse en gardant catalogue et mémoire courte, puis des garde-fous (US-281 à US-287) | ARCHITECTURE_COMPAGNON §1.3 |
| 14/11 | **Mesure sur un dialogue réel** | Quatre configurations sur « j'aimerai planter des salades » : la chaîne actuelle dérive, la boucle à capacités tient | RAPPORT_MESURE_1411 |
| 14/11 | **Architecture à capacités** | Révision qui remplace le §12 de l'ancien document | ARCHITECTURE_COMPAGNON_CAPACITES |
| 17/11 | **Épic 20** | 15 US, 68 points, découpage du §6.2 | `backlog/US-336` à `US-350` |

## 2. Le constat

Chaque révision de l'agent a gardé le même principe de départ : le modèle est un **traducteur vers les commandes du bot**. Quatre
causes de structure en découlent :

| Cause | Où | Effet |
|---|---|---|
| Les outils sont la grammaire des commandes | `app/services/agent/catalogue_outils.py` | Un besoin qui n'est pas une commande (« est-ce le moment ? ») n'a pas de chemin : le modèle prend la commande la plus proche (`programmer_rappel`, `modifier_parcelle`) |
| La mémoire est du texte recollé, sans ce qui a été lu | `contexte_court.py`, `interpreteur_agent.py` (10 échanges, 30 min) | L'intention disparaît dès qu'un tour finit sans question en attente |
| Le code interprète la langue autour du modèle | `app/services/agent/` (≈ 5 500 lignes, 32 expressions régulières), `interpreteur_commandes.py` | Deux systèmes lisent la même phrase ; quand ils divergent, le jardinier perd |
| Le code réécrit la réponse du modèle | `savoir.py::chercher_connaissance` (US-283) | Un passage sur la tomate est montré pour une question sur la salade |

À quoi s'ajoute une cause de **contenu** : les 20 fiches agronomiques ne couvrent que 10 cultures, et la recherche en plein texte
ignore la notion de culture.

**Pourquoi les correctifs ne convergent pas.** Chaque règle ajoutée est juste localement, mais l'ensemble épaissit la couche qui
interprète autour du modèle, c'est-à-dire la cause elle-même. Une nouvelle formulation du même besoin retombe dans une impasse.

## 3. Ce que la mesure du 14/11 établit

| Critère | A. Small 4 actuel | B. Large 3 actuel | C. Small 4 + capacités + historique | D. Claude + MCP |
|---|---|---|---|---|
| Verdict de saison au tour 1 | non | non | non (« indéterminé ») | oui |
| Intention gardée sur 7 tours | non | non | **oui** | **oui** |
| Dérive vers une commande hors sujet | oui | oui | **non** | **non** |
| Passage « tomate » montré | oui | oui (×2) | **non** | **non** |
| Rien d'inventé | oui | non | oui | oui |
| Jetons d'entrée, 7 tours | 108 894 (61 % en cache) | ≈ 158 000 | **51 211 (86 % en cache)** | n/a |
| Latence par tour | 0,6 à 3,0 s | 1,4 à 10,8 s | 0,9 à 3,3 s | n/a |

1. **La taille du modèle n'est pas le goulot** : Large 3 dérive comme Small 4, chacun vers la commande voisine.
2. **Les outils et la mémoire changent le comportement** : le même Small 4, avec capacités et historique complet, tient le fil.
3. **Une capacité doit rendre un verdict, pas des données brutes** : Small 4 n'a pas tiré la saison des fenêtres de calendrier.
4. **Le code qui réécrit la réponse aggrave l'erreur** (passage « tomate »).
5. **Le savoir manque** dans toutes les configurations (pas de fiche salade ni laitue).

*Limites* : un dialogue, un passage, un modèle qui ne répond pas toujours pareil. D'où le **lot 0** : ces résultats indiquent une
direction, le jeu d'évaluation doit la confirmer.

## 4. Les sept principes

| # | Principe | Ce qu'il exclut |
|---|---|---|
| P1 | **Une couche de capacités, deux clients** (compagnon et MCP) | Un catalogue pour l'agent, un autre pour le MCP |
| P2 | **Une capacité répond à une question de jardinier et rend un verdict**, issu du service qui sert l'écran de la PWA | Un outil par commande ; des données brutes à interpréter |
| P3 | **Le modèle conduit la conversation** | Une cascade qui décide avant lui ; un texte réécrit par le code |
| P4 | **L'historique complet, borné**, commun à Telegram et à la PWA | Une ancre concaténée ; une question en attente reconstituée par des règles |
| P5 | **Le code garde l'écriture, pas le langage** | Des regex qui décident si une phrase est un refus ou une offre |
| P6 | **Le savoir structuré d'abord**, texte rattaché à une culture, trou de couverture dit | Une recherche qui rend le meilleur passage quelle que soit la culture |
| P7 | **La mesure décide** | Un correctif pour un scénario ; une livraison jugée sur un modèle simulé |

## 5. La structure cible

```
   PWA (compagnon)        Telegram (texte, voix)        Claude, Le Chat…
          └────────┬──────────────┘                            │ MCP (OAuth)
                   ▼                                           ▼
        Boucle du compagnon (Small 4)                 Adaptateur MCP (quotas, portée, journal)
        prompt court · outils · historique complet              │
                   │  lit / écrit le fil de conversation        │
                   ▼                                           ▼
        ┌──────────────── Registre de capacités (unique) ───────────────┐
        │  Lectures à verdict  ·  Propositions d'écriture  ·  Décisions  │
        └──────────┬────────────────────────────┬───────────────────────┘
                   ▼                            ▼
        Services métier de la PWA       Propositions → validateur → confirmation
        (saison, plan, stock, carnet…)   (boutons PWA et Telegram) → exécution
```

## 6. Ce qu'on garde, ce qu'on retire

| Élément | Sort | Lot |
|---|---|---|
| Validateur des écritures, propositions, confirmation, exécution, actions menées | **Gardé** (cœur sûr) | — |
| Passerelle LLM, `conso_tokens`, pilotage LLM (épic 18) | **Gardé** (corrigé : US-350) | — |
| Registre et lectures MCP (US-290 à US-297) | **Gardé, extrait** en couche neutre | 1 |
| Orchestrateur (US-270) | **Gardé, simplifié** : porte unique des canaux | 2 |
| Commandes tapées, boutons, parseur de gestes déterministe | **Gardés** (le parseur seulement s'il bat la boucle à la mesure : A5) | — |
| Cascade des questions (`/ask`, repli si le modèle est indisponible) | **Gardée** hors du compagnon | — |
| Catalogue projeté des commandes (`catalogue_outils.py`) | **Retiré** de l'interface du modèle | 5 |
| Contexte court, ancre, question en attente | **Retirés**, remplacés par le fil complet | 5 |
| Règles de langage (`_demande_nouvelle`, `offre_une_action`, `refuse_la_question`…) | **Retirées** au fil des mesures | 5 |
| Texte réécrit par le code (relances, résumé de passage US-283) | **Retiré** : la réponse est celle du modèle | 5 |

L'ancien moteur reste en place derrière l'interrupteur `COMPAGNON_MOTEUR` **jusqu'au lot 5**.

## 7. Risques

| Risque | Parade | US |
|---|---|---|
| L'historique complet fait grossir les prompts | Fenêtre glissante, compaction, résultats tronqués ; cache (86 % mesuré) ; coût suivi par critère | US-343 |
| Un petit modèle raisonne mal sur des données brutes | Capacités à verdict : le code calcule, le modèle explique | US-339, 340 |
| Un texte de jardinier détourne le modèle | `avertissement_donnees` ; aucune écriture sans proposition validée et confirmée ; destruction au bouton seul | US-338, 344 |
| Régression pendant la migration | Interrupteur, ancien moteur conservé, jeu d'évaluation comme témoin | US-342, 347 |
| Le MCP et le compagnon divergent | Registre unique ; test de parité | US-338 |
| Particularités des fournisseurs (`top_p`, contenu en liste) | Passerelle corrigée, un test par fournisseur | US-350 |
| Le jeu d'évaluation devient une cible de réglage | Un tiers des cas renouvelable, tenu hors des prompts, contrôle automatique | US-336 |

## 8. Arbitrages encore ouverts (§9 de l'architecture)

| # | Question | Proposition de l'architecture | Bloque |
|---|---|---|---|
| A1 | Cette révision remplace-t-elle le §12 de l'ancien document ? | Oui, avec renvoi dans l'en-tête de l'ancien document | US-347 |
| A2 | Conseil général hors corpus ? | Oui, signalé « ne vient pas de l'application », jamais de dose ni de traitement | US-341, 342 |
| A3 | Durée du fil | 12 tours complets, compaction au-delà ; reprise possible le lendemain | US-343 |
| A4 | Modèle de référence | Small 4, à reconfirmer sur le jeu | US-342 |
| A5 | Parseur de gestes déterministe devant la boucle | Gardé tant qu'il bat la boucle à la mesure | US-347 |
| A6 | Ordre des canaux | PWA d'abord (lot 2), Telegram au lot 4 | US-346 |
| A7 | Les US 281 à 287 en cours sur l'ancien moteur | Les terminer seulement si elles servent le lot 0 ou la sécurité de l'écriture ; sinon, geler | US-347 |
