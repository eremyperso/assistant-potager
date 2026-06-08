-- =============================================================================
-- migration_v14.sql — US-029 : Chaînage plantation → godet (source_evenement_ids)
-- =============================================================================
-- Ce script :
--   1. Ajoute la colonne source_evenement_ids (TEXT NULL) sur evenements
--   2. Rétropopule source_evenement_ids + variete pour les plantations sans variété
--      dont la culture a exactement 1 variété en mise_en_godet
--   3. Rétropopule origine_graines_id pour les mise_en_godet dont la culture
--      a exactement 1 semis correspondant (avec variété identique si précisée)
--
-- Idempotent : ADD COLUMN IF NOT EXISTS
-- Rétrocompatibilité : les événements sans lien conservent le comportement heuristique CA6
-- =============================================================================

-- [1] Nouvelle colonne
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS source_evenement_ids TEXT NULL;

-- [2] Rétroalimentation plantations sans variété
--     Condition : culture a exactement 1 variété distincte non-NULL en mise_en_godet
WITH cultures_variete_unique AS (
    SELECT
        LOWER(culture)        AS culture_lower,
        MAX(variete)          AS variete,
        MIN(id)               AS godet_id   -- plus ancien godet = source FIFO
    FROM evenements
    WHERE type_action    = 'mise_en_godet'
      AND culture        IS NOT NULL
      AND variete        IS NOT NULL
    GROUP BY LOWER(culture)
    HAVING COUNT(DISTINCT variete) = 1
)
UPDATE evenements AS p
SET variete              = u.variete,
    source_evenement_ids = u.godet_id::TEXT
FROM cultures_variete_unique u
WHERE p.type_action          = 'plantation'
  AND p.variete              IS NULL
  AND p.source_evenement_ids IS NULL
  AND p.culture              IS NOT NULL
  AND LOWER(p.culture)       = u.culture_lower;

-- [3] Rétroalimentation origine_graines_id pour mise_en_godet sans lien semis
--     Condition : un seul semis correspondant (même culture + même variété si précisée)
WITH semis_uniques AS (
    SELECT
        LOWER(culture) AS culture_lower,
        variete,
        MIN(id)        AS semis_id
    FROM evenements
    WHERE type_action = 'semis'
      AND culture     IS NOT NULL
    GROUP BY LOWER(culture), variete
    HAVING COUNT(*) = 1
)
UPDATE evenements AS g
SET origine_graines_id = s.semis_id
FROM semis_uniques s
WHERE g.type_action        = 'mise_en_godet'
  AND g.origine_graines_id IS NULL
  AND g.culture            IS NOT NULL
  AND LOWER(g.culture)     = s.culture_lower
  AND (g.variete = s.variete OR (g.variete IS NULL AND s.variete IS NULL));

-- [4] Vérification
SELECT
    'plantations rétroliées' AS label,
    COUNT(*)                 AS nb
FROM evenements
WHERE type_action          = 'plantation'
  AND source_evenement_ids IS NOT NULL
  AND variete              IS NOT NULL
UNION ALL
SELECT
    'godets rétroliés au semis' AS label,
    COUNT(*)                    AS nb
FROM evenements
WHERE type_action       = 'mise_en_godet'
  AND origine_graines_id IS NOT NULL;
