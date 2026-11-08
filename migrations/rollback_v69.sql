-- =============================================================================
-- rollback_v69.sql — Annule migration_v69.sql (US-290, canal MCP)
-- Perd les connecteurs, jetons, codes et le journal des appels MCP : chaque
-- assistant connecté devra se reconnecter.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS mcp_appels;
DROP TABLE IF EXISTS mcp_codes_autorisation;
DROP TABLE IF EXISTS mcp_jetons;
DROP TABLE IF EXISTS mcp_autorisations;
DROP TABLE IF EXISTS mcp_clients;

COMMIT;
