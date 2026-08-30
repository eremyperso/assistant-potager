-- =============================================================================
-- rollback_v35.sql — Annule migration_v35.sql (origine de la date, US-169)
-- =============================================================================
-- Supprime `evenements.date_source` et son index partiel.
--
-- Sans perte fonctionnelle : la colonne est de l'instrumentation pure, aucune
-- condition métier, aucun gabarit ni message utilisateur ne la lit. La seule
-- chose perdue est la mesure du dénominateur nécessaire au taux de correction
-- réel des dates (CA11/CA12) — elle n'est pas reconstituable a posteriori,
-- puisque l'origine de l'ancrage n'est écrite nulle part ailleurs.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_evenements_date_source;

ALTER TABLE evenements
    DROP COLUMN IF EXISTS date_source;

COMMIT;
