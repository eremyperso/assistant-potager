-- =============================================================================
-- migration_v29.sql — Cycle de vie du potager : actif / archivé / supprimé (US-080)
-- =============================================================================
-- Ajoute sur `potagers` l'état explicite du LIEU physique (jamais celui d'une
-- campagne culturale, cf. docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md §2.3) :
--   * etat        : 'actif' | 'archive' | 'supprime' — valeurs SANS accent en
--                   base, les libellés accentués restent côté affichage
--   * archive_le  : horodatage de l'archivage (US-083)
--   * supprime_le : horodatage du soft-delete, point de départ du délai de
--                   grâce avant purge physique (US-084)
--
-- Purement structurelle : aucun écran, aucune commande bot ne change. 100 %
-- des potagers existants sont backfillés à 'actif' — personne ne perçoit
-- de différence (CA2, CA8).
--
-- Idempotent : IF NOT EXISTS sur les colonnes et l'index, garde sur pg_constraint
-- pour la contrainte CHECK, backfill borné par `WHERE etat IS NULL`.
-- Rollback : migrations/rollback_v29.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- [CA1] Les trois colonnes du cycle de vie.
-- Le DEFAULT 'actif' backfille déjà les lignes existantes (CA2) ; le UPDATE
-- ci-dessous n'est qu'un filet si la colonne avait été créée sans défaut.
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS etat        VARCHAR(20) NOT NULL DEFAULT 'actif';
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS archive_le  TIMESTAMP NULL;
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS supprime_le TIMESTAMP NULL;

-- [CA2, CA3] Backfill idempotent — aucun potager existant ne change de comportement.
UPDATE potagers SET etat = 'actif' WHERE etat IS NULL;

-- [CA1, CA3] Contrainte de domaine, ajoutée une seule fois.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_potagers_etat'
    ) THEN
        ALTER TABLE potagers
            ADD CONSTRAINT ck_potagers_etat
            CHECK (etat IN ('actif', 'archive', 'supprime'));
    END IF;
END$$;

-- Le filtrage par état est désormais sur le chemin de TOUTE lecture des
-- potagers d'un utilisateur (app/services/potager_actif.py).
CREATE INDEX IF NOT EXISTS idx_potagers_etat ON potagers (etat);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'potagers'
  AND column_name IN ('etat', 'archive_le', 'supprime_le')
ORDER BY column_name;

SELECT etat, COUNT(*) AS nb_potagers FROM potagers GROUP BY etat;
