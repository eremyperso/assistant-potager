-- =============================================================================
-- rollback_v23.sql — Annule migration_v23.sql (unicité parcelles.nom_normalise)
-- =============================================================================
-- Restaure la contrainte UNIQUE(nom_normalise) globale — échouera si, entre
-- temps, deux potagers différents partagent un nom_normalise identique
-- (c'est justement le cas que migration_v23 est censée permettre).
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS uq_parcelles_potager_nom_normalise;
ALTER TABLE parcelles ADD CONSTRAINT parcelles_nom_normalise_key UNIQUE (nom_normalise);

COMMIT;
