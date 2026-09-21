-- =============================================================================
-- rollback_v50.sql — Annule migration_v50.sql (intentions de geste, US-196)
-- =============================================================================
-- Retire la table `gestes_intentions` et sa policy RLS.
--
-- Perte : les intentions en cours (au plus 15 minutes de préparations non
-- confirmées). Aucun événement n'est concerné — une intention n'a jamais rien
-- écrit : c'est toute sa raison d'être. Le bouton « Enregistrer » de la fiche
-- calendrier redevient absent, exactement comme avant US-196 (US-183 / CA6).
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette table : `database/models.py` (GesteIntention),
-- `app/services/intentions_geste.py`, `POST /gestes/intentions` dans
-- `app/api/main.py`, `app/bot/geste_prerempli.py`.
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_gestes_intentions ON gestes_intentions;
DROP TABLE IF EXISTS gestes_intentions;

COMMIT;
