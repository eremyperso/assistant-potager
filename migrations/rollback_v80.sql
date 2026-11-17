-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v80.sql — annule migration_v80.sql [US-317]
-- ═════════════════════════════════════════════════════════════════════════════
-- Perd la trace des bilans envoyés : si les interrupteurs sont allumés, le résumé du jour peut repartir.
-- Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP TABLE IF EXISTS bilans_pilotage;

COMMIT;
