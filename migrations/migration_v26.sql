-- =============================================================================
-- migration_v26.sql — Localisation du potager par ville (US-074)
-- =============================================================================
-- Ajoute la colonne `ville` (libellé affichable, ex. "Vitry-sur-Seine") sur
-- `potagers`, choisie via le module de recherche de ville unifié (géocodage
-- Open-Meteo côté frontend). `latitude`/`longitude` existent déjà depuis le
-- socle multi-tenant (US-040) — cette migration ne les touche pas.
--
-- Idempotent : IF NOT EXISTS sur l'ajout de colonne.
-- Rollback : migrations/rollback_v26.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE potagers ADD COLUMN IF NOT EXISTS ville VARCHAR(255);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'potagers'
  AND column_name = 'ville';
