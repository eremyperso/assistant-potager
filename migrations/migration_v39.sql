-- =============================================================================
-- migration_v39.sql — Attributs agronomiques de conduite sur culture_config (US-161)
-- =============================================================================
-- [CA1] `culture_config` porte aujourd'hui quatre informations : type d'organe
-- récolté, description agronomique libre, espacement, surface au sol. C'est trop
-- peu pour composer une fiche. Cette migration ajoute les attributs de conduite
-- manquants — exposition, besoin en eau, profondeur de semis, rusticité minimale
-- — et rien d'autre. Tous NULLABLE, aucune colonne existante supprimée ni
-- renommée : c'est l'invariant projet de migration incrémentale non cassante,
-- et c'est aussi ce qui garantit la non-régression du CA11 (type d'organe,
-- stock végétatif/reproducteur, écrans Stocks et Statistiques lisent exactement
-- les mêmes colonnes qu'avant).
--
-- [CA2] Les deux attributs qualitatifs prennent leurs valeurs dans un
-- vocabulaire fermé — exposition parmi 'plein soleil' | 'mi-ombre' | 'ombre',
-- besoin en eau parmi 'faible' | 'moyen' | 'élevé'. La validation vit dans
-- `app/services/attributs_culture.py`, seul point d'écriture traversé par
-- l'import comme par le bot, et NON dans une contrainte CHECK : le vocabulaire
-- est une décision produit révisable (une exposition 'ombre légère' se
-- discutera), et un CHECK la figerait dans le schéma. Le type reste VARCHAR
-- pour la même raison — un ENUM Postgres ferait de chaque ajout un ALTER TYPE.
-- Ce n'est pas pour autant du texte libre : rien n'écrit ces colonnes hors du
-- service, et le refus y est testé (tests/test_us161_attributs_agronomiques.py).
--
-- [CA3] Chaque valeur porte SA source, rattachée au registre d'US-166 — une
-- colonne d'origine par attribut, et non une origine de ligne. C'est ce qui
-- rend le CA6 tenable : une profondeur corrigée à la main survit à un rejeu
-- d'import sans geler pour autant l'exposition, que l'import doit continuer de
-- rafraîchir. Aucun attribut orphelin : une valeur dont on ne sait plus d'où
-- elle vient ne peut ni être défendue au jardinier, ni retirée proprement si sa
-- source devient litigieuse.
--
-- [CA4] Aucun DEFAULT, aucun backfill de valeur : un attribut non renseigné
-- reste NULL et s'affiche « non renseigné ». Il n'est jamais deviné, jamais
-- moyenné, jamais complété par un modèle de langage.
--
-- [CA7] Ce script ne crée AUCUNE ligne culture_config. Le pré-remplissage se
-- fait par le script d'import d'US-166 (`tools/importer_referentiel.py`), qui
-- se limite aux dix cultures du périmètre initial — jamais par une migration.
-- 14 des 54 configurations mesurées le 25/08/2026 ne portent aucun événement :
-- peupler les écrans de cultures jamais cultivées est un risque constaté.
--
-- [CA8/CA9] Aucune colonne de calendrier (fenêtre de semis, durée, date) : elles
-- relèvent d'US-068. Aucune relation (association, rotation, bioagresseur) :
-- ce sont des arêtes, elles relèvent d'US-162 et d'US-163.
--
-- ⚠️ Coordination avec US-067 (migration_v37) et US-068 : les trois touchent
-- `culture_config`. Celle-ci s'applique APRÈS la v38, dont elle réutilise la
-- table `referentiel_source` pour ses quatre clés étrangères.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS uniquement.
-- Rollback : migrations/rollback_v39.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ── [CA1, CA2] Les quatre attributs de conduite ──────────────────────────────
ALTER TABLE culture_config
    ADD COLUMN IF NOT EXISTS exposition          VARCHAR NULL,
    ADD COLUMN IF NOT EXISTS besoin_eau          VARCHAR NULL,
    ADD COLUMN IF NOT EXISTS profondeur_semis_cm DOUBLE PRECISION NULL,
    ADD COLUMN IF NOT EXISTS rusticite_min_c     DOUBLE PRECISION NULL;

COMMENT ON COLUMN culture_config.exposition IS
    'US-161/CA2 — Vocabulaire fermé : ''plein soleil'' | ''mi-ombre'' | ''ombre''. '
    'Validé par app/services/attributs_culture.py, jamais du texte libre. '
    'NULL = non renseigné (CA4), jamais deviné.';

COMMENT ON COLUMN culture_config.besoin_eau IS
    'US-161/CA2 — Vocabulaire fermé : ''faible'' | ''moyen'' | ''élevé''. '
    'NULL = non renseigné (CA4), jamais deviné.';

