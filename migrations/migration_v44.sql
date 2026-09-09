-- =============================================================================
-- migration_v44.sql — Journal des commandes interprétées (US-172)
-- =============================================================================
-- Aucune table nouvelle : l'US-172 journalise ses interprétations dans les
-- colonnes d'observabilité de routage déjà en place (`routage_logs`, US-097).
-- Deux d'entre elles manquaient, et le CA18 les nomme explicitement — la
-- commande retenue, et l'issue de la proposition.
--
-- Pourquoi ne pas réutiliser des colonnes existantes : `etage_resolveur` porte
-- déjà l'étage, `origine_classification` l'origine (règle ou modèle),
-- `confiance` la confiance et `latence_ms` la latence. Y loger en plus le nom
-- de la commande, ou détourner `issue_savoir` (US-098) pour y écrire l'issue de
-- la validation, rendrait illisibles DEUX mesures à la fois : celle du socle de
-- connaissance et celle de l'interpréteur. Deux colonnes valent mieux qu'une
-- colonne qui veut dire deux choses.
--
-- [CA18] Ce que ces colonnes permettent de savoir, et rien d'autre ne le
-- permet : quelles formulations le jardinier refuse au récapitulatif (issue
-- 'refusee'), et lesquelles il abandonne faute de savoir compléter un argument
-- ('abandonnee'). C'est la matière première de l'enrichissement des règles —
-- donc ce qui dit quelles formulations écrire ensuite, exactement comme
-- `issue_savoir = 'vide'` dit quelles fiches écrire ensuite.
--
-- Les deux colonnes sont NULLABLES : une ligne écrite par le routeur (une
-- question, l'écrasante majorité) n'a ni commande ni issue de validation, et
-- doit continuer de s'écrire sans elles. NULL y signifie « cette demande n'est
-- pas passée par l'interpréteur », jamais « on ne sait pas ».
--
-- Idempotente et rejouable : `ADD COLUMN IF NOT EXISTS`. Aucune donnée
-- existante n'est réécrite, aucun index n'est ajouté — ces colonnes se lisent
-- en filtrant d'abord sur `potager_id` + `cree_le`, que
-- `idx_routage_logs_potager_date` couvre déjà.
--
-- Rollback : rollback_v44.sql
-- =============================================================================

BEGIN;

-- Nom de la commande retenue, sous-commande comprise : « parcelle supprimer »,
-- « culture profondeur », « stats ». Le format lisible est délibéré — cette
-- colonne se lit à l'œil dans une requête d'exploitation, elle ne joint rien.
ALTER TABLE routage_logs
    ADD COLUMN IF NOT EXISTS commande_interpretee VARCHAR(64);

-- Issue de la proposition, vocabulaire fermé côté application
-- (`app/services/interpreteur_commandes.ISSUE_*`) :
--   'proposee'    récapitulatif affiché, le jardinier n'a pas encore tranché
--   'confirmee'   validé, la commande a été exécutée
--   'refusee'     refusé au récapitulatif — rien n'a été fait
--   'abandonnee'  une précision a été demandée et n'est jamais venue
--
-- Pas de CHECK de vocabulaire, même arbitrage que migration_v39, v41 et v43 :
-- un vocabulaire fermé mais révisable en produit, validé par le seul point
-- d'écriture applicatif.
ALTER TABLE routage_logs
    ADD COLUMN IF NOT EXISTS issue_interpretation VARCHAR(16);

COMMENT ON COLUMN routage_logs.commande_interpretee IS
    '[US-172 / CA18] Commande et sous-commande retenues par l''interpréteur. '
    'NULL = demande non passée par l''interpréteur.';
COMMENT ON COLUMN routage_logs.issue_interpretation IS
    '[US-172 / CA18] proposee | confirmee | refusee | abandonnee. '
    'NULL = demande non passée par l''interpréteur.';

COMMIT;

-- ── Contrôles post-migration ────────────────────────────────────────────────
-- Les deux colonnes existent et sont nullables. Attendu : 2 lignes, is_nullable = YES.
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'routage_logs'
  AND column_name IN ('commande_interpretee', 'issue_interpretation')
ORDER BY column_name;

-- Aucune ligne existante n'a été touchée : tout l'historique de routage porte
-- NULL sur ces deux colonnes. Attendu : 0.
SELECT COUNT(*) AS lignes_deja_renseignees
FROM routage_logs
WHERE commande_interpretee IS NOT NULL OR issue_interpretation IS NOT NULL;
