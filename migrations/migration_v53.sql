-- =============================================================================
-- migration_v53.sql — Longueur d'une parcelle (US-225)
-- =============================================================================
-- Le rang n'est plus un trait de longueur relative : c'est une PISTE DE PLACES,
-- et compter des places suppose une longueur. Cette longueur est une propriété
-- de la PARCELLE, pas du rang : une planche a une longueur unique, et tous ses
-- rangs la partagent. D'où `parcelles.longueur_m`, et non `longueur_rang_m`.
--
-- [CA1] `parcelles.longueur_m` : NUMERIC(5,1), 0,5 à 200 mètres, NULLABLE.
--       NULL = « non renseignée », ce qui n'est PAS « zéro mètre ».
--       AUCUN backfill : la longueur ne se déduit jamais de la superficie.
--
-- ⚠️ La LARGEUR ne se déclare pas et ne se stocke pas : elle se déduit à la
--    lecture (`superficie_m2 ÷ longueur_m`, `utils.parcelles.largeur_deduite`)
--    et ne sert qu'à l'affichage, comme repère de cohérence. Aucune colonne.
--
-- Comme la borne 1–99 de `nb_rangs` (v52), les bornes 0,5–200 sont une
-- propriété stable du domaine : elles sont posées en CHECK SQL, qui les
-- garantit à toute écriture, migration comprise, et revalidées au point
-- d'écriture Python (`utils.parcelles.update_parcelle`) que SQLite ne porte pas.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : ADD COLUMN IF NOT EXISTS + contrainte créée si absente.
-- Rollback : migrations/rollback_v53.sql
-- =============================================================================

BEGIN;

ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS longueur_m NUMERIC(5,1);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_parcelles_longueur_m'
    ) THEN
        ALTER TABLE parcelles
            ADD CONSTRAINT ck_parcelles_longueur_m
            CHECK (longueur_m IS NULL OR (longueur_m BETWEEN 0.5 AND 200));
    END IF;
END
$$;

COMMIT;
