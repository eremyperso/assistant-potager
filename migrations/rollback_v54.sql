-- =============================================================================
-- rollback_v54.sql — Annule migration_v54.sql (pépinière chaude ou froide, US-208)
-- =============================================================================
-- Retire `parcelles.type_pepiniere` et sa contrainte de cohérence.
--
-- Perte : les types de pépinière déclarés. Les pépinières restent pépinières
-- (`est_pepiniere` n'est pas touché) ; aucun calcul ne dépendait du type.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `utils/parcelles.py`,
-- `app/services/interpreteur_commandes.py`, `GET /plan` et `GET /pepiniere/lots`.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS ck_parcelles_type_pepiniere;
ALTER TABLE parcelles DROP COLUMN IF EXISTS type_pepiniere;

COMMIT;
