-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v78.sql — annule migration_v78.sql [US-310]
-- ═════════════════════════════════════════════════════════════════════════════
-- Ne perd aucune donnée : les lectures de pilotage deviennent seulement plus lentes. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS idx_conso_tokens_cree_le;
DROP INDEX IF EXISTS idx_conso_tokens_date_provenance;

COMMIT;
