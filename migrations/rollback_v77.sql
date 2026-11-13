-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v77.sql — annule migration_v77.sql [US-323]
-- ═════════════════════════════════════════════════════════════════════════════
-- Perd le contexte d'écran gardé avec les échanges ; aucune phrase, aucune réponse,
-- aucun geste n'est perdu. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation DROP COLUMN IF EXISTS contexte;

COMMIT;
