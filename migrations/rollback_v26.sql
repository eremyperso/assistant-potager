-- =============================================================================
-- rollback_v26.sql — Annule migration_v26.sql (localisation du potager)
-- =============================================================================
-- Supprime la colonne `ville`. Les potagers déjà localisés perdent leur
-- libellé de ville (latitude/longitude, posées avant cette migration,
-- restent inchangées).
-- =============================================================================

BEGIN;

ALTER TABLE potagers DROP COLUMN IF EXISTS ville;

COMMIT;
