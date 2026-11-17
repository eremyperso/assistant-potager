-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v78.sql — [US-310] Index de lecture des agrégats de pilotage
-- ═════════════════════════════════════════════════════════════════════════════
-- Les routes /admin/pilotage/... lisent `conso_tokens` sur une période, filtrée par provenance
-- (usage + fond par défaut), toutes les valeurs de potager confondues. Deux index :
--   * idx_conso_tokens_date_provenance : le chemin de toute lecture (période + provenance).
--   * idx_conso_tokens_cree_le         : le pas horaire d'une journée et l'ordre des lignes.
-- `echange_ref` est déjà indexé (v74). Aucune colonne, aucune donnée, aucune RLS ajoutée.
-- PRÉREQUIS : v73 (colonne `provenance`). À jouer dans l'ordre, après v73, v74 et v75 : sur une base
-- où elles manquent, PostgreSQL répond « column "provenance" does not exist » (42703).
-- Idempotente. Rollback : rollback_v78.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE INDEX IF NOT EXISTS idx_conso_tokens_date_provenance ON conso_tokens (date, provenance);
CREATE INDEX IF NOT EXISTS idx_conso_tokens_cree_le         ON conso_tokens (cree_le);

COMMIT;
