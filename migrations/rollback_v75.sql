-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v75.sql — annule migration_v75.sql [US-309]
-- ═════════════════════════════════════════════════════════════════════════════
-- Retire le fournisseur, le coût et la version de grille : les coûts figés sont perdus
-- (ils se rejouent avec tools/chiffrer_historique.py, au tarif d'une grille donnée). Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE conso_tokens DROP CONSTRAINT IF EXISTS ck_conso_tokens_cout_positif;
ALTER TABLE conso_tokens
    DROP COLUMN IF EXISTS tarif_version,
    DROP COLUMN IF EXISTS cout_micro_eur,
    DROP COLUMN IF EXISTS fournisseur;

COMMIT;
