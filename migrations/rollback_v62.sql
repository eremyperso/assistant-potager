-- =============================================================================
-- rollback_v62.sql — Annule migration_v62.sql (US-261, US-260)
-- =============================================================================
-- ⚠️ Perte de données : les actions menées sont supprimées avec leur table.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS actions_menees;

ALTER TABLE propositions DROP COLUMN IF EXISTS traite_canal;

COMMIT;
