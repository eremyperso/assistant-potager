-- =============================================================================
-- rollback_v67.sql — Annule la question en attente du compagnon (US-284)
-- =============================================================================
-- ⚠️ Perd les questions en attente (10 minutes de vie au plus) : une réponse
-- courte redevient une phrase sans contexte.
-- =============================================================================

BEGIN;

ALTER TABLE echanges_conversation DROP COLUMN IF EXISTS question;

COMMIT;
