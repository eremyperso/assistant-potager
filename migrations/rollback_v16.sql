-- =============================================================================
-- rollback_v16.sql — Annule migration_v16.sql (socle multi-tenant)
-- =============================================================================
-- [US-040 / CA9] Supprime colonnes, index et tables dans l'ordre inverse des
-- dépendances FK. Ramène la base à son état fonctionnel équivalent à avant
-- v16 (aucune donnée métier existante n'est perdue, seul potager_id
-- disparaît).
--
-- Exécution :
--   psql -U potager_user -d potager -f rollback_v16.sql
-- =============================================================================

BEGIN;

-- [1] Index
DROP INDEX IF EXISTS idx_evenements_potager_date;
DROP INDEX IF EXISTS idx_parcelles_potager;
DROP INDEX IF EXISTS idx_culture_config_potager;

-- [2] Colonnes potager_id sur les tables métier
ALTER TABLE evenements     DROP COLUMN IF EXISTS potager_id;
ALTER TABLE parcelles      DROP COLUMN IF EXISTS potager_id;
ALTER TABLE culture_config DROP COLUMN IF EXISTS potager_id;

-- [3] Tables tenant, dans l'ordre inverse des FK
DROP TABLE IF EXISTS potager_membres;
DROP TABLE IF EXISTS potagers;
DROP TABLE IF EXISTS users;

COMMIT;
