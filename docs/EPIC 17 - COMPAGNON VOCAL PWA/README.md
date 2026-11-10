# ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider)*

Parler à Gaston depuis la PWA et l'écouter au haut-parleur, sur PC, tablette et mobile,
avec les modèles Voxtral de Mistral (transcription et synthèse, choix de la voix, ton et
rythme par balises).

| Document | Contenu |
|---|---|
| [ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md](ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md) | besoin, existant, offre Mistral, contraintes, décisions D1 à D8, solution, coût, RGPD, découpage |
| `RAPPORT_ESSAI_VOXTRAL_FR.md` | à produire par US-298 : verdict sur les formats, les voix et les balises en français |

## Décisions

| # | Décision |
|---|---|
| D1 | Balises essayées en français d'abord, puis posées par des règles |
| D2 | Voix françaises lues sur l'API, repli sur Marie, Manon, Léa et Camille ; pas de clonage |
| D3 | Appuyer pour parler (fichier), pas de temps réel |
| D4 | Phrase transcrite envoyée automatiquement |
| D5 | Lecture automatique après une dictée, ▶ sur chaque réponse |
| D6 | Résumé parlé court, distinct du texte affiché |
| D7 | PWA seulement, le bot Telegram n'est pas modifié |
| D8 | Pas d'outillage de test dédié ; tests habituels par US |

## User stories

| US | Titre | Dépend de | Points |
|---|---|---|---|
| [US-298](../../backlog/US-298_essayer-voxtral-en-francais.md) | Essayer Voxtral en français avant de construire | — | 2 |
| [US-299](../../backlog/US-299_transcrire-synthetiser-voxtral-passerelle.md) | Transcrire et synthétiser par Voxtral dans la passerelle | US-298 | 5 |
| [US-300](../../backlog/US-300_preferences-vocales-catalogue-voix.md) | Mémoriser les préférences vocales et lister les voix françaises | US-299 | 3 |
| [US-301](../../backlog/US-301_regler-voix-compagnon.md) | Régler la voix de mon compagnon dans la PWA | US-300 | 3 |
| [US-302](../../backlog/US-302_dicter-phrase-compagnon.md) | Dicter une phrase au compagnon depuis la PWA | US-299, US-300, US-301 | 5 |
| [US-303](../../backlog/US-303_resumer-reponse-pour-oral.md) | Résumer la réponse du compagnon pour l'oral | US-299 | 3 |
| [US-304](../../backlog/US-304_ecouter-reponse-gaston.md) | Écouter la réponse de Gaston au haut-parleur | US-300, US-302, US-303 | 5 |
| [US-305](../../backlog/US-305_ton-rythme-par-regles.md) | Donner le ton et le rythme de Gaston par des règles | US-298 (verdict), US-304 | 3 |

Total : 29 points. Maquettes Claude Design à produire avant US-301, US-302 et US-304.
Tickets Jira (projet PIA) à créer.
