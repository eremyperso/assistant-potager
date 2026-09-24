-- =============================================================================
-- migration_v52.sql — Nombre de rangs d'une parcelle (US-197)
-- =============================================================================
-- La Vue plan se lit en RANGS : « 13 rangs occupés sur 18 déclarés ». Ce
-- dénominateur n'existait nulle part — la parcelle ne portait que `nom`,
-- `superficie_m2`, `exposition`, `type_sol`, `ordre`, `est_pepiniere`.
--
-- [CA1] `parcelles.nb_rangs` : SMALLINT, entier de 1 à 99, NULLABLE.
--       NULL = « non renseigné », ce qui n'est PAS « zéro rang » : une planche
--       jamais déclarée n'est pas une planche sans place.
--       AUCUN backfill — aucune valeur n'est supposée pour l'existant.
--
-- ⚠️ Le « rang » d'un ÉVÉNEMENT (multiplicateur : « 4 salades sur 3 rangs »
--    = 12 plants) n'a aucun rapport avec cette colonne et ne la renseigne pas.
--
-- Contrairement à `parcelles.abri` (v49), dont le vocabulaire se révise en
-- Python, la borne 1–99 est une propriété stable du domaine : elle est donc
-- posée en CHECK SQL, qui la garantit à toute écriture, migration comprise.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : ADD COLUMN IF NOT EXISTS + contrainte créée si absente.
-- Rollback : migrations/rollback_v52.sql
-- =============================================================================

BEGIN;

ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS nb_rangs SMALLINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_parcelles_nb_rangs'
    ) THEN
        ALTER TABLE parcelles
            ADD CONSTRAINT ck_parcelles_nb_rangs
            CHECK (nb_rangs IS NULL OR (nb_rangs BETWEEN 1 AND 99));
    END IF;
END
$$;

COMMIT;
