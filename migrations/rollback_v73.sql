-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v73.sql — annule migration_v73.sql [US-306]
-- ═════════════════════════════════════════════════════════════════════════════
-- Retire la provenance : les lignes de mesure et de test se confondent de nouveau
-- avec l'usage. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE conso_tokens DROP CONSTRAINT IF EXISTS ck_conso_tokens_provenance;
ALTER TABLE conso_tokens DROP COLUMN IF EXISTS provenance;

COMMIT;
