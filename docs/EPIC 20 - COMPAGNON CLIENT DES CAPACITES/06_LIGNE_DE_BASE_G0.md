# Porte G0 — ligne de base du compagnon (20/11/2026)

Modèle mesuré : Mistral Small 4 (`mistral-small-2603`). Juge : Mistral Large 3 (`mistral-large-2512`). Jeu : 144 cas
(100 sur le potager neuf 37, 44 sur le potager rempli 38), 3 passages par cas et par moteur.
`actuel` = chaîne en production (témoin) ; `capacites` = prototype de boucle sur le registre MCP (reconstitué, hors dépôt).

Détails (non versionnés, `rapports_evaluation/` est ignoré) : `rapports_evaluation/G0_20261120/rapport_neuf.md` et `rapport_rempli.md` ; traces dans `20261120_170706/` (capacites neuf), `20261120_182205/` (rempli), `20261120_185536/` (actuel neuf rejoué).

## Potager neuf (100 cas × 3)

| Critère | Seuil (à confirmer) | actuel | capacites |
|---|---|---|---|
| Utile au premier tour | ≥ 80 % | 7 % | 19 % |
| Aboutit (≤ 3 tours) | ≥ 85 % | 8 % | 15 % |
| Intention gardée | 100 % | 98 % | 96 % |
| Rien d'inventé | 100 % | 89 % | 75 % |
| Écriture sûre | 100 % | 95 % | 91 % |
| Hors-sujet montré | 0 | 48 | 58 |
| Latence p95 par tour | ≤ 4 s | 4,0 s | 3,0 s |
| Jetons d'entrée par tour | ≤ actuel | 16 849 | 8 070 |
| Données lues avant de répondre | — | 3 % | 45 % |
| Couverture absente dite | — | 8 % | 71 % |

Échecs dominants : `actuel` — passages sur une autre culture (36), chiffres sans source (32) ; `capacites` — quantité
jamais dite mise dans la proposition (50), chiffres sans source (22), hors-sujet (19).

## Potager rempli (44 cas × 3) — notes du code à jour, verdicts du juge AVANT correction de la grille

| Critère | actuel | capacites |
|---|---|---|
| Utile au premier tour | 23 % | 47 % |
| Aboutit | 22 % | 42 % |
| Intention gardée | 100 % | 100 % |
| Rien d'inventé | 99 % | 98 % |
| Écriture sûre | 99 % | 78 % |
| Hors-sujet montré | 3 | 0 |
| Latence p95 | 3,4 s | 2,9 s |

Réserves : 3 tours `actuel` arrêtés au geste (ancien moteur de mesure), 9 tours `capacites` en erreur fournisseur.

## Fidélité de la mesure

- Corrigé pendant G0 : la mesure suit le geste comme la PWA (`_suivre_le_geste`) ; le juge reçoit la date du jour et ne
  confond plus la fiche de besoin avec le dit ; contrôles : date du jour par défaut, lettres doublées, `afficher` n'est
  pas une écriture, une valeur LUE dans le potager n'est pas inventée.
- Accord juge / jardinier (phrases réelles du 18/11, première réponse, verdicts tranchés) : 12/21 = 57 %. Deux
  désaccords sont une faute du juge : il note « utile au premier tour » sur la suite du dialogue (B09-F6, B15-F7).
  **À corriger dans la grille avant G1.**
- Le moteur `capacites` n'est pas comparé aux verdicts humains : ils portent sur la chaîne actuelle.

## Déroulé

| Étape | Début | Fin | Durée |
|---|---|---|---|
| G0 potager neuf, deux moteurs (600 traces) | 17:07 | 18:22 | 1 h 15 |
| G0 potager rempli, deux moteurs (264 traces) | 18:22 | 18:54 | 32 min |
| Rejeu `actuel` neuf, moteur corrigé (300 traces) | 18:55 | 22:17 | 3 h 22 (41 min utiles) |
| Reprise des 161 traces dégradées | 22:18 | 22:44 | 26 min |
| Nouvelle notation `capacites` neuf (300 verdicts) | 22:45 | 23:05 | 20 min |
| **Total** | 17:07 | 23:05 | **5 h 58**, dont ≈ 3 h 15 de mesure utile |

Temps perdu : veille moderne du PC (réseau coupé de 19:02 à 19:09 et de 19:31 à 22:05), erreurs 500/429 de Mistral
vers 22:16 et sur le juge Large (214 verdicts à refaire), et le premier passage `actuel` invalidé par le défaut de suivi
du geste.
