-- =============================================================================
-- migration_v8.sql — Ajout colonnes espacement et surface_m2 sur culture_config
-- =============================================================================
-- Prérequis de migration_v13.sql : ces colonnes doivent exister avant l'INSERT.
-- Idempotent : ADD COLUMN IF NOT EXISTS
-- =============================================================================

ALTER TABLE culture_config ADD COLUMN IF NOT EXISTS espacement  VARCHAR;
ALTER TABLE culture_config ADD COLUMN IF NOT EXISTS surface_m2  DOUBLE PRECISION;

-- Vérification
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'culture_config'
  AND column_name IN ('espacement', 'surface_m2')
ORDER BY column_name;
