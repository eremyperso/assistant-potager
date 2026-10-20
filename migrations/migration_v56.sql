-- =============================================================================
-- migration_v56.sql — Ensoleillement d'une parcelle (US-239)
-- =============================================================================
-- [CA1] `parcelles.ensoleillement` : « plein soleil », « mi-ombre » ou « ombre »
--       (vocabulaire d'US-161), NULL = non renseigné. Le vocabulaire est validé
--       au point d'écriture (`utils.parcelles.normaliser_ensoleillement`), comme
--       `culture_config.exposition` : pas de CHECK SQL, une décision produit
--       révisable.
-- [CA2] Aucune conversion : `parcelles.exposition` (orientation, texte libre)
--       est conservée telle quelle, et les parcelles existantes ont un
--       ensoleillement NULL — traduire « Sud » en « plein soleil » serait une
--       donnée supposée.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v56.sql
-- =============================================================================

BEGIN;

ALTER TABLE parcelles
    ADD COLUMN IF NOT EXISTS ensoleillement VARCHAR(16);

COMMIT;
