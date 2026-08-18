-- =============================================================================
-- migration_v28.sql — Type de sol de la parcelle (US-058)
-- =============================================================================
-- Ajoute la colonne `type_sol` (texte libre, ex. "Limoneux", "Argileux") sur
-- `parcelles`, saisie à l'étape "Première parcelle" de l'assistant de création
-- du premier potager. Purement informative à ce stade — non exploitée par le
-- calcul de stock/plan (cf. utils/parcelles.py, database/models.py).
--
-- Idempotent : IF NOT EXISTS sur l'ajout de colonne.
-- Rollback : migrations/rollback_v28.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS type_sol VARCHAR(50);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'parcelles'
  AND column_name = 'type_sol';
