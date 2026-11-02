-- =============================================================================
-- rollback_v65.sql — Annule les signaux du veilleur et les rappels (US-266)
-- =============================================================================
-- ⚠️ Perd les signaux détectés et les rappels programmés.
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_rappels ON rappels;
DROP TABLE IF EXISTS rappels;

DROP POLICY IF EXISTS tenant_isolation_signaux ON signaux;
DROP TABLE IF EXISTS signaux;

COMMIT;
