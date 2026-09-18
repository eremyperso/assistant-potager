-- =============================================================================
-- rollback_v48.sql — Annule migration_v48.sql (altitude du potager, US-193)
-- =============================================================================
-- Retire la colonne `potagers.altitude`.
--
-- Perte :
--   • les altitudes enregistrées — elles se reconstituent en rejouant
--     migration_v48.sql puis tools/renseigner_altitude_potagers.py.
--   • les potagers de montagne sans zone choisie reviennent à la zone déduite
--     de la seule position (jamais « montagnard »).
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `app/services/potagers.py`,
-- `app/services/calendrier_cultural.py`, `POST`/`PATCH /potagers` dans `main.py`.
-- =============================================================================

BEGIN;

ALTER TABLE potagers
    DROP COLUMN IF EXISTS altitude;

COMMIT;
