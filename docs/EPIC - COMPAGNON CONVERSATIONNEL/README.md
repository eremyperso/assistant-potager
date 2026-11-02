# Dossier d'étude : le compagnon conversationnel

> **Ouvert le** 21/10/2026. **Statut** : étude, aucune US créée, aucun code modifié.

## Objet

Donner à l'Assistant Potager un interlocuteur unique, à la fois dans la PWA (un
panneau de conversation) et dans Telegram (le bot actuel), **sans construire un
second moteur** à côté de l'agent interpréteur de l'épic 13.

## Référence d'interface

Les captures fournies le 21/10/2026 (« Gleba ») montrent ceci :

- un bouton flottant qui ouvre un panneau ancré en bas à droite ;
- dans l'en-tête du panneau : nouvelle conversation, historique des
  conversations, « Agrandir » et fermeture ;
- trois modes au choix :
  - **Normal** ;
  - **Support** ;
  - **Extra** : « Analyse croisée météo, sols, cultures, verger et
    comptabilité, sans modifier tes données ».

  En mode Extra, la réponse passe d'abord par un état d'attente explicite
  (« Analyse approfondie de l'exploitation… »).

Ces captures servent de référence d'usage, pas de maquette à reproduire.

## Documents

| Document | Contenu |
|---|---|
| [ANALYSE_MESURE_AGENT_D_ABORD.md](ANALYSE_MESURE_AGENT_D_ABORD.md) | **Analyse du 02/11/2026** : mesure de l'agent d'abord sur 43 tours réels du potager 33 (8B, 14B, Small 4) ; décision D14 (l'agent comprend, le code garde ; Mistral Small 4) ; causes communes aux trois modèles ; US-280 à US-287 et seuils de bascule. Rapports bruts : [base actuelle](RAPPORT_MESURE_ACTIF_terrain_compagnon_2026_11.md), [agent d'abord, terrain](RAPPORT_MESURE_PRIORITAIRE_terrain_compagnon_2026_11.md), [agent d'abord, corpus US-256](RAPPORT_MESURE_PRIORITAIRE_us256_dialogues.md) |
| [CADRAGE_COMPAGNON_ACTIF.md](CADRAGE_COMPAGNON_ACTIF.md) | **Cadrage du 27/10/2026, révisé le 02/11** (§4.5, D14, §6.6) : décisions D1 à D4 et D11 (Mistral payant avec Ministral 3B en référence, proactivité complète, confirmation dans la PWA, prénom et registre, Telegram canal des notifications avec une proposition traitable dans les deux canaux), dialogues cibles, profil d'échange et carnet, quatre mémoires, veilleur et distributeur, règles R7 à R10, découpage US-254 à US-272 (US-273 facultative) et critères de mesure |
| [25-10-2026 analyse.md](25-10-2026%20analyse.md) | Note de reprise du 25/10 : objectif d'un vrai dialogue, défauts constatés, points de vigilance |
| [ARTICULATION_COMPAGNON_AGENT_INTERPRETEUR.md](ARTICULATION_COMPAGNON_AGENT_INTERPRETEUR.md) | Cartographie des composants réutilisables, limites du périmètre actuel, comparaison des options A, B et C, conséquences des US-236 à US-238, garanties à conserver (validation, confirmation, potager actif, cloisonnement des potagers), stratégie de modèles, schéma cible et recommandation |

## Ce qui est décidé, et ce qui reste à arbitrer

**Décidé le 02/11/2026 (D14)** : l'agent d'abord. Toute phrase libre va à l'agent,
qui voit tout le catalogue ; les garde-fous passent après le modèle, dans le validateur ;
Mistral Small 4 en référence. Le bot reste en `AGENT_MODE=actif` jusqu'à US-287.

Écrit pour : une autre session Claude Code qui implémente l'agent d'abord, sans le contexte de cette conversation. Tu peux copier ce qui suit.

---

## Mode `AGENT_MODE=prioritaire` : objectif et ordre d'implémentation

**Objectif.** Le jardinier parle avec ses mots, sans tournure guidée, et aucun mot-clé ne détourne sa phrase vers la documentation. Toute phrase libre va à l'agent. Il voit tout le catalogue d'outils (écritures, lectures, `consulter_donnees`, `chercher_connaissance`, météo, annulation) et rend le même service pour toutes les opérations du potager.

**Principe (décision D14, 02/11/2026).** Le modèle comprend, le code garde. Les faits sont préchargés, les dates calculées par le code, et les garde-fous passent **après** le modèle, dans le validateur. Le modèle de référence est Mistral Small 4 (`mistral/mistral-small-2603`). Les règles actuelles (mode `actif`) restent le mode dégradé si Mistral tombe.

**État au 02/11/2026 (rien n'est commité).**
- Le mode existe : `app/config.py`, `_l_agent_d_abord` dans `app/services/interpreteur_commandes.py`, `interpreteur_agent.proposer(prioritaire=True)` et `PROMPT_FIXE_PRIORITAIRE`.
- Il n'a servi qu'aux mesures. `.env.dev` reste en `actif` sur ministral-8b. **Ne pas activer `prioritaire` dans le bot avant US-287.**
- La mesure sur 43 tours réels (potager 33) donne 25 réponses justes sur 43 pour Small 4, dont 6 sur 16 aux questions.
- Il y a une régression de sécurité : sur les trois modèles, une question comme « est-ce que je peux supprimer… » produit une carte de suppression.
- Les trois modèles échouent sur les mêmes tours. Les corrections sont donc dans le code, pas dans le choix du modèle.

**Documents à lire d'abord.** [ANALYSE_MESURE_AGENT_D_ABORD.md](docs/EPIC%20-%20COMPAGNON%20CONVERSATIONNEL/ANALYSE_MESURE_AGENT_D_ABORD.md) et le cadrage [CADRAGE_COMPAGNON_ACTIF.md](docs/EPIC%20-%20COMPAGNON%20CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md) (D14, §4.5, §6.6). Les US sont dans `backlog/US-280_…` à `US-287_…`. Chaque fichier donne son modèle et son effort conseillés.

**Ordre conseillé (une US par session, `/clear` entre deux).**

0. **Préalable : stabiliser les lots 1 à 5 déjà codés.** Commit sur accord, puis migrations v61 à v66 sur PostgreSQL de dev. D'après la mémoire du projet, v66 n'est pas jouée et casse le bot : à vérifier. Le reliquat d'US-260 (« non 4 rangs » → abandon de la proposition) est une garde de validation, à traiter dans US-281.
1. **US-280 (3 pts)** : donner à chaque question du corpus de mesure son texte attendu (CA6). Sans cela, le taux « bon outil » surestime les questions.
2. **US-281 (5 pts)** : garde-fous après le modèle. Une question ne produit jamais d'écriture, pas de devinette, pas de recréation d'une parcelle existante.
3. **US-282 (3 pts)** : un seul outil météo, pour ici ou ailleurs, passé ou prévision.
4. **US-283 (5 pts)** : la recherche de l'agent sépare l'application et le jardinage, avec un seuil de pertinence. Elle retire aussi les documents « Assistant Automobile » trouvés dans `knowledge_documents` en dev.
5. **Remesure** des deux corpus (terrain et US-256) sur Small 4.
6. **US-285 (3 pts)** : habitudes, objectifs et gestes distingués, plus une garde contre la grossièreté.
7. **US-284 (5 pts)** : la question posée par le compagnon reste en attente, pour qu'une réponse d'un mot (« la 259 », « oui ») suffise.
8. **US-286 (5 pts, épic 14)** : l'agent voit ce que le bot a envoyé de lui-même (relances, purges, rappels).
9. **US-287 (5 pts)** : bascule. Remesure finale, puis dev, puis prod après une semaine sans couperet au journal. Elle traite aussi les raccourcis à mots-clés de `app/bot/messages.py` qui passent avant l'interpréteur (annuler, godets, déplacer, note).
10. **Ensuite** le lot 6 (US-270 → 271 → 272, la PWA), puis le lot 7. La PWA doit se brancher sur le moteur définitif. **US-269** peut avancer en parallèle, à tout moment.

**Seuils pour livrer US-287** (remesure sur Small 4) :
- 0 suppression proposée sans demande ;
- 0 écriture proposée sur une question ;
- au moins 90 % de réponses justes aux questions ;
- au moins 90 % de bon outil sur les commandes ;
- p95 de 4 s au plus.

**Règles à respecter.**
- Réponses en français ; aucun commit ni push sans accord explicite.
- **Aucune mesure sur le vrai modèle sans accord explicite** : un seul passage, volume annoncé avant. Utiliser `tools/evaluer_dialogues.py --mode prioritaire --corpus … --potager … --utilisateur …` avec la clé `MISTRAL_API_KEY_MESURE`.
- Ne pas déclarer une US « livrée » sur des tests à modèle simulé.
- Tout changement de comportement met à jour les fiches de `data/connaissance/doc_app/`, et `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.
- Pas de `db.query` hors `app/services/`, et tout appel modèle passe par `llm.passerelle`.
- Trois échecs de tests ne viennent pas de ce chantier : `test_us237` ca7, `test_us250` ca6, `test_us276` ca5.
- Les tickets Jira PIA des US-280 à 287 ne sont pas créés. Toute PR doit se terminer par la section « Jira US », avec les clés trouvées via Jira, jamais inventées.

---


**Recommandé, pas encore décidé :**

- un orchestrateur commun, écrit en code déterministe et sans appel au modèle ;
- l'agent interpréteur choisit le traitement en mode Normal ;
- l'analyse du mode Extra est en lecture seule par construction ;
- six règles vérifiables empêchent deux moteurs concurrents (document principal,
  §14.2).

**À arbitrer** : les points C1 à C7 du document principal (§14.5), en
particulier la saisie des gestes depuis la PWA (maintien ou non de l'arbitrage
A16 des épics 9 à 12).

## Documents liés

- [Architecture de l'agent interpréteur](../EPIC%20-%20AGENT%20INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md) et ses rapports de mesure (US-233, US-235)
- [Épic 7 : BYOK](../Epic%207%20-%20BYOK%20%20LLM%20du%20potager/epic-7-byok-cle-personnelle.md) : un modèle par potager (US-186 / CA3), aucun repli silencieux (US-191)
- [Plan des épics 9 à 12](../EPIC%209-12%20-%20PLAN%20CULTURES%20PEPINIERE/PLAN_EPICS_9_A_12.md), arbitrage A16
- `docs/domaines/commandes-bot.md` : le pilotage du bot par une phrase
