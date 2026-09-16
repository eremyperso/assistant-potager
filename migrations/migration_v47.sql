-- =============================================================================
-- migration_v47.sql — Contexte du semis : pépinière ou pleine terre (US-069)
-- =============================================================================
-- Un semis suit l'un de deux itinéraires — semé hors sol puis repiqué, ou semé
-- directement en place — et les deux s'enregistraient sous le même
-- `type_action = 'semis'`. Or le référentiel d'US-068 porte DEUX fenêtres de
-- semis : sans savoir de quelle filière relève un semis, impossible de choisir
-- la sienne, ni d'ancrer la projection d'US-070.
--
-- [CA1] `evenements.contexte_semis` : 'pepiniere' | 'pleine_terre' | NULL.
-- NULLABLE : un semis dont le contexte n'est pas dit, et que le jardinier n'a
-- pas confirmé, reste sans contexte (CA3, CA9). Seul un semis en porte un —
-- c'est le seul CHECK posé ici, parce que c'est un fait de modèle et non un
-- vocabulaire révisable. Le vocabulaire, lui, n'est pas contraint (même
-- arbitrage que migration_v39, v43, v46) : il est validé par
-- app/services/contexte_semis.py, seul point de normalisation.
--
-- [CA8] Aucune colonne existante n'est touchée, aucun calcul ne lit cette
-- colonne pour déduire un stock : le stock continue de se déduire de
-- `parcelles.est_pepiniere` et du chaînage `origine_graines_id`.
--
-- [CA5] REPRISE DES SEMIS EXISTANTS — la seule supposition permise est celle
-- qui n'en est pas une : un semis dont une mise en godet est CHAÎNÉE
-- (`origine_graines_id`) a été repiqué, donc semé en pépinière. Tous les autres
-- restent NULL — un semis sans godet chaîné n'est PAS présumé en pleine terre :
-- il peut être un semis de pépinière pas encore repiqué, ou un godet saisi sans
-- rattachement. La requête ne touche que des lignes NULL : rejouée, elle ne
-- réécrit rien, et n'écrase jamais une correction du jardinier.
--
-- ⚠️ Cette requête est exécutée TELLE QUELLE par les tests
-- (tests/test_us069_contexte_semis.py, entre les marqueurs REPRISE) : ne pas la
-- recopier ailleurs, la modifier ici.
--
-- À exécuter avec le rôle propriétaire de la base (RLS sur `evenements`).
-- Idempotent : ADD COLUMN IF NOT EXISTS, contrainte recréée, UPDATE sur NULL.
-- Rollback : migrations/rollback_v47.sql
-- =============================================================================

BEGIN;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS contexte_semis VARCHAR(16);

ALTER TABLE evenements
    DROP CONSTRAINT IF EXISTS ck_evenements_contexte_semis_semis_seul;
ALTER TABLE evenements
    ADD CONSTRAINT ck_evenements_contexte_semis_semis_seul
    CHECK (contexte_semis IS NULL OR type_action = 'semis');

COMMENT ON COLUMN evenements.contexte_semis IS
    '[US-069] Contexte d''un semis : pepiniere | pleine_terre | NULL (non précisé). '
    'Jamais présumé. Ne pilote aucun calcul de stock.';

-- -- REPRISE:DEBUT --
UPDATE evenements
SET contexte_semis = 'pepiniere'
WHERE type_action = 'semis'
  AND contexte_semis IS NULL
  AND EXISTS (
      SELECT 1
      FROM evenements godet
      WHERE godet.type_action = 'mise_en_godet'
        AND godet.origine_graines_id = evenements.id
  );
-- -- REPRISE:FIN --

COMMIT;

-- ── Vérifications ────────────────────────────────────────────────────────────
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'evenements' AND column_name = 'contexte_semis';

-- [CA5] Répartition après reprise : aucune ligne 'pleine_terre' ne peut venir
-- de cette migration.
SELECT COALESCE(contexte_semis, '(sans contexte)') AS contexte, COUNT(*) AS nb_semis
FROM evenements
WHERE type_action = 'semis'
GROUP BY contexte_semis
ORDER BY contexte;

-- [CA1] DOIT valoir 0.
SELECT COUNT(*) AS contexte_hors_semis
FROM evenements
WHERE contexte_semis IS NOT NULL AND type_action <> 'semis';
