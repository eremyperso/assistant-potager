-- =============================================================================
-- rollback_v18.sql — Annule migration_v18.sql (RLS + rôle app_user)
-- =============================================================================
-- [US-043] Supprime les policies, désactive RLS, révoque les droits et
-- supprime le rôle app_user. Aucune donnée métier n'est perdue — seule la
-- protection RLS disparaît (retour au scoping applicatif US-042 seul).
--
-- ⚠️ Si DATABASE_URL pointe vers app_user au moment du rollback, remettre la
-- chaîne de connexion applicative sur le rôle admin AVANT ou juste après ce
-- script, sinon l'application perd tout accès (le rôle app_user disparaît).
--
-- Exécution :
--   psql -U potager_user -d potager_dev -h localhost -f migrations/rollback_v18.sql
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_evenements     ON evenements;
DROP POLICY IF EXISTS tenant_isolation_parcelles       ON parcelles;
DROP POLICY IF EXISTS tenant_isolation_culture_config  ON culture_config;

ALTER TABLE evenements     DISABLE ROW LEVEL SECURITY;
ALTER TABLE parcelles      DISABLE ROW LEVEL SECURITY;
ALTER TABLE culture_config DISABLE ROW LEVEL SECURITY;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM app_user;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_user;
REVOKE USAGE ON SCHEMA public FROM app_user;

DROP ROLE IF EXISTS app_user;

COMMIT;
