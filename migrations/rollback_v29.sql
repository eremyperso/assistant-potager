-- =============================================================================
-- rollback_v29.sql — Annule migration_v29.sql (cycle de vie du potager, US-080)
-- =============================================================================
-- Supprime la contrainte, l'index et les trois colonnes d'état. Après rollback,
-- tout potager redevient implicitement « actif » : aucune donnée métier
-- (parcelles, événements, membres) n'est touchée — seuls les horodatages
-- d'archivage/suppression éventuels sont perdus.
-- =============================================================================

BEGIN;

ALTER TABLE potagers DROP CONSTRAINT IF EXISTS ck_potagers_etat;

DROP INDEX IF EXISTS idx_potagers_etat;

ALTER TABLE potagers DROP COLUMN IF EXISTS supprime_le;
ALTER TABLE potagers DROP COLUMN IF EXISTS archive_le;
ALTER TABLE potagers DROP COLUMN IF EXISTS etat;

COMMIT;
