-- =============================================================================
-- rollback_v55.sql — Annule migration_v55.sql (numéro de lot de semis, US-209)
-- =============================================================================
-- Retire `evenements.numero_lot`, son index et `potagers.compteur_lots`.
--
-- Perte : les numéros de lot attribués — ceux que le jardinier a pu écrire sur ses
-- étiquettes. Un nouveau jeu de migration repartirait de 1 dans l'ordre des dates.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces colonnes : `database/models.py`, `database/numerotation_lots.py`,
-- `utils/stock.py`, `GET /pepiniere/lots` et la commande `/lot`.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS ux_evenements_potager_numero_lot;
ALTER TABLE evenements DROP CONSTRAINT IF EXISTS ck_evenements_numero_lot_semis_seul;
ALTER TABLE evenements DROP COLUMN IF EXISTS numero_lot;
ALTER TABLE potagers DROP COLUMN IF EXISTS compteur_lots;

COMMIT;
