-- =============================================================================
-- migration_v54.sql — Pépinière chaude ou froide (US-208)
-- =============================================================================
-- `est_pepiniere` est un booléen : une mini-serre chauffante et un châssis froid
-- se valaient. La pépinière porte désormais un TYPE déclaré par le jardinier.
--
-- [CA1] `parcelles.type_pepiniere` : 'chaude' | 'froide', NULLABLE.
--       NULL = « type non renseigné », état à part entière.
--       AUCUN backfill : aucune pépinière existante n'est supposée chaude ou froide.
--       Une parcelle qui n'est pas pépinière n'a jamais de type (CHECK).
--
-- ⚠️ Ce n'est PAS `parcelles.abri` (v49, US-181), qui module la confiance des
--    cultures EN PLACE. « Chaude » = chauffée ou à l'intérieur, pas « au soleil ».
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : ADD COLUMN IF NOT EXISTS + contrainte créée si absente.
-- Rollback : migrations/rollback_v54.sql
-- =============================================================================

BEGIN;

ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS type_pepiniere VARCHAR(8);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_parcelles_type_pepiniere'
    ) THEN
        ALTER TABLE parcelles
            ADD CONSTRAINT ck_parcelles_type_pepiniere
            CHECK (type_pepiniere IS NULL
                   OR (est_pepiniere AND type_pepiniere IN ('chaude', 'froide')));
    END IF;
END
$$;

COMMIT;
