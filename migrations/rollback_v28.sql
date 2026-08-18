-- =============================================================================
-- rollback_v28.sql — Annule migration_v28.sql (type de sol de la parcelle)
-- =============================================================================
-- Supprime la colonne `type_sol`. Purement informative — aucune donnée de
-- calcul (stock, plan) ne dépend d'elle.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP COLUMN IF EXISTS type_sol;

COMMIT;
