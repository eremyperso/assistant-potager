-- =============================================================================
-- rollback_v17.sql — Annule migration_v17.sql (potager_id NOT NULL)
-- =============================================================================
-- [US-042] Repasse potager_id en NULLABLE sur evenements et parcelles.
-- Aucune donnée n'est perdue (les valeurs existantes sont conservées, seule
-- la contrainte NOT NULL est levée).
--
-- Exécution :
--   psql -U potager_user -d potager_dev -h localhost -f migrations/rollback_v17.sql
-- =============================================================================

BEGIN;

ALTER TABLE evenements ALTER COLUMN potager_id DROP NOT NULL;
ALTER TABLE parcelles  ALTER COLUMN potager_id DROP NOT NULL;

COMMIT;
