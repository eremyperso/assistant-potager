-- =============================================================================
-- rollback_v63.sql — Annule migration_v63 (US-279)
-- =============================================================================
-- Retire l'empreinte des copies personnalisées : chaque copie se compare de
-- nouveau valeur par valeur au partagé, et un « Garder ma version » est oublié.
-- Aucun calendrier n'est perdu. Idempotent.
-- =============================================================================

BEGIN;

ALTER TABLE itineraire_cultural DROP COLUMN IF EXISTS empreinte_reference;

COMMIT;
