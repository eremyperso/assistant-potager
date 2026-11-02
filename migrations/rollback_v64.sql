-- =============================================================================
-- rollback_v64.sql — Annule le carnet du compagnon (US-265)
-- =============================================================================
-- ⚠️ Perd les faits du carnet, les niveaux et les objectifs de saison.
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_carnet_faits ON carnet_faits;
DROP TABLE IF EXISTS carnet_faits;

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_niveau_compagnon;
ALTER TABLE potager_membres
    DROP COLUMN IF EXISTS niveau_compagnon,
    DROP COLUMN IF EXISTS objectifs_saison;

COMMIT;
