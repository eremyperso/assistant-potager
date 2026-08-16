-- =============================================================================
-- migration_v19.sql — Credentials web (auth JWT) sur la table users
-- =============================================================================
-- [US-044] Ajoute les colonnes nécessaires à l'authentification web par
-- e-mail / mot de passe, distincte de l'identité Telegram (US-045).
--
-- mot_de_passe_hash : hash argon2/bcrypt (jamais le mot de passe en clair).
-- email_verifie     : réservé à une future US de vérification d'e-mail
--                      (hors périmètre US-044) — vaut false par défaut.
--
-- Idempotent : IF NOT EXISTS sur l'ajout de colonnes.
-- Rollback : migrations/rollback_v19.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS mot_de_passe_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verifie BOOLEAN NOT NULL DEFAULT false;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'users' AND column_name IN ('mot_de_passe_hash', 'email_verifie');
