-- =============================================================================
-- rollback_v70.sql — Annule migration_v70.sql (US-294)
-- Perd le réglage « assistants externes interdits » (les assistants redeviennent
-- autorisés partout où ils étaient consentis) et le lien appel → geste.
-- =============================================================================

BEGIN;

ALTER TABLE mcp_appels DROP COLUMN IF EXISTS evenement_id;
ALTER TABLE potagers   DROP COLUMN IF EXISTS assistants_externes_interdits;

COMMIT;
