-- =============================================================================
-- rollback_v19.sql — Annule migration_v19.sql (credentials web sur users)
-- =============================================================================
-- [US-044] Supprime les colonnes de credentials web. Les comptes créés via
-- /auth/register perdent leur mot de passe (login web impossible ensuite) —
-- l'identité Telegram (telegram_chat_id) n'est pas affectée.
-- =============================================================================

BEGIN;

ALTER TABLE users DROP COLUMN IF EXISTS mot_de_passe_hash;
ALTER TABLE users DROP COLUMN IF EXISTS email_verifie;

COMMIT;
