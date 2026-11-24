# Relecture humaine — mesure US-342/343 du 23/11/2026

Pour chaque fiche : lire la fiche de besoin et le dialogue, puis donner votre verdict (utile au tour 1, aboutit en 3 tours au plus, contrôles du code justes ou non) — dans la case en bas de la fiche, ou directement dans la conversation. Les « points à regarder » sont des questions, pas des conclusions. Vos verdicts sont reportés dans `verdicts_humains.json` ; un attendu, une règle du juge ou un contrôle faux va dans `A_CORRIGER.md`.

Échantillon tiré par le rapport (passage 3) : 15 cas par moteur, Mistral Small 4, juge Mistral Large 3. U = utile au premier tour, A = aboutit. ✅ oui · ❌ non · ⚠️ juge indisponible (quota dépassé).

## Ordre de relecture proposé

D'abord les cas où un doute est le plus net (juge contredit par la trace, attendu inadapté, juge absent), puis les autres doutes, puis les cas sans doute.

| # | Moteur | Cas | Besoin | Jeu | Juge U / A | Échecs du code | Doutes | Fiche | Utile | Aboutit |Contrôle juste | remarque
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | actuel | B16-F4 | lire son stock | rempli | ✅ / ✅ | — | 2 | [actuel_B16-F4.md](actuel_B16-F4.md) |non|non|non|le compagnon invente « rien en stock » alors que le potager 38 a 7 variétés
| 2 | actuel | B24-F4 | va-t-il geler ? | rempli | ✅ / ✅ | — | 2 | [actuel_B24-F4.md](actuel_B24-F4.md) |non|non|non|Jours décalés (« dès demain », dimanche 26 etc. faux)
| 3 | boucle | B09-F2 | noter un semis fait | neuf | ❌ / ✅ | inventé | 2 | [boucle_B09-F2.md](boucle_B09-F2.md) |non|non|non|avant de proposer le geste, il doit demander Quelle quantité ? (ex: 2 kg, 15 plants, 1 sachet...) car non précisé dans la demande du jardinier
| 4 | boucle | B10-F1 | noter une plantation faite | neuf | ✅ / ✅ | — | 2 | [boucle_B10-F1.md](boucle_B10-F1.md) |non|non|non|le jardinier confirme avoir planter donc il s'agit d'enregistrer le geste immédiatement
| 5 | boucle | B22-F2 | associations de la tomate | neuf | ❌ / ✅ | — | 2 | [boucle_B22-F2.md](boucle_B22-F2.md) |oui|partiel|partiel|la réponse de l'outil est plus détaillé : voir commande /Association lister tomate, cette commande donne aussi des consignes plus précis.
| 6 | boucle | B03-F6 | semer un haricot en pleine terre | neuf | ❌ / ❌ | inventé | 3 | [boucle_B03-F6.md](boucle_B03-F6.md) |oui|partiel|oui|sa réflexion, accès à la fiche, puis s'appuis sur l'agent pour une réponse. dans les tests réalisé j'ai eu plusieurs réponses différentes du compagnon; il reformule : tu veux semer des poic chiches en plaine terre ou en pépinière. Si je précise en pleine terre alors il m'indique qu'il ne peut pas créer la parcelle planche légume. (plutôt bizarre). autre cas ou il rejoins la réponse du test, il ne trouve pas de conseil pour semer dans ces références. Il ajoute le noter pour es prochaines mises à jour. Il s'agit d'une réponse inventé car il n'effectue aucune opération de mémorisation de la demande.
| 7 | boucle | B19-F6 | trouver une fonction de l'appli | neuf | ❌ / ❌ | — | 2 | [boucle_B19-F6.md](boucle_B19-F6.md) |non|non|non|dans la version 3.134 il répond correctement en me demandant la ville puis il interroge le service avec la ville pour une météo correcte. Sur la version 3.140, il demande aussi la ville mais dès que la ville est donné, il répond par je te propose la météo de Monaco pour aujourd'hui. sans résultat. 
| 8 | boucle | B17-F6 | lire son carnet | rempli | ✅ / ❌ | — | 2 | [boucle_B17-F6.md](boucle_B17-F6.md) |oui|oui|oui| A noter qu'en version 3.140 il semble ne pas comprendre la question. donc la version précédente était plius juste
| 9 | boucle | B23-F4 | où en est la pépinière | rempli | ⚠️ / ⚠️ | — | 2 | [boucle_B23-F4.md](boucle_B23-F4.md) |oui|oui|oui|sur  les version 3.134 ou 3.140 si la pépinière est vide de semis alors il répond qu'il n'a pas bien compris. ce qui est faux. dans ce cas il doit effectivement répondre aucun semis en pépinière actuellement
| 10 | boucle | B08-F3 | arroser ou non | rempli | ✅ / ⚠️ | — | 3 | [boucle_B08-F3.md](boucle_B08-F3.md) |oui|oui|oui
| 11 | boucle | B07-F6 | que faire au potager | rempli | ❌ / ❌ | écriture | 4 | [boucle_B07-F6.md](boucle_B07-F6.md) |oui|oui|oui
| 12 | boucle | B18-F3 | comprendre un symptôme | rempli | ❌ / ✅ | — | 3 | [boucle_B18-F3.md](boucle_B18-F3.md) |oui|non|partiel|il faut noter l'observation dans le carnet de la tomate et poser une question complémentaire au jardinier afin de localiser plus précisement la/les tomates observées
| 13 | boucle | B22-F5 | associations de la tomate | neuf | ❌ / ✅ | — | 1 | [boucle_B22-F5.md](boucle_B22-F5.md) |oui|non|partiel|il n'a pas utilisé la mémoire de conversation pour associer cette recherche avec la culture de tomate
| 14 | boucle | B15-F1 | corriger ce qui vient d'être dit | neuf | ❌ / ✅ | — | 3 | [boucle_B15-F1.md](boucle_B15-F1.md) |oui|oui|oui|A noter que le comportement réel n'est pas capable de comprendre le semis sur 3 unités de rang
| 15 | boucle | B09-F3 | noter un semis fait | neuf | ✅ / ❌ | — | 2 | [boucle_B09-F3.md](boucle_B09-F3.md) |oui|non|non|il ne propose pas d'enregistrer le geste et de faire les contrôles nécessaires pour permettre l'enregistrement du geste dans le carnet 
| 16 | boucle | B20-F4 | culture sans fiche (panais) | neuf | ❌ / ❌ | inventé | 3 | [boucle_B20-F4.md](boucle_B20-F4.md) |
| 17 | actuel | B01-F8 | planter une salade absente | neuf | ❌ / ❌ | — | 3 | [actuel_B01-F8.md](actuel_B01-F8.md) |
| 18 | actuel | B14-F4 | noter une perte | neuf | ❌ / ❌ | — | 3 | [actuel_B14-F4.md](actuel_B14-F4.md) |
| 19 | actuel | B14-F1 | noter une perte | neuf | ❌ / ❌ | — | 3 | [actuel_B14-F1.md](actuel_B14-F1.md) |
| 20 | actuel | B15-F3 | corriger ce qui vient d'être dit | neuf | ❌ / ❌ | inventé | 2 | [actuel_B15-F3.md](actuel_B15-F3.md) |
| 21 | actuel | B15-F4 | corriger ce qui vient d'être dit | neuf | ❌ / ❌ | inventé, écriture | 3 | [actuel_B15-F4.md](actuel_B15-F4.md) |
| 22 | actuel | B05-F1 | est-ce le moment ? (radis) | neuf | ❌ / ❌ | — | 2 | [actuel_B05-F1.md](actuel_B05-F1.md) |
| 23 | actuel | B06-F3 | que semer ce mois-ci | neuf | ❌ / ❌ | — | 3 | [actuel_B06-F3.md](actuel_B06-F3.md) |
| 24 | actuel | B22-F6 | associations de la tomate | neuf | ❌ / ❌ | — | 1 | [actuel_B22-F6.md](actuel_B22-F6.md) |
| 25 | actuel | B19-F2 | trouver une fonction de l'appli | neuf | ✅ / ✅ | — | 2 | [actuel_B19-F2.md](actuel_B19-F2.md) |
| 26 | actuel | B03-F1 | semer un haricot en pleine terre | neuf | ❌ / ❌ | — | 3 | [actuel_B03-F1.md](actuel_B03-F1.md) |
| 27 | boucle | B09-F4 | noter un semis fait | neuf | ❌ / ❌ | hors-sujet 5 | 1 | [boucle_B09-F4.md](boucle_B09-F4.md) |
| 28 | actuel | B07-F4 | que faire au potager | rempli | ❌ / ❌ | — | 2 | [actuel_B07-F4.md](actuel_B07-F4.md) |
| 29 | actuel | B08-F2 | arroser ou non | rempli | ❌ / ❌ | — | 2 | [actuel_B08-F2.md](actuel_B08-F2.md) |
| 30 | actuel | B04-F7 | planter des tomates (plants) | neuf | ❌ / ❌ | écriture | 0 | [actuel_B04-F7.md](actuel_B04-F7.md) |

