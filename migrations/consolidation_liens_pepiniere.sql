-- ============================================================
-- Consolidation liens pépinière — 2026-06-09
-- Harmonisation variétés + liens origine_graines_id + source_evenement_ids
-- ============================================================

BEGIN;

-- ── BLOC 1 : Harmonisation des noms de variété ────────────────

-- blette : "poirée verte" → "poirées"
UPDATE evenements SET variete = 'poirées'
WHERE culture = 'blette' AND variete = 'poirée verte';

-- courgette : "Gold Rush jaune" → "jaune"
UPDATE evenements SET variete = 'jaune'
WHERE culture = 'courgette' AND variete = 'Gold Rush jaune';

-- tomate : "ronde noire de Crimée" → "noire de Crimée"
UPDATE evenements SET variete = 'noire de Crimée'
WHERE culture = 'tomate' AND variete = 'ronde noire de Crimée';


-- ── BLOC 2 : Liens godet → semis (origine_graines_id) ────────

-- courgette/jaune (godet id=93) → semis id=56
UPDATE evenements SET origine_graines_id = 56
WHERE id = 93 AND type_action = 'mise_en_godet';


-- ── BLOC 3 : Liens plantation → godet(s) (source_evenement_ids) ──

-- blette/poirées
UPDATE evenements SET source_evenement_ids = '173'
WHERE id = 174 AND type_action = 'plantation';

-- cornichon/petit Paris
UPDATE evenements SET source_evenement_ids = '170'
WHERE id IN (171, 183) AND type_action = 'plantation';

-- courgette/verte
UPDATE evenements SET source_evenement_ids = '121'
WHERE id = 180 AND type_action = 'plantation';

-- courgette/jaune
UPDATE evenements SET source_evenement_ids = '93'
WHERE id = 179 AND type_action = 'plantation';

-- tomate/cerise
UPDATE evenements SET source_evenement_ids = '118'
WHERE id = 189 AND type_action = 'plantation';

-- tomate/noire de Crimée
UPDATE evenements SET source_evenement_ids = '116'
WHERE id = 193 AND type_action = 'plantation';

-- potiron (sans variété) — FIFO : lot le plus ancien d'abord (id=123)
UPDATE evenements SET source_evenement_ids = '123'
WHERE id = 195 AND type_action = 'plantation';

-- tomate/cœur de bœuf — allocation FIFO (godets id=114 puis id=120)
-- id=181 : 14 plants → 14 sur les 20 de id=114
UPDATE evenements SET source_evenement_ids = '114'
WHERE id = 181 AND type_action = 'plantation';

-- id=192 : 9 plants → 6 restants de id=114 + 3 de id=120
UPDATE evenements SET source_evenement_ids = '114;120'
WHERE id = 192 AND type_action = 'plantation';

-- id=194 : 3 plants → id=120
UPDATE evenements SET source_evenement_ids = '120'
WHERE id = 194 AND type_action = 'plantation';

-- id=197 : 3 plants → id=120
UPDATE evenements SET source_evenement_ids = '120'
WHERE id = 197 AND type_action = 'plantation';


-- ── VÉRIFICATION post-application ────────────────────────────

SELECT
    e.id,
    e.date::date,
    e.type_action,
    e.culture,
    e.variete,
    e.origine_graines_id,
    e.source_evenement_ids,
    CASE
        WHEN e.type_action = 'mise_en_godet' AND e.origine_graines_id IS NULL    THEN '⚠ semis manquant'
        WHEN e.type_action = 'plantation'    AND e.source_evenement_ids IS NULL   THEN '⚠ godet manquant'
        ELSE 'OK'
    END AS statut
FROM evenements e
WHERE e.id IN (
    93, 173, 174,
    170, 171, 183,
    121, 180,
    93, 179,
    118, 189,
    116, 193,
    123, 195,
    114, 120, 181, 192, 194, 197,
    56
)
ORDER BY e.culture, e.type_action, e.id;

COMMIT;
