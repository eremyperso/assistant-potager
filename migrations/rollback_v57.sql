-- =============================================================================
-- rollback_v57.sql — Annule migration_v57.sql (levée terminée, US-212)
-- =============================================================================
-- Retire `evenements.levee_terminee` et sa contrainte.
--
-- Perte : l'indication « levée terminée » de chaque comptage. Les comptages eux-mêmes
-- (type_action = 'levee', quantite, origine_graines_id) sont conservés ; sans la
-- colonne, un lot dont la levée avait été déclarée terminée redevient « en cours ».
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `app/services/evenements.py`,
-- `utils/stock.py` et `GET /pepiniere/lots`.
-- =============================================================================

BEGIN;

ALTER TABLE evenements DROP CONSTRAINT IF EXISTS ck_evenements_levee_terminee_levee_seule;
ALTER TABLE evenements DROP COLUMN IF EXISTS levee_terminee;

COMMIT;