## Ce qui revient d'une fiche à l'autre (à garder en tête)

- **Le juge ne voit pas ce que les outils ont rendu** : il lit le nom de l'outil et ses arguments, pas le résultat (`tools/jeu_evaluation/juge.py`, `transcrire`). Il ne peut donc pas distinguer une donnée lue d'une donnée inventée (actuel B16-F4, B24-F4 ; boucle B07-F6).
- **Clic « Confirmer » sans carte en attente** : quand le compagnon écrit « veux-tu que je… », « tu veux que je… », « je te propose », le jardinier simulé clique « Confirmer » même si rien n'est proposé ; le texte « (Confirmé : la mesure n'exécute rien.) » ne pose pas de question et le dialogue s'arrête (actuel B03-F1, B06-F3, B14-F1, B14-F4 ; boucle B03-F6, B09-F3, B10-F1).
- **Questions non reconnues par le jardinier simulé et par « intention gardée »** : « la date exacte », « tu veux dire que… ? », « semer ou planter ? » ne sont pas détectées : le simulateur répond « je ne sais pas » et le contrôle ne compte pas la redemande (actuel B05-F1, B15-F4 ; boucle B07-F6, B09-F4).
- **Besoins sans `outils_attendus`** alors que l'attendu exige une lecture : B03, B07, B08, B16, B18, B23 — « données lues » reste vide.
- **Attendus génériques d'un besoin appliqués à une formulation qui demande autre chose** : boucle B03-F6 (pois chiche jugé sur l'attendu du haricot), B17-F6 (dernier semis), B19-F6 (météo d'une autre région).
- **Juge indisponible (quota)** sur 2 cas de l'échantillon (boucle B08-F3 « aboutit », B23-F4 les deux). Sur toute la mesure, le juge manque pour « utile » 13 fois (actuel) et 49 fois (boucle) sur 432, pour « aboutit » 29 et 64 fois ; le rapport calcule les taux sans ces cas.

## Fichiers

- `<moteur>_<cas>.md` : une fiche par cas (30).
- `verdicts_humains.json` : vos verdicts, une entrée par cas (`null` = pas encore relu).
- `A_CORRIGER.md` (créé au besoin) : attendus, règles du juge ou contrôles jugés faux, sans correction faite.
- `SYNTHESE.md` (à la fin) : accord juge/humain par moteur, désaccords, contrôles faux.
