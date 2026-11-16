-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v74.sql — annule migration_v74.sql [US-307]
-- ═════════════════════════════════════════════════════════════════════════════
-- Retire l'identifiant d'échange, le canal, la version et l'unité. Les sommes de
-- tokens_in mélangent de nouveau jetons, secondes et caractères. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS ix_echanges_conversation_echange_ref;
ALTER TABLE echanges_conversation DROP COLUMN IF EXISTS echange_ref;

DROP INDEX IF EXISTS ix_conso_tokens_echange_ref;
ALTER TABLE conso_tokens DROP CONSTRAINT IF EXISTS ck_conso_tokens_unite;
ALTER TABLE conso_tokens DROP CONSTRAINT IF EXISTS ck_conso_tokens_canal;
ALTER TABLE conso_tokens
    DROP COLUMN IF EXISTS unite,
    DROP COLUMN IF EXISTS version_app,
    DROP COLUMN IF EXISTS canal,
    DROP COLUMN IF EXISTS echange_ref;

COMMIT;
