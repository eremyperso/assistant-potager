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
| [ARTICULATION_COMPAGNON_AGENT_INTERPRETEUR.md](ARTICULATION_COMPAGNON_AGENT_INTERPRETEUR.md) | Cartographie des composants réutilisables, limites du périmètre actuel, comparaison des options A, B et C, conséquences des US-236 à US-238, garanties à conserver (validation, confirmation, potager actif, cloisonnement des potagers), stratégie de modèles, schéma cible et recommandation |

## Ce qui est décidé, et ce qui reste à arbitrer

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
