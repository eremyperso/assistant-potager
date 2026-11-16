-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v75.sql — [US-309] Chiffrer chaque appel d'après une grille tarifaire versionnée
-- ═════════════════════════════════════════════════════════════════════════════
-- `conso_tokens` gagne trois colonnes, toutes NULLABLES (l'existant n'est pas chiffré à la
-- migration : `tools/chiffrer_historique.py` le rejoue, en simulation par défaut) :
--   * fournisseur    : qui a servi l'appel (groq | mistral | <fournisseur compatible>).
--   * cout_micro_eur : coût estimé en micro-euros ENTIERS, figé à l'écriture au tarif public
--                      de la grille en vigueur (même au palier gratuit). NULL = non chiffrable
--                      (modèle absent de la grille) ; jamais un coût inventé.
--   * tarif_version  : identifiant de la grille (data/tarifs/tarifs_llm.json) qui a servi au calcul.
-- Reprise anticipée des colonnes de coût d'US-188 (BYOK), qui garde l'origine de la clé,
-- l'identifiant de requête du fournisseur et la réconciliation avec une facture tierce.
--
-- Additive, sans RLS ajoutée. Idempotente. Rollback : rollback_v75.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE conso_tokens
    ADD COLUMN IF NOT EXISTS fournisseur    VARCHAR(40) NULL,
    ADD COLUMN IF NOT EXISTS cout_micro_eur BIGINT      NULL,
    ADD COLUMN IF NOT EXISTS tarif_version  VARCHAR(40) NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_conso_tokens_cout_positif') THEN
        ALTER TABLE conso_tokens
            ADD CONSTRAINT ck_conso_tokens_cout_positif
            CHECK (cout_micro_eur IS NULL OR cout_micro_eur >= 0);
    END IF;
END $$;

COMMENT ON COLUMN conso_tokens.fournisseur IS
    '[US-309] groq | mistral | fournisseur compatible ; NULL avant v75';
COMMENT ON COLUMN conso_tokens.cout_micro_eur IS
    '[US-309] Coût estimé en micro-euros entiers, figé au tarif public de tarif_version ; NULL = non chiffré';
COMMENT ON COLUMN conso_tokens.tarif_version IS
    '[US-309] Version de la grille data/tarifs/tarifs_llm.json qui a servi au calcul ; NULL = jamais chiffrée';

COMMIT;
