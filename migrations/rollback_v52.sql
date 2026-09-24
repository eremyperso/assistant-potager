-- =============================================================================
-- rollback_v52.sql — Annule migration_v52.sql (nombre de rangs, US-197)
-- =============================================================================
-- Retire `parcelles.nb_rangs` et sa contrainte de bornes.
--
-- Perte : les nombres de rangs déclarés par le jardinier. La Vue plan
-- (US-200) retombe sur l'absence de dénominateur — « non renseigné » partout.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `utils/parcelles.py`,
-- `app/services/interpreteur_commandes.py`, `GET /plan` dans `main.py`.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS ck_parcelles_nb_rangs;
ALTER TABLE parcelles DROP COLUMN IF EXISTS nb_rangs;

COMMIT;
