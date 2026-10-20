-- =============================================================================
-- rollback_v56.sql — Annule migration_v56.sql (ensoleillement, US-239)
-- =============================================================================
-- Retire `parcelles.ensoleillement`. Perte : les ensoleillements déclarés ; les
-- orientations (`exposition`) ne sont pas touchées.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `utils/parcelles.py`, `GET /plan`,
-- `PATCH /parcelles/{id}` et `app/services/echeances_lots.py`.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP COLUMN IF EXISTS ensoleillement;

COMMIT;
