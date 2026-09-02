-- =============================================================================
-- migration_v32.sql — Observabilité de la cascade de réponses + retour du
-- jardinier (US-097)
-- =============================================================================
-- Crée deux tables :
--   * routage_logs    : une ligne par question passée par `llm/routeur.py`
--                       (`repondre_avec_cascade`) — nature détectée, origine de
--                       la classification, étage ayant finalement répondu,
--                       remontée de cascade, confiance, latence totale et
--                       jetons consommés (routage inclus, CA5 du document
--                       d'architecture).
--   * routage_retours : au plus un avis 👍/👎 du jardinier par ligne de
--                       `routage_logs` (contrainte UNIQUE — CA11, jamais
--                       redemandé pour la même réponse).
--
-- [CA2] La question journalisée est la question NORMALISÉE (même procédé que
-- le cache de classification, `llm/routeur.py::_normaliser_question`), jamais
-- le message brut.
-- [CA3] Rétention documentée : 12 mois, purge via
-- `app.services.metriques_routage.purger_routage_logs_expires`, appelée par le
-- job planifié quotidien (`bot.py::job_purge_potagers`, voir aussi US-084).
-- Les entrées d'un potager supprimé sont effacées avec lui par
-- `app.services.potagers.purger_potager` (CA3).
-- [CA4] Aucun secret, aucune clé, aucun contenu de fragment de connaissance :
-- seules des métadonnées de routage sont stockées ici, jamais un extrait de
-- réponse.
--
-- Purement additive : aucune table existante n'est modifiée, aucun
-- comportement applicatif ne dépend de la présence de données ici.
--
-- Idempotent : CREATE TABLE / CREATE INDEX IF NOT EXISTS.
-- Rollback : migrations/rollback_v32.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS routage_logs (
    id                     SERIAL PRIMARY KEY,
    -- Imputation tenant — permet l'agrégation par potager et par jour
    -- (préparation US-123, note technique de l'US).
    potager_id             INTEGER      NOT NULL REFERENCES potagers(id),
    cree_le                TIMESTAMP    NOT NULL DEFAULT NOW(),
    -- [CA2] Question NORMALISÉE (unidecode + minuscule + ponctuation retirée) —
    -- jamais le message brut du jardinier.
    question_normalisee    TEXT         NOT NULL,
    -- ACTION | QUESTION_DATA | QUESTION_SAVOIR | QUESTION_HYBRIDE (llm/routeur.py)
    nature                 VARCHAR(20)  NOT NULL,
    -- regle | cache | modele — origine de la DÉCISION DE CLASSIFICATION.
    origine_classification VARCHAR(10)  NOT NULL,
    -- donnee | savoir | raisonnement — étage ayant produit la réponse finale
    -- (distinct de la classification : une classification QUESTION_DATA peut
    -- remonter vers l'étage raisonnement, CA6/CA7 US-093).
    etage_resolveur        VARCHAR(20)  NOT NULL,
    -- Vrai si l'étage data n'a pas su répondre et que le raisonnement a pris
    -- le relais (au plus une remontée, US-093 CA7).
    cascade_remontee       BOOLEAN      NOT NULL DEFAULT FALSE,
    -- Confiance de la classification — NULL pour une décision par règle
    -- (confiance déjà maximale, sans objet à distinguer).
    confiance              REAL,
    -- Latence totale de la cascade (classification + réponse), en ms.
    latence_ms             INTEGER      NOT NULL DEFAULT 0,
    -- [CA5] Jetons consommés pour produire CETTE réponse, routage (appel de
    -- classification) inclus.
    tokens_consommes       INTEGER      NOT NULL DEFAULT 0
);

-- Requête cible CA5/CA6 : répartition et coût par étage sur une période.
CREATE INDEX IF NOT EXISTS idx_routage_logs_potager_date
    ON routage_logs (potager_id, cree_le);

-- Purge par ancienneté (CA3) et calcul de métriques transverses (CA5/CA6).
CREATE INDEX IF NOT EXISTS idx_routage_logs_cree_le
    ON routage_logs (cree_le);

CREATE TABLE IF NOT EXISTS routage_retours (
    id             SERIAL PRIMARY KEY,
    -- [CA11] Une seule ligne de retour par entrée de journal.
    routage_log_id INTEGER     NOT NULL UNIQUE REFERENCES routage_logs(id),
    -- Dénormalisé depuis routage_logs : évite une jointure pour la purge
    -- potager (CA3) et pour le scoping tenant des futurs endpoints web.
    potager_id     INTEGER     NOT NULL REFERENCES potagers(id),
    -- positif | negatif
    avis           VARCHAR(10) NOT NULL,
    cree_le        TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_routage_retours_avis CHECK (avis IN ('positif', 'negatif'))
);

-- [CA12] Liste des réponses les plus souvent jugées mauvaises.
CREATE INDEX IF NOT EXISTS idx_routage_retours_potager
    ON routage_retours (potager_id);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name IN ('routage_logs', 'routage_retours')
ORDER BY table_name, ordinal_position;

SELECT COUNT(*) AS nb_lignes_routage_logs FROM routage_logs;
SELECT COUNT(*) AS nb_lignes_routage_retours FROM routage_retours;
