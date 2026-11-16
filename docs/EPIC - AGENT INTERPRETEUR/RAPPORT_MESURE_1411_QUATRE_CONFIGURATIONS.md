# Mesure du 14/11/2026 : un dialogue réel, quatre configurations

> **Objet** : comprendre pourquoi le compagnon répond à côté sur une demande simple, en séparant ce qui vient du
> **modèle**, des **outils**, de la **mémoire de conversation** et du **savoir**.
> **Accord** : mesure sur le vrai modèle autorisée le 14/11/2026, un seul passage par configuration, clé de mesure
> `MISTRAL_API_KEY_MESURE`. Aucune écriture dans le potager, seulement les lignes `conso_tokens`.
> **Suite** : [ARCHITECTURE_COMPAGNON_CAPACITES.md](ARCHITECTURE_COMPAGNON_CAPACITES.md).

## 1. Le dialogue

C'est un compte neuf (potager 34, user 42), avec une seule parcelle, « planche légumes », 20 m², plein sud. Le
jardinier écrit au compagnon de la PWA le 14/11/2026 (`echanges_conversation` 441 à 447) :

1. « j'aimerai planter des salades »
2. « oui si tu veux »
3. « oui je veux bien »
4. « la planche légumes »
5. « demain »
6. « des salades »
7. « comment je plante des salades ? »

**Réponse attendue au tour 1** : la fiche Salade de la PWA l'affiche déjà, section « Maintenant ». Elle dit
« Rien à semer ni planter ce mois-ci. Prochaine fenêtre : semer en pépinière de février à mars », en zone
océanique, et que la salade n'est pas au potager.

**Ce qu'a vécu le jardinier le 14/11** : sept tours sans conseil ni proposition. Au tour 5, le compagnon lui
demande « quelle culture ? ». Au tour 7, il lui répond par un passage sur les jeunes plants de tomate.

## 2. Les quatre configurations

| # | Configuration | Comment elle a été jouée |
|---|---|---|
| A | **Chaîne actuelle, Small 4** (`mistral-small-2603`, modèle de production) | `tools/evaluer_dialogues.py --mode prioritaire --potager 34 --utilisateur 42` : vraie cascade, vrai prompt, catalogue projeté des commandes, contexte court et question en attente, données réelles en lecture seule |
| B | **Chaîne actuelle, Large 3** (`mistral-large-2512`) | Même outil. La passerelle a dû être contournée hors dépôt (voir §5) |
| C | **Small 4 + capacités + historique complet** | Prototype hors dépôt (environ 150 lignes) : les 9 lectures du registre MCP (`app/services/mcp/lectures.py`) appelées en Python sur le potager 34 dans une transaction annulée, `proposer_geste` simulé avec le schéma du MCP, la vraie passerelle, l'historique complet (résultats d'outils compris) et un prompt générique d'une quinzaine de lignes qui ne parle pas de salades |
| D | **Claude + MCP** | Sous-agent Claude sans contexte, avec le connecteur MCP du compte en lecture seule, les phrases envoyées une par une. **Autre potager** : « Potager de Bretagne » (id 11), le potager 34 n'étant pas visible depuis ce compte |

## 3. Résultats

