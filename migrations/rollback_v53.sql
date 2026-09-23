-- =============================================================================
-- rollback_v53.sql — Annule migration_v53.sql (longueur d'une parcelle, US-225)
-- =============================================================================
-- Retire `parcelles.longueur_m` et sa contrainte de bornes.
--
-- Perte : les longueurs déclarées par le jardinier. Le compte de places d'un
-- rang (US-227) et la piste des places (US-228) retombent sur « longueur non
-- renseignée » partout, et la largeur déduite disparaît de `GET /plan`.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `utils/parcelles.py`,
-- `app/services/interpreteur_commandes.py`, `GET /plan` dans `main.py`.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS ck_parcelles_longueur_m;
ALTER TABLE parcelles DROP COLUMN IF EXISTS longueur_m;

COMMIT;
