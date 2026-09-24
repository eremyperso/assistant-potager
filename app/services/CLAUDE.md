# app/services — couche métier partagée par le bot et l'API

Un service = un module, sans dépendance à Telegram ni à FastAPI. Les handlers
(`app/bot/`, `app/api/main.py`) l'appellent ; lui seul touche la base.

## Avant de modifier un service, lire sa fiche de domaine

| Modules | Fiche |
|---|---|
| `familles`, `attributs_culture`, `associations`, `rotation`, `bioagresseurs`, `fiche_culture`, `import_referentiel`, `adaptateur_wind_river`, `referentiel_sources` | `docs/domaines/referentiel-cultures.md` |
| `prediagnostic`, `reponses_chiffrees` (famille `bioagresseurs_culture`) | `docs/domaines/prediagnostic.md` |
| `calendrier_cultural`, `contexte_semis`, `recalage_calendrier` | `docs/domaines/calendrier-cultural.md` |
| `menu_commandes`, `interpreteur_commandes` | `docs/domaines/commandes-bot.md` |
| `connaissance`, `memoire_potager`, `cache_questions` | `docs/domaines/socle-connaissance.md` |
| `repartition_rangs` | `docs/domaines/plan-et-rangs.md` |

## Invariants transverses

- Multi-tenant : toute requête passe par le contexte (`context.current_context`) et
  `database.db.tenant_scope` ; une lecture sans filtre `potager_id` est un défaut.
- Une donnée PARTAGÉE (`potager_id NULL`) n'est écrite que par les imports, jamais
  par une saisie utilisateur ; une correction au bot est toujours locale au potager.
- Aucun chiffre agronomique, aucune fenêtre, aucune durée n'est produit par un
  modèle de langage : ce qui n'est pas dans le référentiel est affiché vide.
- `evenements.py` est le seul point d'écriture des événements (invalidation de
  cache US-095 et indexation mémoire US-141 y sont branchées).
- Un service ajouté qui rend une fiche de `data/connaissance/doc_app/` fausse
  impose la mise à jour de la fiche dans le même commit (US-099 / CA9).
