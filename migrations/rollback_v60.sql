-- =============================================================================
-- rollback_v60.sql — Annule migration_v60 (US-258)
-- =============================================================================
-- Retire le profil d'échange de `potager_membres` : prénoms et registres sont
-- perdus, le compagnon redemande au prochain échange. Idempotent.
-- =============================================================================

BEGIN;

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_registre_compagnon;
ALTER TABLE potager_membres
    DROP COLUMN IF EXISTS prenom_compagnon,
    DROP COLUMN IF EXISTS registre_compagnon,
    DROP COLUMN IF EXISTS compagnon_accueilli;

COMMIT;
