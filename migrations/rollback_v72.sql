-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v72.sql — annule migration_v72.sql [US-303]
-- ═════════════════════════════════════════════════════════════════════════════
-- Retire le résumé parlé des échanges : les lectures suivantes le recalculeront
-- (un appel de modèle par échange relu). Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation
    DROP COLUMN IF EXISTS texte_oral;

COMMIT;
