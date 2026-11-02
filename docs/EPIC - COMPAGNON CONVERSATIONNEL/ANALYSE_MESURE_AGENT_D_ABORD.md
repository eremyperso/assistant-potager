# L'agent d'abord : ce que dit la mesure du 01/11/2026

> **Statut** : analyse du 02/11/2026, après trois passages de `tools/evaluer_dialogues.py`
> le 01/11 au soir (coût réel : 0,29 $). **Décision du porteur du produit (D14)** :
> l'agent d'abord devient la cible, avec Mistral Small 4 en référence et les garde-fous
> déplacés après le modèle. Le bot reste en `AGENT_MODE=actif` jusqu'à US-287.
> **Révise** : le §4.5 de [CADRAGE_COMPAGNON_ACTIF.md](CADRAGE_COMPAGNON_ACTIF.md).
> **Rapports bruts** :
> [base actuelle](RAPPORT_MESURE_ACTIF_terrain_compagnon_2026_11.md) ·
> [agent d'abord, terrain](RAPPORT_MESURE_PRIORITAIRE_terrain_compagnon_2026_11.md) ·
> [agent d'abord, corpus US-256](RAPPORT_MESURE_PRIORITAIRE_us256_dialogues.md).
> **US** : US-280 à US-287 (§7).

---

## 0. L'essentiel

**Le constat de départ.** En usage réel, le compagnon répond mal dès qu'on sort des
tournures prévues. Le jardinier a envisagé de passer par un serveur MCP et un LLM
externe. L'analyse a écarté cette piste comme remède : MCP ne change pas la qualité,
ne permet pas l'initiative (veilleur, rappels) et pose le problème du multi-utilisateur.
Le vrai défaut est ailleurs : **le code décide avant le modèle**, sur des listes de mots.

**Ce que la mesure confirme.** En mode `prioritaire`, toutes les phrases réelles vont
au modèle, et aucune n'est plus déviée vers un passage de documentation. Les commandes
en langage libre passent : phrases dictées, polies, composées, corrections.

**Ce qu'elle infirme.** L'agent d'abord n'est pas encore fiable. Sur Small 4, une lecture
tour par tour donne **25 réponses justes sur 43** (6 sur 16 aux questions), loin des 81 %
affichés par le taux « bon outil ». Surtout, **les trois modèles échouent sur les mêmes
tours** : la plupart des défauts viennent des outils et du contexte, pas de la taille du
modèle.

**La décision.**

1. L'agent comprend toutes les phrases libres. Le code ne filtre plus avant l'appel : il
   **valide après**.
2. **Mistral Small 4** (`mistral-small-2603`) devient la référence : même justesse que le
   8B et le 14B, 3 à 4 fois plus rapide, et le moins cher grâce au cache.
3. Cinq corrections dans le code, puis une remesure, avant de basculer le bot.

---

## 1. D'où vient le diagnostic : les traces réelles

229 échanges du potager 33 (« Potager de recette ») du 28/10 au 01/11/2026, dans
`echanges_conversation` et `routage_logs` :

| Défaut | Nombre | Exemple réel |
|---|---:|---|
| Phrase partie à la cascade des questions sans passer par l'agent | 39 | « Est-ce que tu peux renommer parcelle, tunnel ? » |
| Question sur ses propres données, réponse tirée de la documentation de l'application | ≈ 8 | « c'est quoi la dernière action notée », « quelle météo à Lyon », « quel est la date », « rappelle-moi mon objectif » |
| Confirmation demandée en texte, sans proposition à confirmer | 7 | « Je vais effacer le dernier geste… tu veux vraiment ? » |
| « oui » suivi d'un « Salut… ! » au lieu d'une action | 10 | « oui » → « Salut, potager ! » |
| « Je n'ai pas bien compris » | 4 | « Ouvre moi mon carnet » |

Les deux défauts du milieu s'enchaînent : une promesse en texte ne crée aucune carte, donc
le « oui » ne confirme rien et le modèle repart de zéro. Aucune mesure antérieure ne voyait
ce défaut. Le prompt l'encourageait même : `CONSIGNE_SAVOIR` disait « tu peux proposer de
noter (« tu veux que je le note ? ») ».

---

## 2. Ce qui a été mesuré

| Brique | Ce qu'elle fait |
|---|---|
| `AGENT_MODE=prioritaire` | `_l_agent_d_abord` envoie toute phrase libre à l'agent avant les règles. Catalogue complet, outils de savoir, `PROMPT_FIXE_PRIORITAIRE`. Les règles servent de mode dégradé si l'agent est indisponible |
| `PROMPT_FIXE_PRIORITAIRE` | Douze consignes, écrites avant la mesure. Les questions reviennent à l'agent ; jamais de confirmation en texte ; pas de salut en pleine conversation ; une réponse courte reprend la demande d'origine |
| Corpus de terrain | `tests/corpus/terrain_compagnon_2026_11.json` : 35 dialogues réels (43 tours), rejoués sur les **vraies données** du potager 33, en lecture seule |
| Deux couperets nouveaux | « confirmation sans proposition », « salut en plein dialogue » |

Trois passages :

1. la cascade actuelle sur le corpus de terrain (8B) ;
2. l'agent d'abord sur le corpus de terrain (8B, 14B, Small 4) ;
3. l'agent d'abord sur le corpus d'US-256 (mêmes modèles, potager fictif).

---

## 3. Résultats chiffrés

| | Cascade actuelle (8B) | Agent d'abord 8B | 14B | Small 4 |
|---|---:|---:|---:|---:|
| Tours confiés à l'agent (terrain) | 19 / 43 | 43 / 43 | 43 / 43 | 43 / 43 |
| « Bon outil » (terrain) | 16/19 | 35/43 | 35/43 | 35/43 |
| « Bon outil » (corpus US-256) | — | 31/44 | 29/44 | 33/44 |
| p95 de latence (terrain) | 3,1 s | 8,6 s | 10,5 s | **2,6 s** |
| Jetons d'entrée par message | 3 900 | 13 800 | 12 500 | 11 600 |
| Coût réel des trois passages | — | 0,094 $ | 0,148 $ | **0,044 $** |

Small 4 est le moins cher : 84 % de son entrée a été servie en cache (0,015 $ le million).
Le coût d'usage reste faible : à 50 messages par jour, environ 3 $ par mois au plus, cache
non déduit.

**Pourquoi la cascade actuelle semble meilleure (16/19).** Elle ne confie au modèle que les
phrases faciles. Les 24 autres partent aux règles ou à la cascade des questions, dont la
mesure ne juge pas les réponses. Ce que ces réponses valaient, ce sont les traces du §1.

**Pourquoi « bon outil » surestime l'agent d'abord.** Une réponse en texte est acceptée sur
une question, même quand elle est fausse. La lecture tour par tour (§4) corrige ce biais.
US-280 ajoute au corpus le texte attendu, pour que la prochaine mesure le juge seule.

---

## 4. Lecture tour par tour (Small 4, corpus de terrain)

**Questions : 6 justes sur 16.**

| Phrase | Réponse | Verdict | Cause |
|---|---|---|---|
| « quel est mon dernier semis ? » | « le 29 octobre, des radis, 8 graines » | ✅ | |
| « quel est la date ? » | « Le 2 novembre 2026 » | ✅ | |
| « que sais-tu sur moi ? » | carnet et objectifs au complet | ✅ | |
| « quand dois-je arroser mes tomates ? » | croise la pluie du jour et « tes arrosages du soir » | ✅ | |
| « Quelle météo sur Lyon ? », « et demain ? » | la pluie **du potager**, présentée pour Lyon | ❌ | outil `meteo` limité à l'historique du potager |
| « quel météo en Belgique ? » | la météo du potager, présentée comme celle de la Belgique | ❌ | idem |
| « pour mon objectif d'autonomie, que privilégier ? » | un passage sur le plan d'occupation, recopié | ❌ | `chercher_connaissance` mêle doc de l'application et agronomie |
| « semer des tomates ce week-end ? » | un passage sur les plants étiolés | ❌ | passage hors sujet |
| « liste ce que j'ai fait aujourd'hui » | des arrosages inventés à partir des habitudes du carnet | ❌ | habitudes et gestes mal distingués |
| « c'est quoi la dernière action notée » | la mauvaise action | ❌ | à vérifier : ordre ou présentation des actions menées |
| « rappelle-moi mon objectif cette année » | l'objectif 2027, et une proposition d'écriture | ❌ | objectifs non datés |
| « quels sont mes notes ? » | ouvre la saisie d'une note | ❌ | |

**Commandes et dialogues : 19 justes sur 27.** Créations multiples, renommage poli,
pépinières, sol, « non 4 rangs », geste au passé et conversation tiennent. Échecs :

- « Supprime la planche » → « laquelle ? » → « la planche test » → il **redemande** au lieu
  de proposer. Les trois modèles font de même ;
- « Oui je veux bien » après un rappel proposé → mauvais identifiant de proposition ;
- « vide le geste » → envoyé au parseur de gestes, puis « Ah, merde… » (registre gouailleur) ;
- « ma serre est une pépinière tiède » → « chaude » inventé ;
- quatre créations dictées, dont « Est » qui existe déjà → une recréation proposée.

**Corpus US-256 : une régression de sécurité.** À « est-ce que je peux supprimer la planche
sud sans perdre mon historique ? », **les trois modèles proposent une carte de suppression**.
Rien n'est exécuté sans le clic, mais c'est inacceptable. En mode `actif`, la projection
« question → aucune écriture » (US-276) l'empêchait. S'y ajoutent des devinettes :
« renomme la planche sud » sans nouveau nom, « enlève la serre » → désactivation.

---

## 5. Les causes, et pourquoi un plus gros modèle n'y suffit pas

| Cause | Tours touchés | Commun aux 3 modèles ? | Correction |
|---|---|---|---|
| Plus aucun garde-fou entre une question et une écriture | suppression sur une question, devinettes | oui | **US-281** : les garde-fous après le modèle, dans le validateur |
| Deux chemins météo, le bon caché dans `afficher` | Lyon, Belgique, demain | oui | **US-282** : un seul outil météo, lieu et prévision |
| Connaissance mêlée et peu pertinente | autonomie, week-end, objectif connu | oui | **US-283** : séparer application et jardinage, seuil de pertinence, synthèse |
| La question posée par l'agent n'est pas un état | « la planche test » | oui | **US-284** : la question en attente |
| Habitudes, objectifs et gestes mal distingués ; aucune garde de registre | gestes inventés, objectif 2027, « merde » | en partie | **US-285** |
| L'agent ignore ce que le bot a envoyé seul | « vide le geste » après une purge | oui | **US-286** |

Le 14B n'apporte rien de mesurable sur le 8B. Small 4 fait aussi bien, plus vite et moins
cher. La montée de modèle n'est pas le levier.

---

## 6. Ce que la mesure change au cadrage

Le §4.5 du cadrage posait : « le code pense, le modèle choisit et parle ». Pour qu'un petit
modèle tienne, le code décidait **avant** l'appel : règles, garde de savoir, filtre de
gestes, outils retirés selon les mots. Chacune de ces décisions est un piège à mots-clés.
La mesure d'US-256 (52 % sur le 3B) et celle-ci montrent que ce pari ne tient pas.

La règle devient :

> **Le modèle comprend, le code garde.** Toute phrase libre va au modèle, qui voit tout le
> catalogue. Le code ne retire rien avant l'appel. Il précharge les faits, calcule les
> dates et valide **après** : une question ne produit jamais d'écriture, une valeur non dite
> n'est jamais acceptée, une suppression exige le nom dit et le clic. Le veilleur reste
> sans modèle (R7).

Ce qui ne change pas : le modèle propose, le code valide, le jardinier confirme, le code
exécute. Un seul moteur de compréhension (R1), un seul chemin d'écriture (R2).

---

## 7. Découpage en US

| US | Titre | Effort | Dépend de |
|---|---|---:|---|
| [US-280](../../backlog/US-280_mesurer-agent-d-abord-dialogues-reels.md) | Mesurer l'agent d'abord sur des dialogues réels | 3 | *(réalisée le 01/11, reste le CA du texte attendu)* |
| [US-281](../../backlog/US-281_garde-fous-apres-le-modele.md) | Garder les garde-fous après le modèle, dans le validateur | 5 | US-280 |
| [US-282](../../backlog/US-282_un-seul-outil-meteo.md) | Un seul outil météo pour l'agent : ici ou ailleurs, passé ou prévision | 3 | US-280 |
| [US-283](../../backlog/US-283_connaissance-application-et-jardinage.md) | Séparer, dans la recherche de l'agent, l'application et le jardinage | 5 | US-280 |
| [US-284](../../backlog/US-284_question-en-attente.md) | Garder en attente la question que pose le compagnon | 5 | US-281 |
| [US-285](../../backlog/US-285_habitudes-gestes-registre.md) | Distinguer habitudes, objectifs et gestes notés, et garder le registre | 3 | US-280 |
| [US-286](../../backlog/US-286_agent-voit-messages-envoyes.md) | Montrer à l'agent ce que le bot a envoyé de lui-même | 5 | US-280 |
| [US-287](../../backlog/US-287_basculer-agent-d-abord.md) | Basculer le bot en agent d'abord sur Mistral Small 4 | 5 | US-281 à US-286 |

**Ordre conseillé.** US-280, puis US-281 (sécurité), US-282 et US-283 (les erreurs les plus
visibles), US-285, US-284, US-286, et enfin US-287. Une remesure sur Small 4 après chaque
US, en un seul passage et avec l'accord du jardinier-développeur.

**Seuils de bascule (US-287)**, sur les deux corpus, avec Small 4 :

- 0 suppression proposée au jardinier sans demande, 0 écriture proposée sur une question ;
- au moins 90 % de réponses justes aux questions, jugées sur le texte attendu (US-280) ;
- au moins 90 % de bon outil sur les commandes ;
- p95 de latence de 4 s au plus.

---

## 8. Risques

| Risque | Parade |
|---|---|
| Plus de jetons par message (×3 : 11 600 contre 3 900) | Cache de prompt (84 % mesuré sur Small 4) ; préfixe stable ; coût suivi dans `conso_tokens` |
| Panne ou quota Mistral | Mode dégradé : les règles d'aujourd'hui (`_l_agent_d_abord` rend la main) |
| Clé personnelle (BYOK) avec un modèle faible | Le mode dégradé s'applique ; le compagnon le dit, sans basculer en silence (US-191) |
| Le corpus de terrain vieillit avec les données du potager 33 | Les dialogues citent leur échange d'origine ; une parcelle disparue s'adapte, la source le dit |
| Une correction de prompt « pour faire passer » le corpus | Interdit : toute retouche du prompt se fait avant une mesure, jamais pendant |
