-- =============================================================================
-- migration_v41.sql — Associations de cultures, orientées et tracées (US-163)
-- =============================================================================
-- [CA1] Crée `association_culture` : une arête TYPÉE entre deux cultures et/ou
-- familles botaniques — jamais un paragraphe dans une fiche (US-140/CA7bis,
-- docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.2). `nature` porte la
-- relation ('favorable' | 'defavorable' | 'neutre'), `motif` le texte court qui
-- la rend compréhensible plutôt qu'autoritaire.
--
-- [CA2] `niveau_preuve` ('etabli' | 'traditionnel') distingue une relation
-- démontrée d'une relation seulement issue de la tradition horticole — les
-- verser dans la même colonne sans distinction ferait affirmer à l'application
-- ce qu'elle ne peut pas soutenir (docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_
-- CULTURES.md §6.5). La formulation différenciée (CA3) est un problème de
-- restitution, pas de schéma : elle vit dans app/services/associations.py.
--
-- Ni `nature` ni `niveau_preuve` ne portent de contrainte CHECK de vocabulaire :
-- même arbitrage que migration_v39 sur `culture_config.exposition` — un
-- vocabulaire fermé mais RÉVISABLE en produit, validé par
-- app/services/associations.py, seul point d'écriture.
--
-- [CA4] Chaque côté (A, B) référence SOIT une culture (`culture_x_id`) SOIT une
-- famille botanique (`famille_x_id`), jamais les deux ni aucun des deux — les
-- deux CHECK ci-dessous le garantissent en base, en plus de la validation
-- Python. Porter une association au niveau de la famille la fait valoir pour
-- toutes les cultures qui s'y rattachent (mesure du 25/08/2026 : les
-- cucurbitacées se répartissent sur dix libellés distincts) sans la saisir dix
-- fois — et sans l'incohérence garantie d'une saisie répétée.
--
-- [CA5] Le stockage reste ORIENTÉ (une ligne par couple, comme evenements) :
-- c'est la LECTURE qui est symétrique (app/services/associations.lire_associations
-- interroge culture_a_id/famille_a_id ET culture_b_id/famille_b_id), jamais la
-- forme de stockage. Aucune colonne ni index supplémentaire n'est nécessaire
-- pour ça — les quatre index ci-dessous couvrent les deux sens de lecture.
--
-- [CA10] `source_id` est NOT NULL : aucune arête anonyme. Les associations sont
-- SAISIES, pas importées (arbitrage option A sur la licence, zéro CC-BY-SA
-- dans le socle) — l'origine sera donc `saisie_manuelle` dans l'immense
-- majorité des cas, écrite par app/services/associations.py à chaque saisie ou
-- correction depuis le bot (`/association saisir`), jamais par un script
-- d'import : cette migration ne sème AUCUNE ligne `association_culture`.
--
-- ── [CA12] Index de performance pour la rotation ─────────────────────────────
-- La requête de rotation (US-163/CA6, app/services/rotation.py) joint
-- `evenements` à `culture_config`/`familles_botaniques` filtré par parcelle et
-- borné dans le temps. `idx_evenements_potager_date` (migration_v ancienne)
-- couvre déjà (potager_id, date) mais pas parcelle_id : cet index composite
-- couvre la clause WHERE réellement posée par `evaluer_rotation`.
--
-- Idempotent : CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.
-- Rollback : migrations/rollback_v41.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS association_culture (
    id             SERIAL PRIMARY KEY,
    culture_a_id   INTEGER NULL REFERENCES culture_config(id),
    famille_a_id   INTEGER NULL REFERENCES familles_botaniques(id),
    culture_b_id   INTEGER NULL REFERENCES culture_config(id),
    famille_b_id   INTEGER NULL REFERENCES familles_botaniques(id),
    nature         VARCHAR NOT NULL,
    motif          VARCHAR NOT NULL,
    niveau_preuve  VARCHAR NOT NULL,
    source_id      INTEGER NOT NULL REFERENCES referentiel_source(id),
    CONSTRAINT ck_association_culture_cote_a
        CHECK ((culture_a_id IS NOT NULL) <> (famille_a_id IS NOT NULL)),
    CONSTRAINT ck_association_culture_cote_b
        CHECK ((culture_b_id IS NOT NULL) <> (famille_b_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_association_culture_culture_a ON association_culture (culture_a_id);
CREATE INDEX IF NOT EXISTS idx_association_culture_culture_b ON association_culture (culture_b_id);
CREATE INDEX IF NOT EXISTS idx_association_culture_famille_a ON association_culture (famille_a_id);
CREATE INDEX IF NOT EXISTS idx_association_culture_famille_b ON association_culture (famille_b_id);
CREATE INDEX IF NOT EXISTS idx_association_culture_source   ON association_culture (source_id);

COMMENT ON TABLE association_culture IS
    'US-163 — Association orientée entre deux cultures et/ou familles botaniques : '
    'nature (favorable/defavorable/neutre), motif court, niveau de preuve '
    '(etabli/traditionnel), source obligatoire. Stockage orienté, lecture symétrique '
    '(CA5) via app.services.associations.lire_associations.';

COMMENT ON CONSTRAINT ck_association_culture_cote_a ON association_culture IS
    'US-163/CA4 — Un côté référence une culture OU une famille, jamais les deux ni aucun.';

COMMENT ON CONSTRAINT ck_association_culture_cote_b ON association_culture IS
    'US-163/CA4 — Symétrique de ck_association_culture_cote_a pour le second côté.';

-- ── [CA12] Historique d'une parcelle par campagne ────────────────────────────
CREATE INDEX IF NOT EXISTS idx_evenements_parcelle_date ON evenements (parcelle_id, date);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'association_culture'
ORDER BY ordinal_position;

-- [CA10] Aucune arête anonyme : ce compteur doit valoir zéro à tout instant.
SELECT COUNT(*) AS associations_sans_source
FROM association_culture WHERE source_id IS NULL;

-- [CA4] Chaque côté est soit une culture, soit une famille — jamais les deux
-- ni aucun. Ces deux compteurs doivent valoir zéro (déjà garanti par les CHECK,
-- vérification de cohérence redondante mais peu coûteuse).
SELECT COUNT(*) AS cote_a_incoherent FROM association_culture
WHERE (culture_a_id IS NOT NULL) = (famille_a_id IS NOT NULL);
SELECT COUNT(*) AS cote_b_incoherent FROM association_culture
WHERE (culture_b_id IS NOT NULL) = (famille_b_id IS NOT NULL);
