-- =============================================================================
-- rollback_v58.sql — Annule migration_v58.sql (pépinière d'origine, US-241)
-- =============================================================================
-- Retire `evenements.parcelle_origine_id`.
--
-- Perte : l'origine de chaque déplacement chiffré et de chaque sortie d'un lot
-- réparti. Les gestes eux-mêmes sont conservés ; sans la colonne, la répartition
-- d'un lot coupé entre deux pépinières ne peut plus être recalculée.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette colonne : `database/models.py`, `app/services/evenements.py`,
-- `utils/stock.py`. Un déplacement chiffré enregistré entre-temps doit d'abord être
-- corrigé (quantité retirée) ou supprimé : la version précédente le refuse.
-- =============================================================================

BEGIN;

ALTER TABLE evenements DROP COLUMN IF EXISTS parcelle_origine_id;

COMMIT;
