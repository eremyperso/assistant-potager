-- =============================================================================
-- migration_v24.sql — Vérification d'e-mail à l'inscription (US-044 / CA9-CA12)
-- =============================================================================
-- Ajoute les colonnes de token de vérification sur `users` (envoi via API
-- Brevo, cf. app/services/email.py) : hash du token (jamais la valeur brute),
-- expiration (24h) et horodatage d'usage (usage unique, même pattern que
-- liaisons_telegram.utilise_le en US-045).
--
-- Grandfathering : les comptes web déjà inscrits AVANT cette migration ont
-- email_verifie=false par défaut depuis migration_v19 (colonne réservée à
-- cette US mais pas encore exploitée). Il serait abusif de bloquer leur
-- prochaine connexion sans action de leur part alors que cette contrainte
-- n'existait pas à leur inscription — on les réputes donc vérifiés.
-- Seuls les comptes créés APRÈS cette migration devront vérifier leur e-mail
-- avant de pouvoir se connecter (cf. CA11 dans main.py::auth_login).
--
-- Idempotent : IF NOT EXISTS sur l'ajout de colonnes ; l'UPDATE de backfill
-- ne touche que les comptes web encore non vérifiés (rejouable sans effet de
-- bord, y compris sur des comptes vérifiés entre-temps par le vrai flux).
-- Rollback : migrations/rollback_v24.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expire_le TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_utilise_le TIMESTAMP;

-- Grandfathering : les comptes web existants (mot de passe déjà défini) sont
-- réputés vérifiés — ils se sont inscrits avant l'existence de cette contrainte.
UPDATE users
SET email_verifie = true
WHERE mot_de_passe_hash IS NOT NULL
  AND email_verifie = false;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('verification_token_hash', 'verification_token_expire_le', 'verification_token_utilise_le');
