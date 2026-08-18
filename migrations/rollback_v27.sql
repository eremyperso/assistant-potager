-- =============================================================================
-- rollback_v27.sql — Annule migration_v27.sql (procédure supprimer_utilisateur)
-- =============================================================================

BEGIN;

DROP PROCEDURE IF EXISTS supprimer_utilisateur(integer);

COMMIT;
