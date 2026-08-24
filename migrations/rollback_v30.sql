-- =============================================================================
-- rollback_v30.sql — Annule migration_v30.sql (identité fédérée Google, US-090)
-- =============================================================================
-- Supprime l'index unique et la colonne `google_sub`. Après rollback, les
-- comptes créés via Google restent présents mais deviennent inconnectables tant
-- que la migration n'est pas rejouée : sans mot de passe et sans `sub`, aucune
-- méthode de connexion ne subsiste pour eux. Leur adresse e-mail reste toutefois
-- réservée — ne rejouer ce rollback qu'en connaissance de cause.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_users_google_sub;

ALTER TABLE users DROP COLUMN IF EXISTS google_sub;

COMMIT;
