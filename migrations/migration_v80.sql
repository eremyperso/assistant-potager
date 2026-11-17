-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v80.sql — [US-317] La trace des résumés quotidiens et bilans hebdomadaires envoyés
-- ═════════════════════════════════════════════════════════════════════════════
-- Une ligne par (type, début de période) : un bilan n'est jamais produit deux fois pour la même
-- période (CA8). `tentatives` plafonne à 2 (un envoi, un seul rejeu). Table d'administration, sans
-- RLS, sans donnée de jardinier. Indépendante de `alertes_pilotage` (v79) : une alerte est un
-- événement, un bilan une période.
-- Idempotente. Rollback : rollback_v80.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS bilans_pilotage (
    id             SERIAL PRIMARY KEY,
    type           VARCHAR(12) NOT NULL,
    periode_debut  DATE        NOT NULL,
    periode_fin    DATE        NOT NULL,
    statut         VARCHAR(8)  NOT NULL,
    tentatives     SMALLINT    NOT NULL DEFAULT 0,
    envoye_le      TIMESTAMP   NULL,
    erreur         VARCHAR(200) NULL,
    cree_le        TIMESTAMP   DEFAULT NOW(),
    CONSTRAINT uq_bilans_pilotage_periode UNIQUE (type, periode_debut),
    CONSTRAINT ck_bilans_pilotage_type CHECK (type IN ('quotidien', 'hebdomadaire')),
    CONSTRAINT ck_bilans_pilotage_statut CHECK (statut IN ('envoye', 'echoue'))
);
CREATE INDEX IF NOT EXISTS ix_bilans_pilotage_id ON bilans_pilotage (id);

COMMENT ON TABLE bilans_pilotage IS '[US-317] Résumés quotidiens et bilans hebdomadaires de pilotage envoyés (administration, sans RLS)';

COMMIT;
