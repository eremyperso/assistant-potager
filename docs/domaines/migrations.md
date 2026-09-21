# Migrations de base de données

Fichiers SQL manuels dans `migrations/`, numérotés séquentiellement (v2 → v49),
chacun avec son `rollback_vN.sql` depuis v16. À appliquer dans l'ordre sur une
base neuve. En dev, `scripts/update_dev.ps1` joue celles qui manquent (suivi
dans `.migrations_applied`) ; en prod et en dev distant, les workflows
`.github/workflows/deploy*.yml` font de même.

```bash
psql -d potager -f migrations/migration_v49.sql
```

## Ce que portent les dernières migrations

- **v47 [US-069]** — ajoute `evenements.contexte_semis` nullable (`pepiniere` |
  `pleine_terre` | NULL), avec un CHECK qui n'autorise ce contexte que sur un
  `semis`, et rejoue le seul backfill non présomptueux : un semis chaîné à une
  `mise_en_godet` (`origine_graines_id`) devient `pepiniere`, tout autre reste
  NULL — jamais présumé `pleine_terre`. Cet UPDATE vit entre des marqueurs
  `REPRISE` et est exécuté tel quel par `tests/test_us069_contexte_semis.py` :
  on l'édite là, on ne le recopie jamais. La colonne ne pilote AUCUN calcul de
  stock (le stock dérive toujours de `parcelles.est_pepiniere`).
- **v46 [US-068]** — crée le calendrier cultural (`itineraire_cultural`,
  `fenetre_culturale` par zone climatique, `duree_culturale` commune à toutes
  les zones), les trois sous la politique RLS `potager_id NULL = partagé`, et
  ajoute `potagers.zone_climatique` nullable, qui ne stocke que le choix
  explicite du jardinier : la zone déduite de la localisation se calcule à la
  lecture (`app/services/calendrier_cultural.zone_depuis_localisation`), jamais
  en backfill SQL. Aucune ligne de calendrier n'est semée.
- **v45 [US-165]** — crée `symptome` (index GIN plein texte) et
  `symptome_bioagresseur` (arête pondérée), toutes deux sous RLS. `symptome` n'a
  volontairement **pas** de `culture_id` : un symptôme n'appartient à aucune
  culture, et c'est la jointure avec `culture_bioagresseur` qui désigne la piste —
  une colonne de culture aurait dupliqué chaque symptôme par culture et rendu la
  désambiguïsation CA14 structurellement impossible.
- **v44 [US-172]** — ajoute `commande_interpretee` / `issue_interpretation` à
  `routage_logs` (nullable, idempotent), pour journaliser une commande
  interprétée et le sort de sa confirmation sans surcharger `issue_savoir` d'US-098.
- **v43 [US-162]** — bioagresseurs et relation culture × bioagresseur.
- **v42 [US-098]** — crée `knowledge_documents` / `knowledge_chunks` (index GIN
  plein texte, RLS sur les deux tables), ajoute `score_savoir` / `issue_savoir` à
  `routage_logs`, et crée la configuration de recherche `french_sans_accent`
  (`french` + `unaccent`). Ce n'est pas un raffinement : `french` seul lemmatise
  mais ne retire PAS les accents, donc « récolter » et « recolter » sont deux
  lexèmes sans rapport, et un jardinier qui tape sans accents — la norme sur
  mobile — rate chaque terme accentué du corpus. La migration le vérifie
  (`to_tsvector('french_sans_accent', 'récolter recolter')` doit rendre un seul
  lexème). Elle doit rester identique à `app/services/connaissance.CONFIG_FTS`,
  qui sert à l'écriture comme à la requête.

## RLS

Une fiche ou une ligne GLOBALE (`potager_id NULL`) ne s'écrit qu'avec le rôle
propriétaire de la base, jamais `app_user` — même règle pour
`tools/importer_referentiel.py` et `tools/ingerer_connaissance.py`.
