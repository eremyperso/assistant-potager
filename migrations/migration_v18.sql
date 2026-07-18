-- =============================================================================
-- migration_v18.sql — Row-Level Security PostgreSQL en défense en profondeur
-- =============================================================================
-- [US-043] Ajoute une seconde ligne de défense au niveau base de données,
-- indépendante du scoping applicatif (US-042) : même une requête mal écrite
-- dans une future fonction de service ne pourra jamais lire/écrire hors du
-- potager courant.
--
-- Prérequis : migration_v17.sql appliquée (potager_id NOT NULL sur evenements
-- et parcelles). culture_config reste nullable (fiches globales partagées) —
-- la policy RLS ci-dessous en tient compte explicitement.
--
-- Principe :
--   1. Un rôle applicatif NON-superuser `app_user` est créé — le propriétaire
--      des tables (rôle admin/migration) n'est PAS soumis aux policies RLS
--      par défaut, donc RLS n'a d'effet que si l'application se connecte
--      avec un rôle distinct du propriétaire.
--   2. RLS est activé (ENABLE, pas FORCE) sur chaque table métier portant
--      potager_id : evenements, parcelles, culture_config.
--   3. Une policy USING/WITH CHECK compare potager_id au GUC de session
--      `app.potager_id`, positionné par database/db.py (SET LOCAL, par
--      transaction) à partir du TenantContext courant.
--   4. `current_setting('app.potager_id')` SANS le 2ᵉ argument `missing_ok`
--      lève nativement une erreur PostgreSQL explicite si le GUC n'a jamais
--      été positionné dans la session — c'est le fail-fast demandé par CA5 :
--      aucune requête ne peut silencieusement renvoyer zéro ligne faute de
--      contexte, elle échoue bruyamment à la place.
--
-- ⚠️ Après cette migration, `DATABASE_URL` (.env.dev / .env.prod) DOIT
-- pointer vers `app_user` pour que la protection soit effective — tant que
-- l'application se connecte avec le rôle propriétaire des tables, RLS reste
-- inactif pour elle (bypass normal PostgreSQL pour le owner). Les opérations
-- de migration et de sauvegarde (pg_dump, psql -f migrations/*.sql)
-- continuent, elles, à utiliser le rôle admin/propriétaire — c'est
-- précisément ce qui garantit CA7 (aucune policy bloquante pour elles).
--
-- Jobs de fond (météo, sauvegardes, futurs jobs multi-potager) : ils doivent
-- positionner `app.potager_id` eux-mêmes avant toute requête (voir
-- bot.py::job_meteo_quotidienne pour l'exemple actuel, via
-- database.db.tenant_scope) — à traiter potager par potager s'ils itèrent
-- sur plusieurs potagers un jour.
--
-- Idempotent : DO $$ ... $$ + DROP POLICY IF EXISTS avant chaque CREATE
-- POLICY (PostgreSQL ne supporte pas CREATE POLICY IF NOT EXISTS).
--
-- Exécution — le mot de passe de app_user est passé en variable psql (texte
-- brut, sans guillemets : la syntaxe :'app_user_password' dans le script se
-- charge elle-même de l'échapper en littéral SQL) pour ne jamais l'écrire en
-- clair dans ce fichier versionné :
--
-- ⚠️ Environnement dev (déploiement automatique via .github/workflows/deploy-dev.yml
-- sur push vers `dev`) : la variable est déjà câblée depuis le secret GitHub
-- `APP_USER_PASSWORD` — le créer AVANT tout merge/déploiement déclenchant cette
-- migration, sinon app_user est créé avec un mot de passe vide. Préférer un mot
-- de passe alphanumérique (sans guillemet ni espace) pour rester compatible avec
-- l'échappement shell utilisé par le workflow.
--
--   psql -U potager_user -d potager_dev -h localhost \
--        -v app_user_password="un-mot-de-passe-fort" \
--        -f migrations/migration_v18.sql
--
-- Rollback : migrations/rollback_v18.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- [1] Rôle applicatif non-superuser, distinct du rôle admin/propriétaire.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        EXECUTE format('CREATE ROLE app_user LOGIN PASSWORD %L', :'app_user_password');
    END IF;
END $$;

-- [2] Droits nécessaires — RLS filtre les LIGNES, il ne remplace pas les
-- droits SQL standards : app_user a besoin des GRANT habituels sur toutes
-- les tables (y compris hors périmètre RLS : users, potagers, ...) pour que
-- l'application continue de fonctionner une fois reconnectée sous ce rôle.
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Tables créées par de futures migrations (exécutées avec le rôle admin) :
-- héritent automatiquement des mêmes droits pour app_user.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;

-- [3] Activation RLS — ENABLE (pas FORCE) : le rôle propriétaire (migrations,
-- pg_dump) continue de tout voir sans policy, app_user y est soumis (CA7).
ALTER TABLE evenements     ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcelles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE culture_config ENABLE ROW LEVEL SECURITY;

-- [4] Policies — une par table, lecture ET écriture (USING + WITH CHECK).
DROP POLICY IF EXISTS tenant_isolation_evenements ON evenements;
CREATE POLICY tenant_isolation_evenements ON evenements
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_parcelles ON parcelles;
CREATE POLICY tenant_isolation_parcelles ON parcelles
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- culture_config : potager_id NULL = fiche référentiel globale partagée entre
-- tous les potagers (décision actée en US-040/US-042, migration_v16/v17) —
-- ces lignes doivent rester visibles en lecture pour tout potager, donc le
-- USING accepte explicitement NULL en plus du potager courant. Le WITH CHECK,
-- lui, n'accepte PAS NULL : depuis l'application (rôle app_user), on ne crée
-- jamais de fiche globale — seul le rôle admin (hors RLS) le peut.
DROP POLICY IF EXISTS tenant_isolation_culture_config ON culture_config;
CREATE POLICY tenant_isolation_culture_config ON culture_config
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

COMMIT;

-- [5] Vérification post-migration
SELECT rolname, rolsuper, rolcanlogin FROM pg_roles WHERE rolname = 'app_user';

SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN ('evenements', 'parcelles', 'culture_config');

SELECT schemaname, tablename, policyname, cmd, qual, with_check
FROM pg_policies
WHERE tablename IN ('evenements', 'parcelles', 'culture_config')
ORDER BY tablename;
