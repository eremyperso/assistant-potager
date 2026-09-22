# Migrations de base de données

Fichiers SQL manuels dans `migrations/`, numérotés séquentiellement (v2 → v52),
chacun avec son `rollback_vN.sql` depuis v16. À appliquer dans l'ordre sur une
base neuve. En dev, `scripts/update_dev.ps1` joue celles qui manquent (suivi
dans `.migrations_applied`) ; en prod et en dev distant, les workflows
`.github/workflows/deploy*.yml` font de même.

```bash
psql -d potager -f migrations/migration_v52.sql
```

## Ce que portent les dernières migrations

- **v52 [US-197]** — ajoute `parcelles.nb_rangs` (SMALLINT nullable) : le
  nombre de rangs DÉCLARÉS d'une planche, dénominateur de la Vue plan
  (« 13 rangs occupés sur 18 déclarés »). **Aucun backfill** — NULL veut dire
  « jamais renseigné », et le lire comme « zéro rang » ferait passer chaque
  planche existante pour une planche sans place. Contrairement à `parcelles.abri`
  (v49), dont le vocabulaire se révise en Python, la borne 1–99 est une propriété
  stable du domaine : elle est posée en CHECK SQL (`ck_parcelles_nb_rangs`) et
  redoublée au point d'écriture (`utils.parcelles._nb_rangs`), que SQLite — donc
  les tests — n'obtiendrait pas du CHECK. La colonne ne pilote AUCUN calcul :
  ni stock, ni `occupation_pct`, ni confiance. Elle n'a rien à voir avec le
  « rang » d'un événement, qui reste un multiplicateur de geste.
- **v51 [US-224]** — transforme `gestes_intentions` en **file d'attente**.
  `consomme_le` devient `traite_le` (renommage délibéré : ce n'est plus « ce
  lien a servi », à l'ouverture, mais « ce geste est sorti de la file », à la
  confirmation ou à l'abandon — garder l'ancien nom aurait laissé cohabiter
  deux sémantiques opposées sous la même colonne), et ajoute `etat`
  (`en_attente | confirme | abandonne | perime`), `motif_refus` et
  `avertissement_le`. `expire_le` ne change pas de forme, seulement de valeur :
  trois jours depuis le dépôt, **par geste** — jamais par pile. Crée
  `files_gestes_reglages`, une ligne par compte pour ce qui relève de la
  RELANCE et n'appartient à aucun geste (coupure, dernière invitation,
  dernière relance, message à remplacer) ; **pas de RLS** sur celle-ci, comme
  `liaisons_telegram` : c'est une table de compte, pas de jardin. La RLS de
  `gestes_intentions` est INCHANGÉE, et c'est un choix : US-224 fait du bot un
  écrivain sur cette table, il arme donc `app.potager_id` sur le potager DU
  GESTE avant chaque mise à jour (`file_gestes._ecriture`) plutôt que de
  relâcher le `WITH CHECK`, ce qui aurait ouvert l'écriture croisée entre
  potagers.
- **v50 [US-196]** — crée `gestes_intentions` : un geste pré-parsé déposé par
  la PWA, que le bot confirme. La table existe parce que l'API et le bot sont
  DEUX PROCESSUS — un cache mémoire ne traverse pas cette frontière. Sa policy
  RLS est **tolérante au GUC non armé en lecture**, seul moyen pour le bot de
  retrouver un geste par son code avant de savoir de quel potager il relève ;
  l'écriture, elle, exige le GUC.
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
