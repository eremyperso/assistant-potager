# ÉPIC 21 — Socle commun des vues

*État au 25/11/2026, branche `ergo_socle_commun`. Les US sont dans `backlog/` (US-352 à US-361). Neuf US sur dix sont livrées (US-352 à US-360, v3.141.0 à v3.147.0), avec leur ticket Jira en « Revue en cours » ; rien n'est commité. Reste US-361 (rédigée, sans ticket). Le découpage et l'état de chaque US sont dans `02_DECOUPAGE_US.md` ; la recette (partielle) est dans `03_RECETTE.md`.*

## L'épic en dix lignes

La maquette « Socle commun · les sept vues » (Claude Design, projet « potager 2026 ») harmonise toute la PWA, sur mobile comme sur ordinateur.
Elle tient en une seule grammaire. Chaque page a cinq bandes (en-tête, Mot de Gaston, barre d'outils, contenu, fiche commune) et un seul bouton rond, **Noter**, pour parler à Gaston.
Le langage d'étape et le calendrier aux six couleurs sont les mêmes partout, et la police Kalam est réservée au texte du jardinier.

Les fonctions existent déjà. L'épic **reproduit fidèlement le rendu** sans migration ni route nouvelle.
Il refait aussi en profondeur **l'écran de Gaston** : plein écran sur mobile, panneau droit sur ordinateur, carnet en Kalam, carte « À enregistrer » à plusieurs lignes, et des suggestions selon le contexte qui ne coûtent aucun appel au modèle.

| | |
|---|---|
| **US** | 9 (US-352 à US-360), **53 points** |
| **Découpage** | Transverse : 2 US de socle, puis 5 US en parallèle, puis 2 US de clôture |
| **Modèle de développement** | Sonnet 5.5 partout (26 pts en `high`, 21 en `medium`, 6 en `low`). Ni Opus ni Fable ne sont requis |
| **Migration** | aucune ; une seule touche backend, en lecture (onglet Semer de la Pépinière, US-356) |
| **Chemin critique** | 29 points : US-352 → 353 → 355 ou 356 → 358 → 359 |
| **Questions** | Toutes tranchées le 24/11 (D8 à D12 de l'analyse) : Pépinière en trois onglets, rappel de semis à l'ajout depuis le catalogue, pièces jointes supprimées, tableau de bord figé, mode sombre réactivé |

## Contenu du dossier

| Fichier | Pour quoi faire |
|---|---|
| [01_ANALYSE.md](01_ANALYSE.md) | Ce que dit la maquette : anatomie, pièces, sept vues, compagnon. Écarts avec la PWA, décisions D1-D12 |
| [02_DECOUPAGE_US.md](02_DECOUPAGE_US.md) | Les 9 US, le modèle et l'effort, l'enchaînement par vagues, la synthèse de production |
| [maquette/Socle commun - 7 vues.html](maquette/Socle%20commun%20-%207%20vues.html) | Copie figée de la version 2 de la maquette (24/11 : Pépinière en trois onglets, mode sombre). Elle s'ouvre seule dans un navigateur et tous ses écrans sont cliquables. C'est **la référence de fidélité** de chaque US |

Maquette en ligne : canvas « potager 2026 », page *Socle commun - 7 vues*.
