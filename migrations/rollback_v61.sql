-- =============================================================================
-- rollback_v61.sql — Annule migration_v61.sql (US-259)
-- =============================================================================
-- ⚠️ Perte de données : les échanges de conversation et les propositions de
-- conversation (natures commande et plan) sont supprimés. Les gestes de la file
-- d'US-224 sont rendus à `gestes_intentions`, avec leurs anciens états.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS echanges_conversation;

DELETE FROM propositions WHERE nature <> 'geste';

ALTER TABLE propositions DROP CONSTRAINT IF EXISTS ck_propositions_etat;
ALTER TABLE propositions DROP CONSTRAINT IF EXISTS ck_propositions_nature;
DROP INDEX IF EXISTS ix_propositions_conversation;

UPDATE propositions SET etat = 'confirme'  WHERE etat = 'confirmee';
UPDATE propositions SET etat = 'abandonne' WHERE etat IN ('abandonnee', 'remplacee');
UPDATE propositions SET etat = 'perime'    WHERE etat = 'perimee';

ALTER TABLE propositions
    DROP COLUMN IF EXISTS remplacee_par_id,
    DROP COLUMN IF EXISTS notifiee,
    DROP COLUMN IF EXISTS canal,
    DROP COLUMN IF EXISTS nature;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'propositions' AND column_name = 'contenu'
    ) THEN
        ALTER TABLE propositions RENAME COLUMN contenu TO geste;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_policy WHERE polname = 'tenant_isolation_propositions') THEN
        ALTER POLICY tenant_isolation_propositions ON propositions
            RENAME TO tenant_isolation_gestes_intentions;
    END IF;
    IF to_regclass('public.propositions') IS NOT NULL
       AND to_regclass('public.gestes_intentions') IS NULL THEN
        ALTER INDEX IF EXISTS ix_propositions_expire_le  RENAME TO ix_gestes_intentions_expire_le;
        ALTER INDEX IF EXISTS ix_propositions_potager_id RENAME TO ix_gestes_intentions_potager_id;
        ALTER INDEX IF EXISTS ix_propositions_user_etat  RENAME TO ix_gestes_intentions_user_etat;
        ALTER SEQUENCE IF EXISTS propositions_id_seq RENAME TO gestes_intentions_id_seq;
        ALTER TABLE propositions RENAME TO gestes_intentions;
    END IF;
END $$;

COMMIT;
