# US-235 — Évaluation de l'agent interpréteur sur le corpus US-172 enrichi

*Généré par `tools/evaluer_interpreteur_agent.py` le 2026-10-21, modèle `openai/gpt-oss-120b`.*

## Couperets (CA15)

| Couperet | Résultat | Verdict |
|---|---:|---|
| Exécutions destructrices erronées | 0 | ✅ |
| Régressions sur les phrases reconnues par les règles | 0 | ✅ |

**Verdict : les deux couperets passent.** Le passage de `ombre` à `actif` reste un réglage, décidé sur ce rapport et sur le journal d'observation (`routage_logs`, `issue_interpretation = 'ombre'`).

## Chemin des phrases

| Chemin | Phrases |
|---|---:|
| regle | 173 |
| filtre | 56 |
| agent | 31 |
| indisponible | 0 |

## Justesse des propositions de l'agent, par registre

*Juste* : la commande attendue (et, pour une modification, exactement les champs attendus) ; pour une question ou une phrase hors périmètre, aucune commande qui écrit ; pour une phrase incomplète, rien d'exécutable sans précision.

| Source | Registre | Juste |
|---|---|---:|
| us172 | hors_perimetre | 11/11 (100 %) |
| us235 | declaration | 4/4 (100 %) |
| us235 | destructrice | 2/2 (100 %) |
| us235 | hors_perimetre | 2/2 (100 %) |
| us235 | incomplet | 2/2 (100 %) |
| us235 | negation | 6/6 (100 %) |
| us235 | question | 4/4 (100 %) |
| **total** | | **31/31 (100 %)** |

Phrases du corpus US-235 captées par les règles avant l'agent : 2/4 (50 %) lues correctement.

## Coût

- Appels à l'agent : 31 ; 429 rencontrés (attendus puis rejoués) : 2
- Latence : p50 291 ms, p95 2218 ms
- Jetons par appel : 3067 en moyenne

## Phrases à relire

