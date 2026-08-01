-- =============================================================================
-- rollback_v24.sql — Annule migration_v24.sql (vérification d'e-mail sur users)
-- =============================================================================
-- Supprime les colonnes de token de vérification. Les comptes non encore
-- vérifiés perdent leur token en cours (ils devront en redemander un via
-- /auth/resend-verification après réapplication de la migration) — aucune
-- autre donnée n'est affectée. Le flag email_verifie n'est pas remis à false
-- (pas de retour en arrière utile sans l'infra de token pour le régénérer).
-- =============================================================================

BEGIN;

ALTER TABLE users DROP COLUMN IF EXISTS verification_token_hash;
ALTER TABLE users DROP COLUMN IF EXISTS verification_token_expire_le;
ALTER TABLE users DROP COLUMN IF EXISTS verification_token_utilise_le;

COMMIT;
