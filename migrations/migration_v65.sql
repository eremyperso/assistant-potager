-- =============================================================================
-- migration_v65.sql — Les signaux du veilleur et les rappels (US-266)
-- =============================================================================
-- Le veilleur DÉTECTE, sans modèle (R7), ce qui mérite peut-être un message :
-- gel ou canicule sur des cultures en place, fortes pluies, sécheresse sans
-- arrosage noté, échéance d'un lot, récolte imminente, levée non notée,
-- fenêtre de semis qui s'ouvre, bilan de la semaine. Il n'envoie rien (US-267).
--
--   signaux (nouvelle)
--     theme, cle_unique, priorite, expire_le, donnees (JSONB), etat, detecte_le.
--     UNIQUE (potager_id, cle_unique) : un même fait (« gel:2026-10-28:parcelle-12 »)
--     ne produit qu'un signal par potager, quel que soit le nombre de passages.
--     user_id NULL = fait du potager ; renseigné = fait propre à un jardinier.
--
--   rappels (nouvelle)
--     objet, echeance_le, cible_type / cible_id, etat (programme | echu | annule),
--     proposition_id. Écrite par US-268 après confirmation (R9) ; créée ici avec
--     les signaux (cadrage §3 : « signaux et rappels »).
--
-- Horodatages en heure locale du potager (Europe/Paris), écrits par le service.
-- Purge à 30 jours par le job de 04h00 (`compagnon/signaux.purger`).
--
-- ⚠️ RLS stricte (lecture comme écriture) sur les deux tables, comme
-- `actions_menees` (v62) : le veilleur arme chaque potager à son tour.
--
-- Aucun backfill. À exécuter avec le rôle propriétaire de la base. Droits de
-- app_user : couverts par les DEFAULT PRIVILEGES de migration_v18.
-- Idempotent. Rollback : migrations/rollback_v65.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS signaux (
    id          SERIAL       PRIMARY KEY,
    potager_id  INTEGER      NOT NULL REFERENCES potagers(id),
    user_id     INTEGER      REFERENCES users(id),
    theme       VARCHAR(16)  NOT NULL,
    cle_unique  VARCHAR(160) NOT NULL,
    priorite    VARCHAR(10)  NOT NULL,
    expire_le   TIMESTAMP    NOT NULL,
    donnees     JSONB,
    etat        VARCHAR(12)  NOT NULL DEFAULT 'detecte',
    detecte_le  TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_signaux_potager_cle UNIQUE (potager_id, cle_unique),
    CONSTRAINT ck_signaux_theme
        CHECK (theme IN ('meteo', 'suivis', 'echeances', 'suggestions', 'rappels', 'resume')),
    CONSTRAINT ck_signaux_priorite CHECK (priorite IN ('immediat', 'normal', 'resume')),
    CONSTRAINT ck_signaux_etat
        CHECK (etat IN ('detecte', 'envoye', 'regroupe', 'ignore', 'repondu'))
);

CREATE INDEX IF NOT EXISTS ix_signaux_potager_detecte ON signaux (potager_id, detecte_le);
CREATE INDEX IF NOT EXISTS ix_signaux_id ON signaux (id);

COMMENT ON TABLE signaux IS
    'US-266 — Ce que le veilleur a détecté, sans modèle (R7). Un signal par fait et par '
    'potager (cle_unique). Aucun envoi dans US-266 : le distributeur d''US-267 fera avancer etat.';
COMMENT ON COLUMN signaux.cle_unique IS
    'US-266 — Le fait détecté, par exemple « gel:2026-10-28:parcelle-12 ». Dédoublonne les passages.';

CREATE TABLE IF NOT EXISTS rappels (
    id             SERIAL       PRIMARY KEY,
    user_id        INTEGER      NOT NULL REFERENCES users(id),
    potager_id     INTEGER      NOT NULL REFERENCES potagers(id),
    objet          VARCHAR(200) NOT NULL,
    echeance_le    TIMESTAMP    NOT NULL,
    cible_type     VARCHAR(32),
    cible_id       INTEGER,
    etat           VARCHAR(12)  NOT NULL DEFAULT 'programme',
    proposition_id INTEGER      REFERENCES propositions(id) ON DELETE SET NULL,
    cree_le        TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT ck_rappels_etat CHECK (etat IN ('programme', 'echu', 'annule'))
);

CREATE INDEX IF NOT EXISTS ix_rappels_echeance ON rappels (potager_id, etat, echeance_le);
CREATE INDEX IF NOT EXISTS ix_rappels_id ON rappels (id);

COMMENT ON TABLE rappels IS
    'US-266 — Rappels confirmés par le jardinier (écrits par US-268, R9). Le veilleur en tire '
    'un signal « rappels » à l''échéance.';

ALTER TABLE signaux ENABLE ROW LEVEL SECURITY;
ALTER TABLE rappels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_signaux ON signaux;
CREATE POLICY tenant_isolation_signaux ON signaux
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_rappels ON rappels;
CREATE POLICY tenant_isolation_rappels ON rappels
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('signaux', 'rappels');
SELECT polname FROM pg_policy WHERE polname IN ('tenant_isolation_signaux', 'tenant_isolation_rappels');
