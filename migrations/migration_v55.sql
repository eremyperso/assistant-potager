-- =============================================================================
-- migration_v55.sql — Numéro de lot de semis en pépinière (US-209)
-- =============================================================================
-- Un lot de pépinière n'avait que l'identifiant technique de son semis, global à
-- toute l'application. Le jardinier veut un numéro COURT, à écrire au crayon sur
-- l'étiquette de la barquette (« lot 128 »).
--
-- [CA1] `evenements.numero_lot` : entier NULLABLE, unique PAR POTAGER (index
--       partiel), attribué dans l'ordre de création à partir de 1. Seul un semis
--       en porte un (CHECK). Jamais l'identifiant de l'événement : un identifiant
--       global laisserait deviner l'activité des autres potagers.
--       `potagers.compteur_lots` : dernier numéro attribué. Le numéro suivant se
--       prend par UPDATE … compteur_lots + 1 dans la transaction du semis : la
--       ligne du potager est verrouillée, deux semis simultanés ne se croisent
--       pas, et un numéro n'est jamais réutilisé (supprimer un semis ne fait pas
--       reculer le compteur).
--
-- [CA3] REPRISE — numéroter n'est pas supposer : c'est identifier. Les semis du
--       même ensemble que `GET /pepiniere/lots` (parcelle absente ou marquée
--       pépinière, culture connue) sont numérotés potager par potager, dans
--       l'ordre des dates puis des identifiants, À LA SUITE du plus grand numéro
--       déjà attribué. Ne touche que les lignes NULL : rejouée, elle ne
--       renumérote rien. Le compteur est ensuite aligné (jamais abaissé).
--
-- ⚠️ La reprise est exécutée TELLE QUELLE par les tests
-- (tests/test_us209_numero_lot.py, entre les marqueurs REPRISE).
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v55.sql
-- =============================================================================

BEGIN;

ALTER TABLE potagers
    ADD COLUMN IF NOT EXISTS compteur_lots INTEGER NOT NULL DEFAULT 0;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS numero_lot INTEGER;

ALTER TABLE evenements
    DROP CONSTRAINT IF EXISTS ck_evenements_numero_lot_semis_seul;
ALTER TABLE evenements
    ADD CONSTRAINT ck_evenements_numero_lot_semis_seul
    CHECK (numero_lot IS NULL OR type_action = 'semis');

COMMENT ON COLUMN evenements.numero_lot IS
    '[US-209] Numéro court du lot de pépinière, unique par potager, jamais réutilisé. '
    'Distinct de evenements.id.';

-- -- REPRISE:DEBUT --
WITH a_numeroter AS (
    SELECT e.id, e.potager_id,
           ROW_NUMBER() OVER (PARTITION BY e.potager_id ORDER BY e.date, e.id) AS rang
    FROM evenements e
    LEFT JOIN parcelles p ON p.id = e.parcelle_id
    WHERE e.type_action = 'semis'
      AND e.culture IS NOT NULL
      AND e.numero_lot IS NULL
      AND (e.parcelle_id IS NULL OR p.est_pepiniere IS TRUE)
      AND (e.contexte_semis IS NULL OR e.contexte_semis <> 'pleine_terre')
), deja AS (
    SELECT potager_id, MAX(numero_lot) AS maxi
    FROM evenements
    WHERE numero_lot IS NOT NULL
    GROUP BY potager_id
)
UPDATE evenements
SET numero_lot = a.rang + COALESCE(d.maxi, 0)
FROM a_numeroter a
LEFT JOIN deja d ON d.potager_id = a.potager_id
WHERE evenements.id = a.id;

UPDATE potagers
SET compteur_lots = COALESCE((
        SELECT MAX(e.numero_lot) FROM evenements e WHERE e.potager_id = potagers.id
    ), 0)
WHERE COALESCE((
        SELECT MAX(e.numero_lot) FROM evenements e WHERE e.potager_id = potagers.id
    ), 0) > compteur_lots;
-- -- REPRISE:FIN --

CREATE UNIQUE INDEX IF NOT EXISTS ux_evenements_potager_numero_lot
    ON evenements (potager_id, numero_lot)
    WHERE numero_lot IS NOT NULL;

COMMIT;

-- ── Vérifications ────────────────────────────────────────────────────────────
-- DOIT valoir 0 : aucun doublon de numéro dans un potager.
SELECT COUNT(*) AS doublons
FROM (SELECT potager_id, numero_lot FROM evenements
      WHERE numero_lot IS NOT NULL
      GROUP BY potager_id, numero_lot HAVING COUNT(*) > 1) d;

SELECT potager_id, COUNT(numero_lot) AS nb_lots, MAX(numero_lot) AS dernier
FROM evenements GROUP BY potager_id ORDER BY potager_id;
