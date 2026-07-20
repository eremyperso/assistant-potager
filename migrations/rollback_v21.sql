-- =============================================================================
-- rollback_v21.sql — Annule migration_v21.sql (users.potager_actif_id)
-- =============================================================================
-- [US-046] Supprime la colonne de potager actif. Le TenantContext retombe
-- alors sur DEFAULT_POTAGER_ID (potager #1) pour tout le monde, comme avant
-- US-046 — aucune donnée métier (evenements, parcelles) n'est affectée.
-- =============================================================================

BEGIN;

ALTER TABLE users DROP COLUMN IF EXISTS potager_actif_id;

COMMIT;
