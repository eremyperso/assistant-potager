-- migration_v2.sql
-- À exécuter UNE SEULE FOIS si vous avez déjà une table 'evenements'
-- Si la table n'existe pas, elle sera créée automatiquement au démarrage.

ALTER TABLE evenements ADD COLUMN IF NOT EXISTS culture        VARCHAR;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS variete        VARCHAR;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS parcelle       VARCHAR;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS rang           VARCHAR;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS traitement     VARCHAR;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS texte_original VARCHAR;

-- Recopier 'produit' vers 'culture' pour les données existantes (si colonne encore présente)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'evenements' AND column_name = 'produit'
  ) THEN
    UPDATE evenements SET culture = produit WHERE culture IS NULL AND produit IS NOT NULL;
  END IF;
END $$;

-- Vérification : doit lister toutes les colonnes
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'evenements'
ORDER BY ordinal_position;
