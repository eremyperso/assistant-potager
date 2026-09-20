-- =============================================================================
-- rollback_v49.sql — Annule migration_v49.sql (abri et paillage, US-181)
-- =============================================================================
-- Retire `parcelles.abri` et `parcelles.paillage`.
--
-- Perte : les déclarations d'abri et de paillage. Le moteur de confiance
-- retombe sur le comportement d'US-178 (aucune règle modulée).
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces colonnes : `database/models.py`, `utils/parcelles.py`,
-- `app/services/confiance_semis.py`, `GET /plan` dans `main.py`.
-- =============================================================================

BEGIN;

ALTER TABLE parcelles DROP COLUMN IF EXISTS paillage;
ALTER TABLE parcelles DROP COLUMN IF EXISTS abri;

COMMIT;
