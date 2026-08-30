-- =============================================================================
-- rollback_v34.sql — Annule migration_v34.sql (origine du parsing, US-094)
-- =============================================================================
-- Supprime `evenements.origine_parsing` et son index partiel.
--
-- Sans perte fonctionnelle : la colonne est de l'instrumentation pure, aucune
-- condition métier, aucun gabarit ni message utilisateur ne la lit. La seule
-- chose perdue est la mesure de couverture réelle du parseur déterministe sur
-- la période écoulée — elle n'est pas reconstituable a posteriori, puisque le
-- chemin emprunté n'est écrit nulle part ailleurs.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_evenements_origine_parsing;

ALTER TABLE evenements
    DROP COLUMN IF EXISTS origine_parsing;

COMMIT;
