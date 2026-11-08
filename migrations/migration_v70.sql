-- =============================================================================
-- migration_v70.sql — Voir et révoquer les assistants IA connectés (US-294)
-- =============================================================================
-- Deux colonnes, rien d'autre (le reste de l'écran vient des tables d'US-290) :
--
--   potagers.assistants_externes_interdits   le propriétaire interdit les assistants
--       externes pour CE potager (CA6, décision D6). Les connexions existantes perdent
--       l'accès à ce potager dès l'appel suivant, la page de consentement ne le
--       propose plus. FAUX par défaut : aucun potager existant ne change de comportement.
--   mcp_appels.evenement_id                  le geste écrit par un appel confirmé
--       (`confirmer_proposition`), pour que « Activité » renvoie vers le Journal (CA3).
--       Sans clé étrangère : un geste supprimé laisse la trace de l'appel intacte.
--
-- Additive, aucun backfill. Idempotent. À exécuter avec le rôle propriétaire.
-- Rollback : migrations/rollback_v70.sql
-- =============================================================================

BEGIN;

ALTER TABLE potagers
    ADD COLUMN IF NOT EXISTS assistants_externes_interdits BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE mcp_appels
    ADD COLUMN IF NOT EXISTS evenement_id INTEGER NULL;

COMMENT ON COLUMN potagers.assistants_externes_interdits IS
    'US-294/CA6 — vrai : aucun assistant IA externe (MCP) ne lit ni n''écrit dans ce potager.';
COMMENT ON COLUMN mcp_appels.evenement_id IS
    'US-294/CA3 — le geste écrit par un appel confirmé ; sans clé étrangère (le geste peut disparaître).';

COMMIT;
