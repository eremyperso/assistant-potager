-- =============================================================================
-- migration_v25.sql — Réinitialisation du mot de passe oublié (US-057)
-- =============================================================================
-- Ajoute les colonnes de token de réinitialisation sur `users` (envoi via API
-- Brevo, cf. app/services/email.py) : hash du token (jamais la valeur brute),
-- expiration (1h) et horodatage d'usage (usage unique) — même pattern que
-- verification_token_* introduit par migration_v24.sql (US-044).
--
-- Idempotent : IF NOT EXISTS sur l'ajout de colonnes.
-- Rollback : migrations/rollback_v25.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_mdp_token_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_mdp_token_expire_le TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_mdp_token_utilise_le TIMESTAMP;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('reset_mdp_token_hash', 'reset_mdp_token_expire_le', 'reset_mdp_token_utilise_le');
