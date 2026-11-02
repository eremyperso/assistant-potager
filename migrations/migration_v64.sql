-- =============================================================================
-- migration_v64.sql — Le carnet du compagnon (US-265)
-- =============================================================================
-- Le compagnon retient ce que le jardinier lui a DIT de lui-même (« j'arrose le
-- soir »), sur confirmation, et le jardinier voit, corrige ou efface.
--
--   carnet_faits (nouvelle)
--     un fait = 200 caractères au plus, avec sa date et l'échange d'origine.
--     30 faits au plus par jardinier et par potager (borne tenue par le service).
--     Personnel (D9) : rangée par (user_id, potager_id), jamais partagée.
--
--   potager_membres.niveau_compagnon  VARCHAR(10) NULL  — debutant | confirme
--   potager_membres.objectifs_saison  JSONB NULL        — 3 textes au plus
--     Le profil est déjà rangé par couple (jardinier, potager) depuis v60.
--
-- ⚠️ RLS stricte (lecture comme écriture) : un fait se lit et s'écrit dans le
-- potager où il a été dit, comme `echanges_conversation` (v61).
--
-- Aucun backfill : le niveau n'est jamais écrit sans la confirmation du jardinier.
-- À exécuter avec le rôle propriétaire de la base. Droits de app_user : couverts
-- par les DEFAULT PRIVILEGES de migration_v18.
-- Idempotent. Rollback : migrations/rollback_v64.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS carnet_faits (
    id         SERIAL       PRIMARY KEY,
    user_id    INTEGER      NOT NULL REFERENCES users(id),
    potager_id INTEGER      NOT NULL REFERENCES potagers(id),
    texte      VARCHAR(200) NOT NULL,
    origine    TEXT,
    cree_le    TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_carnet_faits_jardinier
    ON carnet_faits (user_id, potager_id, cree_le);
CREATE INDEX IF NOT EXISTS ix_carnet_faits_id ON carnet_faits (id);

COMMENT ON TABLE carnet_faits IS
    'US-265 — Le carnet du compagnon : ce que le jardinier a dit de lui-même. Écrit après '
    'confirmation seulement (R9), effaçable à tout moment (RGPD). Distinct de la mémoire du '
    'potager d''US-141 (ses notes).';
COMMENT ON COLUMN carnet_faits.origine IS
    'US-265 — L''échange qui a fait naître le fait : la phrase du jardinier.';

ALTER TABLE potager_membres
    ADD COLUMN IF NOT EXISTS niveau_compagnon VARCHAR(10),
    ADD COLUMN IF NOT EXISTS objectifs_saison JSONB;

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_niveau_compagnon;
ALTER TABLE potager_membres
    ADD CONSTRAINT ck_potager_membres_niveau_compagnon
    CHECK (niveau_compagnon IS NULL OR niveau_compagnon IN ('debutant', 'confirme'));

COMMENT ON COLUMN potager_membres.niveau_compagnon IS
    'US-265 — debutant | confirme. Déduit de l''activité puis PROPOSÉ ; NULL tant que le '
    'jardinier ne l''a pas confirmé.';
COMMENT ON COLUMN potager_membres.objectifs_saison IS
    'US-265 — Objectifs de saison (3 textes courts au plus), réglés par le jardinier.';

ALTER TABLE carnet_faits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_carnet_faits ON carnet_faits;
CREATE POLICY tenant_isolation_carnet_faits ON carnet_faits
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'carnet_faits';
SELECT polname FROM pg_policy WHERE polname = 'tenant_isolation_carnet_faits';
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'potager_membres' AND column_name IN ('niveau_compagnon', 'objectifs_saison');
