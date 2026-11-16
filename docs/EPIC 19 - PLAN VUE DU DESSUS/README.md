# ÉPIC 19 — Plan du potager sur vue du dessus

*Dossier de suivi · état au **16/11/2026** · branche `feature/pwa-plan-vue-parcelle` · numéro d'épic à valider.*

## À quoi sert ce dossier

Il réunit au même endroit ce que l'épic **prévoit** (d'après la maquette), ce qu'il **contient** (les
fonctions) et **où il en est** (US, Jira, déploiement, ce qui reste).

| Fichier | Contenu |
|---|---|
| [`README.md`](README.md) | Cette page : objectif, état global, arbitrages, réserves, suite |
| [`01_maquette.md`](01_maquette.md) | Ce que prévoit la maquette « Plan - Pistes » : pistes, écrans, règles, principes |
| [`02_fonctions.md`](02_fonctions.md) | Catalogue des fonctions (F01 à F43) : ce qu'elles font, d'où elles viennent, où elles vivent dans le code |
| [`03_us_et_avancement.md`](03_us_et_avancement.md) | Les 16 US : points, Jira, état, écarts avec la fiche, reste à faire |

Les fiches d'US elles-mêmes sont dans `backlog/US-320_…` à `backlog/US-335_…`. L'ancien
`docs/EPIC19_decomposition_US.md` (état du 13/11) est **périmé** : ce dossier le remplace.

## L'objectif en une phrase

Remplacer la vue « Plan · rangs et places » — qui montrait le modèle de données — par **le potager lui-même** :
chaque parcelle dessinée à sa place et à l'échelle, chaque rang avec ce qui y pousse et à quelle étape,
et **toute écriture passant par Gaston** (le compagnon), jamais par un formulaire caché derrière un dessin.

Principe directeur de la maquette : **ce qui manque devient une tâche.** Une culture sans parcelle est
*listée* (« À placer »), jamais dessinée comme un lieu.

## État global

| | |
|---|---|
| **US** | 16 (US-320 à US-335) — **92 points** |
| **Livrées** | **15 US · 84 points (91 %)** : US-320 à US-334 |
| **Restante** | **1 US · 8 points** : US-335 (photo de fond), **bloquée** par l'arbitrage RGPD P2 |
| **Jira** | PIA-304 à PIA-318 (US-320 à US-334) : tous « **Revue en cours** ». US-335 : aucun ticket |
| **Code** | Commité et poussé. Dans `dev` via les PR #193, #194 et #195 |
| **Déploiement dev** | Vert (14/11, PR #195). Le premier (PR #193) avait échoué sur l'ingestion du corpus, corrigé depuis |
| **Production (`main`)** | **Pas encore** : `dev` a 118 commits d'avance sur `main` |
| **Version** | v3.128.0 (US-320 à 333) puis v3.129.0 (US-334) dans `PATCH_NOTES.md` |
| **Migrations** | v76 (géométrie, US-326) et v77 (contexte des échanges, US-323) — jouées sur le déploiement dev, **pas en production** |

### Avancement par lot

```
Socle         US-320 étapes · US-321 langage visuel · US-326 géométrie        ██████████ 3/3
Plan          US-327 vue du dessus · US-322 suivi · US-328 Aujourd'hui · US-329 mobile  ██████████ 4/4
Gaston        US-323 contexte · US-324 Noter · US-325 barre basse             ██████████ 3/3
Parcelle      US-330 détail · US-331 caractéristiques · US-332 créer/inactiver ██████████ 3/3
Édition       US-333 éditeur · US-334 mise en place                            ██████████ 2/2
Photo         US-335 fond photo et recalage                                    ░░░░░░░░░░ 0/1  (bloquée)
```

## Arbitrages

| # | Sujet | État |
|---|---|---|
| P1 | Cultures ou Pépinière sous « Plus » | Tranché : **Cultures sous Plus** (US-325) |
| **P2** | **RGPD de la photo de fond** | **Ouvert — bloque US-335** |
| P3 | Étapes par type de culture | Tranché : semis direct Semé → Levé → En récolte → Terminé ; plant Planté → En récolte → Terminé. **Pas d'étape « En croissance » ni « En fleur »** (voir écarts) |
| P4 | Rang partagé : fraction ou mètres | Tranché : la position du rang ; la part en mètres seulement si la longueur de la parcelle est connue |
| P6 | Ordre du chemin | Tranché : `Parcelle.ordre` |
| P7 | Champ « forme / type » de parcelle | Tranché : colonne libre `forme`, sans lien avec `abri` ni `type_pepiniere` |

## Réserves — ce qui n'a pas été fait ou vérifié

1. **Comparaison à la maquette jamais faite.** Le rendu a été contrôlé à 375, 768 et 1280 px (US-333 : 1280
   et 1024 px), mais pas comparé point par point à « Plan - Pistes ». Verdict QA : *GO avec réserves*.
   Pour les couleurs et pictogrammes d'US-321, la section « Langage visuel commun » de la maquette n'avait pas
   été vue : ils sont de notre choix, **à comparer**.
2. **Aucune recette sur le vrai modèle** pour US-323 (CA7) et US-324 : un appel réel exige l'accord explicite
   du responsable produit. US-328 n'est pas concernée (placement sans modèle).
3. **Telegram** : les phrases d'étape (« les fèves sont en fleur », « rang libéré »), « au rang 3 » et les
   intentions créer / inactiver / supprimer une parcelle n'ont pas été vérifiées sur Telegram réel.
4. **Production** : rien n'est en production ; les migrations v76 et v77 n'y sont pas jouées.
5. **Jira** : US-335 sans ticket ; **US-203 absorbée par US-326 mais pas fermée** (PIA-155).
6. **Corpus** : fiches `doc_app` et guide mis à jour dans chaque livraison ; l'ingestion tourne au déploiement.
7. **Ajustements en cours de route** : voir « Écarts entre la fiche et le livré » dans `03_us_et_avancement.md`.

## Suite recommandée

1. **Valider visuellement** les écrans livrés contre la maquette (US-321 à US-334), avant de promouvoir en production.
2. **Recette sur le vrai modèle** d'US-323 et d'US-324, avec accord, au volume annoncé.
3. **Trancher P2** (stockage d'une photo = donnée personnelle) puis engager **US-335**.
4. **Régulariser Jira** : fermer US-203, créer le ticket d'US-335, passer les US recettées de « Revue en cours » à « Terminé ».
5. **Promouvoir en production** (PR `dev` → `main`) avec les migrations v76 et v77.
