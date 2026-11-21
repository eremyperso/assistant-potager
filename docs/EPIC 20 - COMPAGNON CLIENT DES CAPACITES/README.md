# ÉPIC 20 — Le compagnon, client de ses capacités

*État au 18/11/2026. Source : [ARCHITECTURE_COMPAGNON_CAPACITES.md](../EPIC%20-%20AGENT%20INTERPRETEUR/ARCHITECTURE_COMPAGNON_CAPACITES.md)
et [RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md](../EPIC%20-%20AGENT%20INTERPRETEUR/RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md).
Les US sont dans `backlog/` (US-336 à US-350).*

## L'épic en dix lignes

Le compagnon de la PWA (et, plus tard, de Telegram) traduit aujourd'hui une phrase en **commandes du bot**, avec une mémoire
courte et une couche de code qui interprète la langue autour du modèle. Le 14/11/2026, sur « j'aimerai planter des salades »
(7 tours), la chaîne actuelle perd l'intention et dérive, avec Small 4 comme avec Large 3. Le **même** Small 4, avec les
lectures du serveur MCP et l'historique complet, tient le fil et consomme deux fois moins de jetons.

L'épic remplace donc le cœur de la conversation : **une couche de capacités** (verdicts calculés par le code, partagés avec le
MCP), **une boucle où le modèle conduit**, **un fil complet**, et **une mesure avant chaque lot**. Le chemin d'écriture sûr
(proposer → valider → confirmer → exécuter) est conservé tel quel.

| | |
|---|---|
| **US** | 15 (US-336 à US-350), **68 points** |
| **Livrées** | US-336 (5 pts) et US-337 (5 pts, sauf CA8), non commitées |
| **À faire** | 13 US, 58 points |
| **Modèle de développement** | Opus 5.5 pour 13 points seulement (US-342, US-343) ; Sonnet 5.5 pour 53 points ; Haiku 5.5 pour 2 points |
| **Migration** | une seule probable : US-343 (le fil complet) |
| **Chemin critique** | 42 points : US-338 → 339 → 340 → 342/343 → 344 → 345 → 346 → 347 |

## Contenu du dossier

| Fichier | Pour quoi faire |
|---|---|
| [01_ANALYSE.md](01_ANALYSE.md) | Ce qu'on a appris : de l'agent interpréteur (octobre) à l'architecture à capacités (novembre), la mesure du 14/11, les principes, ce qu'on garde et ce qu'on retire |
| [02_DECOUPAGE_US.md](02_DECOUPAGE_US.md) | Les 16 US : lot, points, modèle, niveau d'effort, migration, état Jira |
| [03_ENCHAINEMENT.md](03_ENCHAINEMENT.md) | Dépendances, ce qui se fait en série ou en parallèle, vagues, points d'arrêt (portes de mesure) |
| [04_PLAN_DE_TESTS.md](04_PLAN_DE_TESTS.md) | Les étapes de test que je mène à chaque US et à chaque porte, avec les seuils |
| [05_BESOINS_ATTENDUS.md](05_BESOINS_ATTENDUS.md) | Ce dont j'ai besoin de vous : accords, clés, bases, arbitrages, relectures |
| [06_LIGNE_DE_BASE_G0.md](06_LIGNE_DE_BASE_G0.md) | Porte G0 (20/11/2026) : ligne de base de la chaîne actuelle et du prototype à capacités, fidélité de la mesure, déroulé |
| [07_REGLE_D_UNE_CAPACITE.md](07_REGLE_D_UNE_CAPACITE.md) | Règle d'écriture d'une capacité (R1 à R5), où vit le registre neutre, exemple de verdict (US-338) |
| [REFERENCE_HUMAINE_B01.md](REFERENCE_HUMAINE_B01.md) | Verdicts et bonnes réponses du jardinier sur 9 scénarios joués le 18/11/2026, versés dans le jeu |

Autres documents de référence : [JEU_EVALUATION_COMPAGNON.md](../EPIC%20-%20AGENT%20INTERPRETEUR/JEU_EVALUATION_COMPAGNON.md)
(format du jeu), [domaines/evaluation-compagnon.md](../domaines/evaluation-compagnon.md) (outils de mesure),
[ARCHITECTURE_AGENT_INTERPRETEUR.md](../EPIC%20-%20AGENT%20INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md) (l'ancien cadrage,
dont §2.2, §3.5, §3.7 et §12.10 restent la référence).

## Points ouverts au 20/11/2026

1. **Numéro US-336.** Jira porte déjà un « US-336 : Étudier l'itinéraire de saison » (PIA-319, créé le 16/11) ; le fichier
   `backlog/US-336_jeu-evaluation-compagnon.md` porte le même numéro. À renuméroter d'un côté ou de l'autre ; les tests et
   la documentation du jeu d'évaluation citent « US-336 ».
2. **Ligne de base de la chaîne actuelle** (CA8 d'US-337) : **mesurée le 20/11/2026**, voir
   [06_LIGNE_DE_BASE_G0.md](06_LIGNE_DE_BASE_G0.md). Reste avant G1 : corriger la grille du juge (« utile au premier tour »
   noté sur la suite du dialogue, accord juge / jardinier 57 %).
3. **Arbitrages A1 à A7** de l'architecture (§9) et **seuils du §7.2** : ouverts. Voir [05_BESOINS_ATTENDUS.md](05_BESOINS_ATTENDUS.md).
4. **Prérequis de livraison.** Les US-290 à US-297 (serveur MCP) sont commitées (27f4569, 02483d3) ; US-338 peut démarrer.
