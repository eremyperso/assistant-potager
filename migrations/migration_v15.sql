-- =============================================================================
-- migration_v15.sql — Distinction parcelle "pleine terre" vs "pépinière/serre"
-- =============================================================================
-- Prérequis : migration_v12.sql (parcelle "Non localisé" créée)
--
-- Ce que fait cette migration :
--   1. Ajoute parcelles.est_pepiniere (booléen, défaut false)
--   2. Marque la parcelle synthétique "Non localisé" comme pépinière — elle ne
--      représente jamais une vraie localisation en pleine terre.
--
-- Contexte métier : un semis rattaché à une parcelle "pépinière" (serre,
-- bacs à godets…) reste un semis pépinière tant qu'aucune plantation réelle
-- n'a eu lieu — même si son parcelle_id est renseigné. Voir
-- utils/stock.py::_cond_semis_pleine_terre.
--
-- Idempotent : utilise IF NOT EXISTS, safe à rejouer.
--
-- Exécution :
--   psql -U potager_user -d potager -f migration_v15.sql
--
-- Après application, marquer manuellement les parcelles pépinière/serre
-- existantes, ex. :
--   UPDATE parcelles SET est_pepiniere = true WHERE nom_normalise = 'testserre';
-- ou via le bot : /parcelle modifier <nom> pepiniere=true
-- =============================================================================

-- [1] Ajouter la colonne de classification
ALTER TABLE parcelles
    ADD COLUMN IF NOT EXISTS est_pepiniere BOOLEAN NOT NULL DEFAULT false;

-- [2] La parcelle "Non localisé" (migration_v12) n'est jamais une localisation
--     pleine terre
UPDATE parcelles SET est_pepiniere = true WHERE nom_normalise = 'nonlocalize';

-- [3] Vérification post-migration
SELECT nom, nom_normalise, est_pepiniere FROM parcelles ORDER BY ordre;
