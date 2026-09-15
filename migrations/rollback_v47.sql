-- =============================================================================
-- rollback_v47.sql — Annule migration_v47.sql (contexte du semis, US-069)
-- =============================================================================
-- Retire la contrainte puis la colonne `evenements.contexte_semis`.
--
-- Perte :
--   • les contextes DICTÉS, CONFIRMÉS ou CORRIGÉS par les jardiniers — ils ne se
--     reconstituent pas (seule la reprise « godet chaîné → pépinière » est
--     rejouable) : exporter la colonne avant si elle doit être conservée.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `app/services/contexte_semis.py`, les points d'écriture de
-- `app/services/evenements.py`, la confirmation et `/stats` de `bot.py`, et la
-- clé `semis_par_contexte` de `GET /stats` dans `main.py`.
-- =============================================================================

BEGIN;

ALTER TABLE evenements
    DROP CONSTRAINT IF EXISTS ck_evenements_contexte_semis_semis_seul;

ALTER TABLE evenements
    DROP COLUMN IF EXISTS contexte_semis;

COMMIT;
