-- =============================================================================
-- migration_v31.sql — Mesure de consommation LLM par potager (US-092)
-- =============================================================================
-- Crée la table `conso_tokens`, alimentée par la passerelle LLM unique
-- (`llm/passerelle.py`) à chaque appel au fournisseur de modèles — succès
-- comme échec.
--
-- Cette table MESURE, elle ne plafonne pas (arbitrage tranché de l'US) : les
-- budgets par potager, le blocage au dépassement et le message d'incitation à
-- l'abonnement restent au périmètre de l'US de quotas, qui consommera ces
-- lignes. Séparer la mesure du plafonnement permet de disposer d'un mois de
-- données réelles avant de fixer un prix.
--
-- Nom de table et colonnes repris du cadrage initial d'US-123 pour ne pas créer
-- une table concurrente. Deux colonnes s'y ajoutent, documentées ci-dessous :
--   * tokens_cache : [CA6] jetons servis depuis le cache de prompt du
--                    fournisseur, distingués des jetons facturés plein tarif ;
--   * user_id      : [CA2] auteur de l'appel, en complément du potager.
--
-- Purement additive : aucune table existante n'est modifiée, aucun
-- comportement applicatif ne dépend de la présence de données ici.
--
-- Idempotent : CREATE TABLE / CREATE INDEX IF NOT EXISTS.
-- Rollback : migrations/rollback_v31.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS conso_tokens (
    id           SERIAL PRIMARY KEY,
    -- Imputation tenant : c'est l'unité de mesure du coût (CA5).
    potager_id   INTEGER      NOT NULL REFERENCES potagers(id),
    -- [CA2] Auteur de l'appel — NULL pour un appel de fond sans utilisateur.
    user_id      INTEGER      NULL     REFERENCES users(id),
    -- Jour d'imputation : l'agrégation utile est quotidienne, pas à la seconde.
    date         DATE         NOT NULL,
    -- classification | parsing | question | synthese | transcription
    appel_type   VARCHAR(32)  NOT NULL,
    -- Modèle réellement appelé : les quotas Groq sont comptés PAR MODÈLE, la
    -- répartition multi-modèles (CA3) n'est lisible que si on le stocke.
    modele       VARCHAR(120) NOT NULL,
    tokens_in    INTEGER      NOT NULL DEFAULT 0,
    tokens_out   INTEGER      NOT NULL DEFAULT 0,
    -- [CA6] Jetons servis depuis le cache de prompt du fournisseur — reste à 0
    -- tant que celui-ci ne les expose pas.
    tokens_cache INTEGER      NOT NULL DEFAULT 0,
    -- Durée de l'appel, nouvelle tentative comprise (CA12).
    latence_ms   INTEGER      NOT NULL DEFAULT 0,
    -- ok | quota | delai | erreur — les échecs sont mesurés eux aussi, faute de
    -- quoi une saturation ressemblerait à une baisse d'usage.
    issue        VARCHAR(16)  NOT NULL DEFAULT 'ok',
    cree_le      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Requête cible de l'US de quotas : « consommation du potager X sur la période ».
CREATE INDEX IF NOT EXISTS idx_conso_tokens_potager_date
    ON conso_tokens (potager_id, date);

-- Analyse transverse : quel type d'appel / quel modèle sature en premier.
CREATE INDEX IF NOT EXISTS idx_conso_tokens_type
    ON conso_tokens (appel_type);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'conso_tokens'
ORDER BY ordinal_position;

SELECT COUNT(*) AS nb_lignes_conso FROM conso_tokens;
