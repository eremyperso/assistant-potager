-- =============================================================================
-- migration_v38.sql — Registre des sources du référentiel (US-166)
-- =============================================================================
-- [CA1] Crée `referentiel_source` : une ligne par origine de donnée, portant sa
-- licence, l'attribution à afficher, son URL et la date du dernier import.
-- L'attribution est une obligation PAR ENREGISTREMENT, pas une ligne de README :
-- c'est la seule façon de répondre « d'où sort cette information ? » et « que
-- puis-je publier ? » six mois après l'import, quand plus personne ne se
-- souvient de ce qui venait d'où.
--
-- [CA2] La colonne `partageable` vaut `true` pour toutes les sources retenues
-- aujourd'hui (arbitrage option A, docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md
-- §2.1 : zéro CC-BY-SA dans le socle). Elle existe malgré tout parce qu'elle
-- rend l'option B réversiblement atteignable si une source à partage à
-- l'identique devenait un jour indispensable sur les associations — pour un
-- coût de deux lignes de migration, contre une reprise de schéma sinon.
--
-- [CA3] Le registre reconnaît aussi les origines NON importées : `saisie_manuelle`
-- (le jardinier corrige au bot) et `redaction_interne` (contenu écrit par le
-- projet). Une donnée saisie est tracée au même titre qu'une donnée importée —
-- il n'existe aucune donnée sans origine.
--
-- [CA4] `familles_botaniques.source_id` et `culture_config.famille_source_id`
-- rattachent la donnée à son origine. Retirer une source devient une requête
-- (voir app/services/referentiel_sources.donnees_derivees, un seul UNION ALL),
-- et non une fouille de code.
--
-- [US-166] `familles_botaniques.nom_scientifique` est l'apport propre de
-- Wikidata (CC0) au référentiel structuré — le champ prévu par
-- docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md §4.1. Nullable : une
-- famille saisie au bot n'a aucune raison d'en porter un.
--
-- Backfill : tout ce que la migration_v37 a semé porte l'origine
-- `redaction_interne` — c'est la vérité (le semis venait de l'ancienne table
-- figée `frontend/src/lib/familles.js`), et c'est ce qui rend CA3 vrai dès la
-- livraison plutôt qu'à partir du premier import. Les colonnes restent
-- nullables : un rattachement antérieur dont l'origine n'est pas connaissable
-- reste NULL plutôt que d'être deviné après coup (même invariant que
-- `evenements.date_source`, US-169 / CA7).
--
-- ⚠️ Ce script ne crée AUCUNE ligne culture_config et n'en modifie aucun
-- attribut métier (CA7) : il ne fait qu'ajouter la traçabilité d'un
-- rattachement déjà écrit par la v37.
--
-- Idempotent : CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS,
-- INSERT ... ON CONFLICT DO NOTHING, UPDATE gardés par IS NULL.
-- Rollback : migrations/rollback_v38.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS referentiel_source (
    id                  SERIAL PRIMARY KEY,
    -- [CA1] Code stable cité par les scripts d'import et les requêtes de
    -- traçabilité — jamais l'id, qui dépend de l'ordre d'insertion.
    code                VARCHAR NOT NULL,
    libelle             VARCHAR NOT NULL,
    -- [CA6] Valeur du socle uniquement : 'CC0' | 'Licence Ouverte 2.0' |
    -- 'proprietaire'. Le refus de tout le reste est appliqué en amont, par
    -- app/services/referentiel_sources.verifier_licence_importable — pas par une
    -- contrainte CHECK, qui figerait le socle dans le schéma alors que
    -- l'arbitrage de licence est une décision produit révisable (option B).
    licence             VARCHAR NOT NULL,
    -- [CA1] NOT NULL : une source sans attribution connue n'entre pas au
    -- registre, donc rien ne peut légalement en dériver.
    attribution         VARCHAR NOT NULL,
    url                 VARCHAR NULL,
    -- [CA1] Dernier import réussi. NULL pour une origine non importée (CA3)
    -- comme pour une source déclarée mais jamais encore rejouée.
    date_dernier_import TIMESTAMP NULL,
    -- [CA2] Exclut d'un éventuel export les sources contaminantes.
    partageable         BOOLEAN NOT NULL DEFAULT TRUE,
    -- [CA3] FALSE = origine non importée (saisie du jardinier, rédaction
    -- interne). C'est aussi ce qui rend 'proprietaire' légitime : cette licence
    -- ne vaut que pour un contenu interne, jamais pour un contenu importé.
    importee            BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_referentiel_source_code UNIQUE (code)
);

