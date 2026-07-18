-- =============================================================================
-- migration_v17.sql — potager_id NOT NULL sur les tables métier (US-042)
-- =============================================================================
-- [US-042 / CA4] Termine le scoping applicatif entamé par US-040 (socle) et
-- US-041 (couche services) : la colonne potager_id devient NOT NULL sur les
-- tables métier dont TOUTE ligne appartient nécessairement à un potager.
--
-- Tables passées NOT NULL :
--   - evenements  → backfillée à 100% par migration_v16.sql (potager #1)
--   - parcelles   → backfillée à 100% par migration_v16.sql (potager #1)
--
-- Table volontairement NON concernée par ce NOT NULL :
--   - culture_config → potager_id reste NULLABLE en permanence. Décision
--     documentée dès US-040 (voir migration_v16.sql §[4] et
--     database/models.py:CultureConfig) : NULL = fiche référentiel globale
--     partagée entre tous les potagers, non NULL = fiche personnalisée à un
--     potager. Passer cette colonne en NOT NULL casserait ce mécanisme de
--     fiches globales — ce n'est pas une omission, c'est un choix de modèle
--     de données antérieur à cette migration, sciemment reconduit ici malgré
--     la formulation générique de l'US ("evenements, culture_config (et
--     toute autre table métier)").
--
-- La migration ÉCHOUE explicitement (RAISE EXCEPTION, transaction annulée)
-- si une ligne potager_id IS NULL subsiste sur evenements ou parcelles —
-- jamais de passage NOT NULL silencieux sur une colonne encore incomplète.
--
-- Rollback : migrations/rollback_v17.sql
--
-- Exécution :
--   psql -U potager_user -d potager_dev -h localhost -f migrations/migration_v17.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- [1] Garde-fou — échec explicite si le backfill US-040 n'est pas complet.
DO $$
DECLARE
    nb_evenements_null INTEGER;
    nb_parcelles_null  INTEGER;
BEGIN
    SELECT count(*) INTO nb_evenements_null FROM evenements WHERE potager_id IS NULL;
    SELECT count(*) INTO nb_parcelles_null  FROM parcelles  WHERE potager_id IS NULL;

    IF nb_evenements_null > 0 THEN
        RAISE EXCEPTION
            '[migration_v17] ABORT : % ligne(s) evenements.potager_id IS NULL — '
            'exécuter migration_v16.sql (backfill) avant de rejouer migration_v17.sql',
            nb_evenements_null;
    END IF;

    IF nb_parcelles_null > 0 THEN
        RAISE EXCEPTION
            '[migration_v17] ABORT : % ligne(s) parcelles.potager_id IS NULL — '
            'exécuter migration_v16.sql (backfill) avant de rejouer migration_v17.sql',
            nb_parcelles_null;
    END IF;
END $$;

-- [2] Passage NOT NULL
ALTER TABLE evenements ALTER COLUMN potager_id SET NOT NULL;
ALTER TABLE parcelles  ALTER COLUMN potager_id SET NOT NULL;

COMMIT;

-- [3] Vérification post-migration
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE table_name IN ('evenements', 'parcelles', 'culture_config')
  AND column_name = 'potager_id'
ORDER BY table_name;
