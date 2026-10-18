-- =============================================================================
-- migration_v57.sql — Levée d'un lot de semis déclarée terminée (US-212)
-- =============================================================================
-- Le geste « levée » compte les graines levées d'un lot de pépinière. Le nombre de
-- levés tient dans `evenements.quantite`, le lot dans `origine_graines_id` : ni l'un
-- ni l'autre ne demande de colonne. Reste l'indication facultative « levée
-- TERMINÉE » (plus rien ne lèvera), qui clôt la germination du lot — il lui faut sa
-- place.
--
-- [CA1] `evenements.levee_terminee` : booléen NULLABLE. NULL pour tout geste autre
--       qu'une levée ; une levée encore en cours porte FALSE ou NULL (les deux se
--       lisent « pas terminée »). CHECK : seul un geste `levee` peut la porter.
--       Aucun backfill : aucune levée n'existait avant cette migration.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v57.sql
-- =============================================================================

BEGIN;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS levee_terminee BOOLEAN;

ALTER TABLE evenements
    DROP CONSTRAINT IF EXISTS ck_evenements_levee_terminee_levee_seule;
ALTER TABLE evenements
    ADD CONSTRAINT ck_evenements_levee_terminee_levee_seule
    CHECK (levee_terminee IS NULL OR type_action = 'levee');

COMMENT ON COLUMN evenements.levee_terminee IS
    '[US-212] Levée déclarée terminée : la germination du lot est close, les graines '
    'non levées sont soldées. NULL pour tout geste autre qu''une levée.';

COMMIT;
