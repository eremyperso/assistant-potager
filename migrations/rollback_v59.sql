-- =============================================================================
-- rollback_v59.sql — Annule migration_v59 (US-235)
-- =============================================================================
-- Retire `routage_logs.outils_agent`. Les lignes de l'agent restent lisibles
-- par `origine_classification = 'agent'`, sans le nom des outils.
-- Idempotent.
-- =============================================================================

BEGIN;

ALTER TABLE routage_logs
    DROP COLUMN IF EXISTS outils_agent;

COMMIT;
