-- =============================================================================
-- migration_v20.sql — Codes de liaison Telegram ⇄ compte web (US-045)
-- =============================================================================
-- [US-045] Table des codes à usage unique permettant de rattacher un
-- telegram_chat_id à un compte web existant (users.id). Le code est généré
-- côté PWA (POST /auth/lien/generer-code, utilisateur authentifié) puis saisi
-- côté Telegram (/lier <code>).
--
-- code       : court, alphanumérique non ambigu (6-8 caractères), unique.
-- user_id    : compte web propriétaire du code.
-- cree_le    : horodatage de génération.
-- expire_le  : cree_le + 10 minutes (calculé côté application).
-- utilise_le : NULL tant que non consommé — usage strict à usage unique (CA4).
--
-- Idempotent : CREATE TABLE IF NOT EXISTS.
-- Rollback : migrations/rollback_v20.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS liaisons_telegram (
    id         SERIAL PRIMARY KEY,
    code       VARCHAR(8) NOT NULL UNIQUE,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    cree_le    TIMESTAMP NOT NULL DEFAULT now(),
    expire_le  TIMESTAMP NOT NULL,
    utilise_le TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_liaisons_telegram_code ON liaisons_telegram (code);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'liaisons_telegram'
ORDER BY ordinal_position;