| Phrase | Attendu | Obtenu | Outils |
|---|---|---|---|
| retire le paillage de la planche sud | parcelle modifier `paillage=non` | `rien` | - |
| la planche sud n'est plus paillée | parcelle modifier `paillage=non` | `/parcelle modifier planche sud n'est plus paillage=oui` | - |
| le tunnel n'est plus utilisé | parcelle modifier `actif=non` | `rien` | - |
| la planche sud est à l'ombre toute la journée | parcelle modifier `ensoleillement=ombre` | `/culture exposition planche sud ombre` | - |
| paille la planche nord | parcelle modifier `paillage=oui` | `rien` | - |

## Lecture et décision

*Écrite à la main le 21/10/2026, après quatre passages complets du même modèle. Le tableau ci-dessus est le quatrième. Entre deux passages, seul l'outil de mesure a changé (jugement des phrases captées par les règles, résolution des noms comme le fait le bot) : le code de l'agent, son prompt et son catalogue n'ont pas bougé. Les quatre passages donnent la même justesse pour l'agent, 31 sur 31.*

### Ce que la mesure établit

- **Les deux couperets du CA15 passent.** Aucune commande destructrice exécutable n'est proposée à tort. Les 173 phrases reconnues par les règles rendent exactement la même commande en `AGENT_MODE=actif` : les règles passent avant l'agent, et c'est vérifié phrase par phrase.
- **Les négations sont comprises sans règle.** « Ma serre extérieure n'est plus une pépinière », « ne fait plus office de pépinière », « arrête la pépinière dans la serre extérieure », « n'est plus sous tunnel » et « enlève l'abri » donnent la bonne modification, avec la valeur déduite (`pepiniere=non`, `abri=aucun`).
- **Le défaut relevé par US-233 est corrigé.** « renomme la planche nord » ne propose plus `Planche Nord → Planche Nord`. À chaque passage, le modèle a demandé une précision. S'il recopie l'ancien nom, le validateur retire la copie et la complétion demande le nouveau nom (test unitaire).
- **Aucune question ne devient une écriture.** Les 4 questions piégeuses (« la serre extérieure est-elle une pépinière ? »), « modifie ma serre », les 2 phrases hors catalogue et les 11 phrases hors périmètre du corpus US-172 qui atteignent l'agent (questions sur les données, observations) ne donnent aucune commande : l'agent les aiguille.

### Ce que la mesure ne règle pas

| Constat | Conséquence | Suite |
|---|---|---|
| « retire le paillage de la planche sud », « paille la planche nord », « le tunnel n'est plus utilisé » n'atteignent jamais l'agent : le filtre « geste annoncé » (`llm.routeur.annonce_un_geste`) les capte avant lui, parce qu'ils s'ouvrent sur un mot de geste (paillage, tunnel) | La première phrase est citée dans la Story. Elle continue de suivre le chemin des gestes, comme avant cette US | US-236, qui revoit l'ordre entre les filtres et les déclarations (§2.6). Un filtre plus fin serait une nouvelle règle de tournure, ce que A3 exclut |
| « la planche sud n'est plus paillée » est lue `paillage=oui` sur une parcelle nommée « planche sud n'est plus » ; « la planche sud est à l'ombre toute la journée » devient l'exposition d'une **culture** « planche sud » | Deux défauts des **règles d'US-172**, antérieurs à cette US : ces phrases n'atteignent jamais l'agent, les règles passent avant lui. Le récapitulatif les montre avant toute écriture (et le nom inexact déclenche une proposition de voisin), mais la proposition est fausse | À corriger dans les règles (correction d'une lecture fausse, pas une tournure de plus), ou à retirer des règles pour laisser l'agent les lire. Décision à prendre, hors de cette US |
| « le tunnel n'est plus utilisé », même si elle atteignait l'agent : « utilisé » n'évoque pas le champ `actif` (libellé « en service ») | L'ancrage du champ (CA6) retirerait `actif=non`, et la complétion demanderait quoi modifier | Limite assumée de la règle 9 : aucune liste de tournures. À suivre dans le journal d'observation |
| 3 067 jetons par appel pour les 13 outils générés, contre 977 pour les 10 outils provisoires d'US-233 | Le catalogue complet triple le préfixe. L'estimation de l'architecture (2 à 3 000 jetons, §3.8) était juste pour le catalogue complet | Le préfixe est fixe et donc cacheable. 31 appels en rafale ont déclenché de 2 à 18 refus 429 par passage sur le quota gratuit, tous rejoués |
| En `ombre`, une phrase qui atteint le repli coûte deux appels : l'ancien repli, qui répond, et l'agent, qui est observé | Coût doublé sur ces phrases pendant l'observation, sans latence de plus pour le jardinier (l'observation tourne à côté) | Durée d'observation à borner |
| Corpus US-235 de 27 phrases, écrites pour la mesure | Une phrase pèse près de 4 points dans son registre | La matière du passage en `actif` est le journal : `routage_logs` où `issue_interpretation = 'ombre'` |

### Décision proposée

**Livrer en `AGENT_MODE=ombre`.** Le code garde `off` par défaut : le mode se règle dans `.env.dev` puis `.env.prod`, sans redéploiement de code. Passer en `actif` après une période d'observation, sur la lecture du journal, en comparant ce que l'agent aurait proposé à ce que le jardinier a réellement fait. Cette décision appartient au responsable du produit.

### Écritures en base

Chaque passage a écrit une ligne `conso_tokens` (`appel_type = 'agent'`, potager 1) par appel dans la base de `.env.dev`, soit au moins 124 lignes pour les quatre passages (une par appel abouti). C'est la preuve que la mesure passe par le chemin réel de la passerelle. Aucune ligne `routage_logs` n'a été écrite : la mesure appelle l'interpréteur, pas le bot.

### Relancer la mesure

```bash
python tools/evaluer_interpreteur_agent.py --dry-run   # combien d'appels, sans en faire
python tools/evaluer_interpreteur_agent.py --detail    # mesure + rapport, une ligne par phrase
```