COMMENT ON COLUMN culture_config.profondeur_semis_cm IS
    'US-161/CA10 — Profondeur de semis en cm. Provient exclusivement de l''import '
    'd''US-166 ou de la saisie du jardinier : aucun chiffre n''est produit par un '
    'modèle de langage. NULL = non renseigné.';

COMMENT ON COLUMN culture_config.rusticite_min_c IS
    'US-161/CA10 — Température minimale supportée, en °C (négative pour une culture '
    'rustique). Même garde-fou que profondeur_semis_cm : aucun chiffre produit par '
    'un modèle. NULL = non renseigné.';

-- ── [CA3] Une origine par attribut, rattachée au registre d'US-166 ───────────
ALTER TABLE culture_config
    ADD COLUMN IF NOT EXISTS exposition_source_id       INTEGER NULL REFERENCES referentiel_source(id),
    ADD COLUMN IF NOT EXISTS besoin_eau_source_id       INTEGER NULL REFERENCES referentiel_source(id),
    ADD COLUMN IF NOT EXISTS profondeur_semis_source_id INTEGER NULL REFERENCES referentiel_source(id),
    ADD COLUMN IF NOT EXISTS rusticite_min_source_id    INTEGER NULL REFERENCES referentiel_source(id);

COMMENT ON COLUMN culture_config.exposition_source_id IS
    'US-161/CA3 — Origine de la valeur `exposition` (''wikidata'', ''redaction_interne'', '
    'ou ''saisie_manuelle'' pour une correction au bot). Relue par l''import pour ne '
    'jamais écraser une correction du jardinier (CA6). NULL = attribut non renseigné.';

COMMENT ON COLUMN culture_config.besoin_eau_source_id IS
    'US-161/CA3 — Origine de la valeur `besoin_eau`. Voir exposition_source_id.';

COMMENT ON COLUMN culture_config.profondeur_semis_source_id IS
    'US-161/CA3 — Origine de la valeur `profondeur_semis_cm`. Voir exposition_source_id.';

COMMENT ON COLUMN culture_config.rusticite_min_source_id IS
    'US-161/CA3 — Origine de la valeur `rusticite_min_c`. Voir exposition_source_id.';

COMMIT;

-- Vérification post-migration ------------------------------------------------

-- [CA1] Les huit colonnes existent et sont toutes nullables.
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'culture_config'
  AND column_name IN ('exposition', 'besoin_eau', 'profondeur_semis_cm', 'rusticite_min_c',
                      'exposition_source_id', 'besoin_eau_source_id',
                      'profondeur_semis_source_id', 'rusticite_min_source_id')
ORDER BY column_name;

-- [CA4/CA7] Aucune valeur n'a été semée par la migration : ces quatre compteurs
-- doivent être à zéro juste après application.
SELECT COUNT(*) FILTER (WHERE exposition          IS NOT NULL) AS exposition_renseignee,
       COUNT(*) FILTER (WHERE besoin_eau          IS NOT NULL) AS besoin_eau_renseigne,
       COUNT(*) FILTER (WHERE profondeur_semis_cm IS NOT NULL) AS profondeur_renseignee,
       COUNT(*) FILTER (WHERE rusticite_min_c     IS NOT NULL) AS rusticite_renseignee,
       COUNT(*)                                                AS total_configurations
FROM culture_config;

-- [CA3] Aucun attribut orphelin : une valeur renseignée porte toujours son
-- origine. Ces quatre compteurs doivent rester à zéro après chaque import.
SELECT COUNT(*) FILTER (WHERE exposition          IS NOT NULL AND exposition_source_id       IS NULL) AS exposition_sans_origine,
       COUNT(*) FILTER (WHERE besoin_eau          IS NOT NULL AND besoin_eau_source_id       IS NULL) AS besoin_eau_sans_origine,
       COUNT(*) FILTER (WHERE profondeur_semis_cm IS NOT NULL AND profondeur_semis_source_id IS NULL) AS profondeur_sans_origine,
       COUNT(*) FILTER (WHERE rusticite_min_c     IS NOT NULL AND rusticite_min_source_id    IS NULL) AS rusticite_sans_origine
FROM culture_config;

-- [CA8] Aucune colonne de calendrier n'a été introduite : ce compteur vaut zéro.
SELECT COUNT(*) AS colonnes_de_calendrier
FROM information_schema.columns
WHERE table_name = 'culture_config'
  AND (column_name LIKE '%semis_debut%' OR column_name LIKE '%semis_fin%'
       OR column_name LIKE '%date%' OR column_name LIKE '%duree%'
       OR column_name LIKE '%germination%' OR column_name LIKE '%fenetre%');
