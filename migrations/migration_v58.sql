-- =============================================================================
-- migration_v58.sql — Pépinière d'origine d'un geste de lot réparti (US-241)
-- =============================================================================
-- US-241 ouvre le déplacement PARTIEL d'un lot : « passé 6 godets du lot 21 au
-- châssis froid ». La quantité tient dans `evenements.quantite`, la destination dans
-- `parcelle_id`, le lot dans `origine_graines_id`. Reste l'ORIGINE : une fois le lot
-- coupé entre deux pépinières, il faut savoir d'où les godets partent, et d'où une
-- plantation, une perte ou une vente les retire (CA3, CA9). Elle ne se déduit pas :
-- le jardinier la dit, ou la choisit par boutons.
--
-- [CA3, CA9] `evenements.parcelle_origine_id` : entier NULLABLE, clé vers `parcelles`.
--       - déplacement chiffré : la pépinière d'où partent les godets ; NULL = godets
--         dont l'emplacement n'a jamais été renseigné (US-210 / CA5) ;
--       - plantation, perte de godet, vente d'un lot réparti : la pépinière d'où
--         viennent les godets ; NULL = non dite (repli du calcul, voir
--         docs/domaines/pepiniere.md) ;
--       - tout autre geste : NULL.
--       ON DELETE SET NULL : supprimer une pépinière ne supprime aucun geste.
--       Aucun backfill : aucun déplacement chiffré n'existait avant cette migration
--       (US-211 les refusait).
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v58.sql
-- =============================================================================

BEGIN;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS parcelle_origine_id INTEGER
    REFERENCES parcelles(id) ON DELETE SET NULL;

COMMENT ON COLUMN evenements.parcelle_origine_id IS
    '[US-241] Pépinière d''où partent les godets d''un déplacement chiffré, ou d''où une '
    'plantation, une perte ou une vente les retire quand le lot est réparti. NULL sinon.';

COMMIT;
