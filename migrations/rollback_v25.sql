-- =============================================================================
-- rollback_v25.sql — Annule migration_v25.sql (réinitialisation mot de passe)
-- =============================================================================
-- Supprime les colonnes de token de réinitialisation. Les liens de
-- réinitialisation en cours d'envoi deviennent invalides (l'utilisateur devra
-- en redemander un via /auth/mot-de-passe-oublie après réapplication de la
-- migration) — aucune autre donnée n'est affectée.
-- =============================================================================

BEGIN;

ALTER TABLE users DROP COLUMN IF EXISTS reset_mdp_token_hash;
ALTER TABLE users DROP COLUMN IF EXISTS reset_mdp_token_expire_le;
ALTER TABLE users DROP COLUMN IF EXISTS reset_mdp_token_utilise_le;

COMMIT;
