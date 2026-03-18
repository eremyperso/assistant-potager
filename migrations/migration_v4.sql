-- Migration v4 — Suppression colonne produit (doublon de culture)
-- À exécuter UNE SEULE FOIS depuis pgAdmin ou psql
--
-- Vérification avant suppression (optionnel)
-- SELECT id, culture, produit FROM evenements WHERE culture != produit;
--
-- Suppression
ALTER TABLE evenements DROP COLUMN IF EXISTS produit;

-- Vérification après
-- \d evenements