| Critère | A. Small 4 actuel | B. Large 3 actuel | C. Small 4 + capacités | D. Claude + MCP |
|---|---|---|---|---|
| Verdict de saison au tour 1 | non | non | non (l'outil a répondu « indéterminé ») | **oui** (reconstitué depuis les fenêtres) |
| Intention gardée jusqu'au tour 7 | non, perdue au tour 2 | non | **oui** (salade, planche légumes, demain) | **oui** |
| Part vers une commande hors sujet | oui : `programmer_rappel` (×2) | oui : `modifier_parcelle` (×4) | **non** | **non** |
| Passage sur la tomate montré au jardinier | oui | oui, deux fois, recopié par le code | **non, écarté et signalé** | **non, écarté et signalé** |
| Rien d'inventé (parcelle, quantité) | oui | non : pépinière froide et voile proposés | oui | oui |
| Arrive à une proposition de geste | non | non | non (attend la variété, propose 10 plants par défaut) | non (attend la quantité) |
| Jetons d'entrée sur 7 tours | 108 894 (61 % en cache) | ≈ 158 000 | **51 211 (86 % en cache)** | n/a |
| Latence par tour | 0,6 à 3,0 s | 1,4 à 10,8 s | 0,9 à 3,3 s | n/a |

### Tours marquants

**A, Small 4 actuel**
- Tour 1 : « Je te propose de créer une nouvelle parcelle pour tes salades sur la planche légumes. Tu confirmes ?
  Source : Problèmes observables de la tomate. »
- Tour 6 : « Qu'est-ce que tu veux qu'on te rappelle précisément pour la planche légumes demain ? »

**B, Large 3 actuel**
- Tour 1 : le modèle interroge bien la connaissance (« quand et comment planter des salades en novembre, en
  climat océanique ? »). Le code affiche pourtant le passage sur la tomate.
- Tours 3 à 6 : `modifier_parcelle(est_pepiniere=true, type_pepiniere=froide, abri=voile)`, répété à chaque tour.
- Tour 7 : six `chercher_connaissance` d'affilée, puis le passage tomate recopié deux fois.

**C, Small 4 + capacités + historique**
- Tour 1 : il lit le stock, le calendrier (laitue, plantation) et le plan. Le calendrier rend « Aucun calendrier
  pour cette culture dans ta zone » (règle R1 `indetermine`). La réponse est maladroite : « Tu n'as plus de
  graines de laitue en stock. Veux-tu noter une perte… ? »
- Tours 4 à 6 : « D'accord, sur la planche légumes donc. » « Demain, c'est le 2026-11-15. » Il réclame la variété
  et la quantité, puis propose 10 plants par défaut.
- Tour 7 : « Je n'ai pas trouvé de passage sur la plantation des salades dans mes données. Voici un conseil
  général, mais pas issu de l'application… », puis « Tu veux que je t'aide à noter un geste de plantation pour
  demain sur la planche légumes ? »

**D, Claude + MCP**
- Tour 1 : « …on est mi-novembre et ton calendrier (zone océanique) ne donne aucune fenêtre pour la salade en ce
  moment. Les semis vont de février à mars en pépinière et de mars à mai en pleine terre… » Il propose la serre
  comme endroit le plus abrité.
- Tour 5 : il lit la météo du 15/11 (pluie légère, pas de gel) et en tire un conseil.
- Tour 7 : il signale qu'il n'y a pas de fiche salade, donne des gestes de base présentés comme une connaissance
  générale, et ajoute la durée de culture tirée du calendrier.
- Défaut : il repose ses trois questions à chaque tour au lieu de proposer une valeur par défaut.

## 4. Ce que la mesure établit

1. **La taille du modèle n'est pas le goulot.** Large 3, branché sur la chaîne actuelle, dérive comme Small 4. Ils
   se rabattent chacun sur la commande la plus proche faute de capacité qui corresponde au besoin : Small 4 sur le
   rappel, Large 3 sur la parcelle.
2. **Le même petit modèle, avec des capacités et l'historique complet, tient le fil**, n'invente rien, écarte le
   hors-sujet, et coûte deux fois moins de jetons grâce au cache.
3. **Une capacité doit rendre un verdict, pas des données à interpréter.** Small 4 n'a pas tiré la saison des
   fenêtres brutes, Claude oui. `voir_calendrier` interroge une seule action et rend « indéterminé » là où la fiche
   PWA rend « rien ce mois-ci, prochaine fenêtre février à mars ».
4. **Le code qui réécrit la réponse du modèle aggrave l'erreur.** Le passage tomate affiché en A et B vient du
   texte recopié par `savoir.chercher_connaissance` (US-283), pas du modèle.
5. **Le savoir manque dans toutes les configurations.** Les 20 fiches agronomiques couvrent 10 cultures ; la
   salade et la laitue n'y sont pas.

**Limites.** Un seul dialogue, un seul passage, et le modèle ne rend pas toujours la même chose (le 14/11, Small 4
avait proposé `/calendrier salade` au tour 1). Le prompt de C a été écrit après l'analyse : il est générique,
mais une phrase en vient (« un passage qui parle d'une autre culture ne répond pas »). D joue sur un autre
potager et mélange trois avantages : un modèle plus fort, de meilleures capacités et l'historique. Ces résultats
indiquent une direction, ils ne la valident pas : la validation passe par le jeu d'évaluation du document
d'architecture (§7).

## 5. Anomalies rencontrées, non corrigées

| Anomalie | Effet | Où |
|---|---|---|
| La passerelle n'envoie pas `top_p=1` avec `temperature=0` | Mistral Large 3 répond 400 `invalid_request_greedy_sampling` ; l'agent part en « indisponible » | `llm/passerelle.py`, construction des `kwargs` de `appeler_chat_outils` |
| La passerelle suppose un `content` texte | Mistral Large 4 (`mistral-large-latest`) renvoie une liste ; `AttributeError` sur `.strip()` | `llm/passerelle.py`, `appeler_chat_outils` |
| `voir_calendrier` rend une confiance par action | « indéterminé » pour une plantation sans fenêtre, au lieu du verdict de la fiche culture | `app/services/mcp/lectures.py::_voir_calendrier` |
| Une consultation sort comme proposition | `/calendrier salade` mis en attente, jamais affiché dans la PWA (échange 441) | `contexte_court.resume_de`, `echange_pwa` |

## 6. Coût de la mesure

Configurations A et B : moins de 0,10 $. Configuration C : 51 211 jetons d'entrée, moins de 0,01 $.
Configuration D : jouée dans la session de développement, sans appel facturé à Mistral.
