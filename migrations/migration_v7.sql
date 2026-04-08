-- =============================================================================
-- migration_v7.sql — Pépinière : ajout champs mise en godet
-- =============================================================================
-- Ajoute les colonnes nécessaires au nouveau type d'action `mise_en_godet`.
-- Idempotent : utilise IF NOT EXISTS, safe à rejouer.
--
-- Exécution depuis psql :
--   psql -U potager_user -d potager -f migration_v7.sql
-- =============================================================================

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS nb_graines_semees INTEGER DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS nb_plants_godets   INTEGER DEFAULT NULL;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'evenements'
  AND column_name IN ('nb_graines_semees', 'nb_plants_godets')
ORDER BY column_name;
-- Attendu : 2 lignes, type integer, nullable YES