COMMENT ON TABLE referentiel_source IS
    'US-166 — Registre des sources : code, licence, attribution affichée, URL, '
    'date du dernier import, partageable (CA2) et importee (CA3). Toute donnée '
    'du référentiel structuré y est rattachée ; il n''existe aucune donnée sans origine.';

-- ── [CA1, CA3] Le socle, importé comme non importé ───────────────────────────
-- Miroir exact de SOURCES_SOCLE dans app/services/referentiel_sources.py.
INSERT INTO referentiel_source (code, libelle, licence, attribution, url, partageable, importee) VALUES
    ('wikidata', 'Wikidata', 'CC0',
     'Wikidata — CC0 1.0 Universal (domaine public)',
     'https://www.wikidata.org/', TRUE, TRUE),
    ('ephy_anses', 'Catalogue E-Phy (ANSES)', 'Licence Ouverte 2.0',
     'ANSES — catalogue E-Phy, Licence Ouverte 2.0 (Etalab)',
     'https://www.data.gouv.fr/fr/datasets/donnees-ouvertes-du-catalogue-e-phy-des-produits-phytopharmaceutiques/',
     TRUE, TRUE),
    ('saisie_manuelle', 'Saisie du jardinier', 'proprietaire',
     'Saisi par le jardinier', NULL, TRUE, FALSE),
    ('redaction_interne', 'Rédaction interne Assistant Potager', 'proprietaire',
     'Assistant Potager — rédaction interne', NULL, TRUE, FALSE)
ON CONFLICT (code) DO NOTHING;

-- ── [US-166] Apport taxonomique + rattachement d'origine sur les familles ────
ALTER TABLE familles_botaniques
    ADD COLUMN IF NOT EXISTS nom_scientifique VARCHAR NULL;

ALTER TABLE familles_botaniques
    ADD COLUMN IF NOT EXISTS source_id INTEGER NULL REFERENCES referentiel_source(id);

CREATE INDEX IF NOT EXISTS idx_familles_botaniques_source
    ON familles_botaniques (source_id);

COMMENT ON COLUMN familles_botaniques.nom_scientifique IS
    'US-166 — Nom scientifique de la famille (''Solanaceae''), importé de Wikidata (CC0). '
    'NULL = non renseigné, jamais deviné.';

COMMENT ON COLUMN familles_botaniques.source_id IS
    'US-166/CA1-CA5 — Origine de la ligne. Relue par l''import pour ne jamais écraser '
    'une correction humaine, et suivie par la requête de retrait de source (CA4).';

-- ── [CA4] Traçabilité du rattachement culture → famille ──────────────────────
ALTER TABLE culture_config
    ADD COLUMN IF NOT EXISTS famille_source_id INTEGER NULL REFERENCES referentiel_source(id);

CREATE INDEX IF NOT EXISTS idx_culture_config_famille_source
    ON culture_config (famille_source_id);

COMMENT ON COLUMN culture_config.famille_source_id IS
    'US-166/CA3 — Origine du rattachement famille_id (import ''wikidata'' ou correction '
    '''saisie_manuelle''), jamais l''origine de la fiche culture_config elle-même, qui '
    'naît de la dictée du jardinier. NULL = rattachement antérieur à l''US.';

-- ── Backfill : ce que la v37 a semé vient de la rédaction interne ────────────
UPDATE familles_botaniques
   SET source_id = (SELECT id FROM referentiel_source WHERE code = 'redaction_interne')
 WHERE source_id IS NULL;

UPDATE culture_config
   SET famille_source_id = (SELECT id FROM referentiel_source WHERE code = 'redaction_interne')
 WHERE famille_source_id IS NULL
   AND famille_id IS NOT NULL;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'referentiel_source'
ORDER BY ordinal_position;

SELECT code, licence, partageable, importee, date_dernier_import
FROM referentiel_source
ORDER BY code;

-- [CA4] La requête de retrait de source, telle qu'elle sera réellement posée.
SELECT s.code,
       (SELECT COUNT(*) FROM familles_botaniques f WHERE f.source_id = s.id)      AS familles,
       (SELECT COUNT(*) FROM culture_config c WHERE c.famille_source_id = s.id)   AS rattachements_culture
FROM referentiel_source s
ORDER BY s.code;

-- Aucune donnée sans origine (CA3) : ces deux compteurs doivent être à zéro.
SELECT COUNT(*) AS familles_sans_origine FROM familles_botaniques WHERE source_id IS NULL;
SELECT COUNT(*) AS rattachements_sans_origine
FROM culture_config WHERE famille_id IS NOT NULL AND famille_source_id IS NULL;
