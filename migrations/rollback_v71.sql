-- =============================================================================
-- rollback_v71.sql — Annule migration_v71.sql (US-300)
-- Perd le mode vocal, la voix choisie et la lecture automatique de chaque
-- jardinier : la PWA retombe sur les défauts (mode vocal éteint).
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS preferences_voix;

COMMIT;
