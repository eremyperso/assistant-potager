-- =============================================================================
-- migration_v23.sql — Unicité de parcelles.nom_normalise PAR POTAGER (bug fix)
-- =============================================================================
-- [Bug multi-tenant] La contrainte UNIQUE sur parcelles.nom_normalise était
-- globale (toutes potagers confondus) alors que toute la logique applicative
-- (utils/parcelles.py : find_doublon, create_parcelle, update_parcelle,
-- rename_parcelle) scope déjà ses vérifications de doublon par potager_id.
-- Conséquence : dès que deux potagers différents ont chacun une parcelle du
-- même nom (ex. "planche-tomate"), la création de la seconde échoue en base
-- avec une UniqueViolation alors que la logique applicative l'autorisait.
--
-- Remplace la contrainte UNIQUE(nom_normalise) seule par une contrainte
-- composite UNIQUE(potager_id, nom_normalise).
--
-- Prérequis : migration_v17.sql (potager_id NOT NULL sur parcelles).
--
-- Idempotent : DROP CONSTRAINT IF EXISTS + DO $$ ... $$ vérifiant pg_constraint
-- avant l'ADD CONSTRAINT (PostgreSQL ne supporte pas ADD CONSTRAINT IF NOT EXISTS).
-- Rollback : migrations/rollback_v23.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS parcelles_nom_normalise_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_parcelles_potager_nom_normalise'
    ) THEN
        ALTER TABLE parcelles
            ADD CONSTRAINT uq_parcelles_potager_nom_normalise UNIQUE (potager_id, nom_normalise);
    END IF;
END $$;

COMMIT;

-- Vérification post-migration
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'parcelles'::regclass;
