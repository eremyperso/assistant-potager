-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v79.sql — [US-316] Seuils de contrôle du pilotage LLM et leurs alertes
-- ═════════════════════════════════════════════════════════════════════════════
-- Deux tables d'ADMINISTRATION, sans RLS (comme `conso_tokens` : elles ne disent rien d'un potager).
--   * seuils_pilotage : un seuil = indicateur + périmètre + fenêtre + comparaison + valeur + gravité.
--     Les seuils par défaut sont posés par le code (`app/services/pilotage/seuils.py`), pas ici :
--     le choix « actif ou non » dépend de la présence d'une grille tarifaire.
--   * alertes_pilotage : un franchissement, de son ouverture à sa résolution. L'index partiel
--     uq_alertes_pilotage_ouverte garantit AU PLUS UNE alerte ouverte par seuil (CA7).
-- Aucune donnée de jardinier, aucune colonne ajoutée à une table existante.
-- Idempotente. Rollback : rollback_v79.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS seuils_pilotage (
    id             SERIAL PRIMARY KEY,
    indicateur     VARCHAR(32) NOT NULL,
    perimetre      VARCHAR(32) NOT NULL DEFAULT 'tous',
    fenetre_jours  SMALLINT    NOT NULL DEFAULT 1,
    comparaison    VARCHAR(12) NOT NULL DEFAULT 'fixe',
    valeur         DOUBLE PRECISION NOT NULL,
    gravite        VARCHAR(8)  NOT NULL DEFAULT 'moyenne',
    actif          BOOLEAN     NOT NULL DEFAULT FALSE,
    a_valider      BOOLEAN     NOT NULL DEFAULT TRUE,
    cree_le        TIMESTAMP   DEFAULT NOW(),
    modifie_le     TIMESTAMP   NULL,
    CONSTRAINT uq_seuils_pilotage_definition UNIQUE (indicateur, perimetre, fenetre_jours, comparaison),
    CONSTRAINT ck_seuils_pilotage_comparaison CHECK (comparaison IN ('fixe', 'ecart_7j')),
    CONSTRAINT ck_seuils_pilotage_gravite CHECK (gravite IN ('haute', 'moyenne', 'basse')),
    CONSTRAINT ck_seuils_pilotage_fenetre CHECK (fenetre_jours BETWEEN 1 AND 31)
);
CREATE INDEX IF NOT EXISTS ix_seuils_pilotage_id ON seuils_pilotage (id);

CREATE TABLE IF NOT EXISTS alertes_pilotage (
    id                 SERIAL PRIMARY KEY,
    seuil_id           INTEGER NOT NULL REFERENCES seuils_pilotage (id) ON DELETE CASCADE,
    valeur_mesuree     DOUBLE PRECISION NOT NULL,
    valeur_reference   DOUBLE PRECISION NULL,
    nb_appels          INTEGER   NOT NULL DEFAULT 0,
    declenchee_le      TIMESTAMP NOT NULL DEFAULT NOW(),
    resolue_le         TIMESTAMP NULL,
    canaux_notifies    VARCHAR(40) NOT NULL DEFAULT '',
    dernier_rappel_le  TIMESTAMP NULL,
    retour_notifie     BOOLEAN   NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_alertes_pilotage_id ON alertes_pilotage (id);
CREATE INDEX IF NOT EXISTS idx_alertes_pilotage_declenchee ON alertes_pilotage (declenchee_le);
CREATE UNIQUE INDEX IF NOT EXISTS uq_alertes_pilotage_ouverte ON alertes_pilotage (seuil_id) WHERE resolue_le IS NULL;

COMMENT ON TABLE seuils_pilotage IS '[US-316] Seuils de contrôle du pilotage LLM (administration, sans RLS)';
COMMENT ON TABLE alertes_pilotage IS '[US-316] Franchissements de seuil ; au plus une alerte ouverte par seuil';

COMMIT;
