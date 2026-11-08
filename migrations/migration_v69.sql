-- =============================================================================
-- migration_v69.sql — Connecter son assistant IA à son potager (US-290)
-- =============================================================================
-- Le canal MCP : un serveur d'autorisation OAuth 2.1 (PKCE) et un serveur MCP
-- distant sur /mcp. Cinq tables de COMPTE, sans RLS (même traitement que
-- `liaisons_telegram`, `files_gestes_reglages`) : un connecteur appartient à un
-- jardinier, pas à un jardin. Le potager visé par un appel est vérifié par le
-- service (consentement + appartenance), puis la RLS du potager s'applique aux
-- lectures de l'outil.
--
--   mcp_clients              clients OAuth enregistrés (RFC 7591)
--   mcp_autorisations        ce que le jardinier a consenti : portée
--                            (lecture | ecriture), potagers, révocation
--   mcp_jetons               jetons opaques (acces | rafraichissement |
--                            personnel) — empreinte SHA-256 seule
--   mcp_codes_autorisation   codes OAuth, 10 min, usage unique, PKCE S256
--   mcp_appels               journal des appels d'outils (sans contenu libre),
--                            base du plafond d'appels par connecteur
--
-- Aucun secret en clair. Supprimer un compte supprime ses connecteurs (CASCADE).
-- Aucune donnée à reprendre. À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v69.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mcp_clients (
    id                 SERIAL PRIMARY KEY,
    client_id          VARCHAR(64)  NOT NULL UNIQUE,
    nom                VARCHAR(120) NOT NULL,
    redirect_uris      JSONB        NOT NULL,
    methode_auth_jeton VARCHAR(24)  NOT NULL DEFAULT 'none',
    secret_empreinte   VARCHAR(64)  NULL,
    cree_le            TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mcp_autorisations (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id        INTEGER      NULL REFERENCES mcp_clients(id) ON DELETE CASCADE,
    type             VARCHAR(10)  NOT NULL,
    libelle          VARCHAR(120) NOT NULL,
    portee           VARCHAR(10)  NOT NULL DEFAULT 'lecture',
    potager_ids      JSONB        NOT NULL,
    cree_le          TIMESTAMP    NOT NULL DEFAULT NOW(),
    dernier_appel_le TIMESTAMP    NULL,
    revoque_le       TIMESTAMP    NULL,
    CONSTRAINT ck_mcp_autorisations_type   CHECK (type IN ('oauth', 'personnel')),
    CONSTRAINT ck_mcp_autorisations_portee CHECK (portee IN ('lecture', 'ecriture'))
);
CREATE INDEX IF NOT EXISTS ix_mcp_autorisations_user_id ON mcp_autorisations (user_id);

CREATE TABLE IF NOT EXISTS mcp_jetons (
    id              SERIAL PRIMARY KEY,
    autorisation_id INTEGER     NOT NULL REFERENCES mcp_autorisations(id) ON DELETE CASCADE,
    type            VARCHAR(16) NOT NULL,
    empreinte       VARCHAR(64) NOT NULL UNIQUE,
    expire_le       TIMESTAMP   NOT NULL,
    revoque_le      TIMESTAMP   NULL,
    cree_le         TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mcp_jetons_type CHECK (type IN ('acces', 'rafraichissement', 'personnel'))
);
CREATE INDEX IF NOT EXISTS ix_mcp_jetons_autorisation_id ON mcp_jetons (autorisation_id);

CREATE TABLE IF NOT EXISTS mcp_codes_autorisation (
    id              SERIAL PRIMARY KEY,
    autorisation_id INTEGER      NOT NULL REFERENCES mcp_autorisations(id) ON DELETE CASCADE,
    empreinte       VARCHAR(64)  NOT NULL UNIQUE,
    code_challenge  VARCHAR(128) NOT NULL,
    redirect_uri    TEXT         NOT NULL,
    expire_le       TIMESTAMP    NOT NULL,
    utilise_le      TIMESTAMP    NULL
);

CREATE TABLE IF NOT EXISTS mcp_appels (
    id              SERIAL PRIMARY KEY,
    horodatage      TIMESTAMP    NOT NULL DEFAULT NOW(),
    user_id         INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    autorisation_id INTEGER      NOT NULL REFERENCES mcp_autorisations(id) ON DELETE CASCADE,
    client          VARCHAR(120) NOT NULL,
    outil           VARCHAR(64)  NOT NULL,
    potager_id      INTEGER      NULL REFERENCES potagers(id) ON DELETE SET NULL,
    resultat        VARCHAR(8)   NOT NULL,
    motif           VARCHAR(32)  NULL,
    duree_ms        INTEGER      NOT NULL DEFAULT 0,
    CONSTRAINT ck_mcp_appels_resultat CHECK (resultat IN ('ok', 'refus', 'erreur'))
);
CREATE INDEX IF NOT EXISTS ix_mcp_appels_autorisation_horodatage ON mcp_appels (autorisation_id, horodatage);

-- ── Convergence ──────────────────────────────────────────────────────────────
-- Une API démarrée avec le nouveau code AVANT cette migration crée déjà les
-- tables par `Base.metadata.create_all` (app/api/main.py) : les CREATE ci-dessus
-- sont alors sautés, et deux écarts subsistent (constatés en dev local le
-- 07/11/2026) — colonnes JSON au lieu de JSONB, `duree_ms` sans défaut. Rejoués
-- sur des tables déjà conformes, ces ALTER ne changent rien.
ALTER TABLE mcp_clients       ALTER COLUMN redirect_uris TYPE JSONB USING redirect_uris::jsonb;
ALTER TABLE mcp_autorisations ALTER COLUMN potager_ids   TYPE JSONB USING potager_ids::jsonb;
ALTER TABLE mcp_appels        ALTER COLUMN duree_ms      SET DEFAULT 0;

COMMENT ON TABLE mcp_appels IS
    'US-290/CA7 — Un appel d''outil MCP : date, client, outil, potager, résultat, motif court, '
    'durée. JAMAIS le contenu des arguments ni des textes libres. Sert aussi au plafond '
    'd''appels par minute et par jour (CA6).';

COMMIT;
