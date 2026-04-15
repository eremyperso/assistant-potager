-- =============================================================================
-- migration_v12.sql — Suppression du champ dénormalisé evenements.parcelle
--                   + Ajout colonne origine_graines_id (traçabilité pépinière)
-- =============================================================================
-- Prérequis : migration_v11.sql (parcelle_id FK remplie)
--
-- Ce que fait cette migration :
--   1. Crée la parcelle "Non localisé" pour les événements orphelins
--   2. Assigne les orphelins (parcelle_id IS NULL) à cette parcelle
--   3. Supprime la colonne evenements.parcelle (texte dénormalisé)
--   4. Ajoute la colonne origine_graines_id (auto-FK pour traçabilité pépinière)
--
-- Idempotent : utilise IF NOT EXISTS / ON CONFLICT, safe à rejouer.
--
-- Exécution :
--   psql -U potager_user -d potager -f migration_v12.sql
-- =============================================================================

-- [1] Créer la parcelle "Non localisé" pour les événements sans parcelle
INSERT INTO parcelles (nom, nom_normalise, ordre, actif)
VALUES ('Non localisé', 'nonlocalize', 9999, true)
ON CONFLICT (nom_normalise) DO NOTHING;

-- [2] Assigner les événements orphelins à "Non localisé"
UPDATE evenements
SET parcelle_id = (SELECT id FROM parcelles WHERE nom_normalise = 'nonlocalize')
WHERE parcelle_id IS NULL;

-- [3] Vérification : aucun événement ne doit rester sans parcelle_id
SELECT COUNT(*) AS orphelins_restants FROM evenements WHERE parcelle_id IS NULL;
-- Attendu : 0

-- [4] Supprimer la colonne texte dénormalisée (PostgreSQL uniquement)
ALTER TABLE evenements DROP COLUMN IF EXISTS parcelle;

-- [5] Ajouter la colonne de traçabilité pépinière (semis → godet → plantation)
ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS origine_graines_id INTEGER
        REFERENCES evenements(id) ON DELETE SET NULL;

-- [6] Vérification post-migration
SELECT
    COUNT(*)                                                AS total_evenements,
    COUNT(*) FILTER (WHERE parcelle_id IS NOT NULL)        AS avec_parcelle_fk,
    COUNT(*) FILTER (WHERE origine_graines_id IS NOT NULL) AS avec_origine_graines
FROM evenements;
