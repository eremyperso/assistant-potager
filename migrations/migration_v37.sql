-- =============================================================================
-- migration_v37.sql — Table de référence des familles botaniques (US-067)
-- =============================================================================
-- [CA1] Crée `familles_botaniques` — table à part plutôt que colonne texte sur
-- `culture_config` : le délai de retour recommandé est un attribut de la
-- FAMILLE, pas de la culture. En colonne, il se duplique sur chaque culture de
-- la famille et devient incohérent à la première correction (le jardinier
-- corrige "Solanacées : 4 ans" sur la tomate, la pomme de terre reste à 3).
--
-- Aucune colonne potager_id sur `familles_botaniques` : une famille botanique
-- est un fait, identique quel que soit le potager (CA7) — cohérent avec le
-- constat mesuré le 25/08/2026 (`culture_config` est déjà à 100% potager_id
-- NULL en dev, voir docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.1).
--
-- `culture_config.famille_id` (nullable, CA3) référence la table. Une culture
-- sans famille renseignée reste utilisable partout, simplement regroupée sous
-- "Autres" côté application (jamais stocké tel quel — c'est un repli d'affichage).
--
-- [CA2] Pré-remplissage : les familles usuelles (portées depuis l'ancienne
-- table figée `frontend/src/lib/familles.js`, US-061) sont semées avec un
-- délai de retour usuellement recommandé en jardinage amateur — valeur de
-- départ corrigible depuis le bot (CA14), jamais présentée comme une vérité
-- scientifique absolue. `culture_config.famille_id` est ensuite pré-rempli
-- pour les cultures déjà connues, SANS jamais écraser une valeur déjà écrite
-- (WHERE famille_id IS NULL) : sûr à rejouer, y compris après une correction
-- manuelle du jardinier entre deux exécutions.
--
-- Familles volontairement laissées sans délai (NULL, CA12/CA13) : Lamiacée —
-- aromatiques essentiellement vivaces (basilic excepté), la notion de
-- rotation annuelle ne s'y applique pas franchement ; sert aussi de cas réel
-- pour tester "famille sans délai" au-delà du seul repli "Autres".
--
-- [Point de vigilance US-067] Ce pré-remplissage ne CRÉE jamais de ligne
-- culture_config : il ne fait que compléter des fiches déjà existantes
-- (UPDATE, pas INSERT). Peupler des fiches pour des cultures jamais utilisées
-- est précisément le risque de "cultures fantômes" mesuré le 25/08/2026 (14
-- des 54 configurations existantes ne portent déjà aucun événement).
--
-- Idempotent : CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, INSERT
-- ... ON CONFLICT DO NOTHING, UPDATE gardé par IS NULL.
-- Rollback : migrations/rollback_v37.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS familles_botaniques (
    id                  SERIAL PRIMARY KEY,
    nom                 VARCHAR NOT NULL,
    -- [CA6] Casse/accents indifférents à la résolution — même stratégie que
    -- Parcelle.nom_normalise (strip + lower + unidecode).
    nom_normalise       VARCHAR NOT NULL,
    -- [CA12/CA13] Délai de retour recommandé, en années. NULL = non renseigné :
    -- n'empêche aucun affichage, rend seulement l'avertissement de rotation
    -- indisponible pour les cultures de cette famille (US-163).
    delai_retour_annees INTEGER NULL,
    CONSTRAINT uq_familles_botaniques_nom UNIQUE (nom),
    CONSTRAINT uq_familles_botaniques_nom_normalise UNIQUE (nom_normalise)
);

ALTER TABLE culture_config
    ADD COLUMN IF NOT EXISTS famille_id INTEGER NULL REFERENCES familles_botaniques(id);

CREATE INDEX IF NOT EXISTS idx_culture_config_famille
    ON culture_config (famille_id);

COMMENT ON TABLE familles_botaniques IS
    'US-067 — Référentiel des familles botaniques : libellé + délai de retour '
    'recommandé (années, nullable). Pas de potager_id : un fait, pas une '
    'préférence de jardinier (CA7).';

COMMENT ON COLUMN culture_config.famille_id IS
    'US-067/CA1 — Famille botanique de la culture. NULL = non renseignée, '
    'affichée "Autres" (CA3) — jamais stocké tel quel.';

-- ── [CA2] Semis des familles usuelles ────────────────────────────────────────
INSERT INTO familles_botaniques (nom, nom_normalise, delai_retour_annees) VALUES
    ('Solanacée',     'solanacee',     4),
    ('Cucurbitacée',  'cucurbitacee',  2),
    ('Alliacée',      'alliacee',      3),
    ('Chénopodiacée', 'chenopodiacee', 3),
    ('Lamiacée',      'lamiacee',      NULL),
    ('Rosacée',       'rosacee',       3),
    ('Apiacée',       'apiacee',       3),
    ('Brassicacée',   'brassicacee',   4),
    ('Astéracée',     'asteracee',     2),
    ('Fabacée',       'fabacee',       2),
    ('Poacée',        'poacee',        2)
ON CONFLICT (nom_normalise) DO NOTHING;

-- ── [CA2] Pré-remplissage culture_config.famille_id ──────────────────────────
-- Appariement sur LOWER(TRIM(nom)), variantes accentuées ET non accentuées
-- listées explicitement (pas d'extension `unaccent`, jamais utilisée ailleurs
-- dans ce projet — toute la normalisation applicative se fait en Python via
-- `unidecode`, jamais côté SQL).

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'solanacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('tomate', 'aubergine', 'poivron', 'piment', 'pomme de terre');

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'cucurbitacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN (
    'courgette', 'courge', 'butternut', 'potiron', 'potimarron', 'concombre',
    'cornichon', 'melon', 'pasteque', 'pastèque', 'patisson', 'pâtisson'
);

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'alliacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('oignon', 'echalote', 'échalote', 'ail', 'poireau', 'ciboulette');

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'chenopodiacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN (
    'betterave', 'blette', 'epinard', 'épinard', 'epinard perpetuel', 'épinard perpétuel'
);

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'lamiacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('basilic', 'menthe', 'thym', 'romarin');

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'rosacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('fraise', 'framboise');

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'apiacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN (
    'carotte', 'persil', 'celeri', 'céleri', 'panais', 'fenouil', 'coriandre'
);

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'brassicacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN (
    'chou', 'radis', 'navet', 'roquette', 'brocoli',
    'chou de bruxelles', 'chou frise', 'chou frisé'
);

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'asteracee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('salade', 'laitue', 'mache', 'mâche', 'artichaut');

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'fabacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN (
    'haricot', 'pois', 'feve', 'fève',
    'petit pois', 'pois gourmand', 'haricot grimpant'
);

UPDATE culture_config SET famille_id = (SELECT id FROM familles_botaniques WHERE nom_normalise = 'poacee')
WHERE famille_id IS NULL AND LOWER(TRIM(nom)) IN ('mais', 'maïs');

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'familles_botaniques'
ORDER BY ordinal_position;

SELECT f.nom, f.delai_retour_annees, COUNT(c.id) AS nb_cultures_rattachees
FROM familles_botaniques f
LEFT JOIN culture_config c ON c.famille_id = f.id
GROUP BY f.nom, f.delai_retour_annees
ORDER BY f.nom;

SELECT COUNT(*) AS cultures_sans_famille FROM culture_config WHERE famille_id IS NULL;
