-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v73.sql — [US-306] Provenance de chaque appel au modèle
-- ═════════════════════════════════════════════════════════════════════════════
-- `conso_tokens.provenance` dit d'où vient la ligne : un jardinier (`usage`), une
-- campagne de mesure de tools/ (`mesure`), le harnais ou le mode test (`test`), une
-- tâche sans utilisateur (`fond`). Les lignes d'avant la colonne reçoivent
-- `historique` : AUCUNE reclassification heuristique (une ligne mal classée
-- fausserait durablement les séries) ; les vues d'administration l'excluent
-- par défaut.
--
-- NOT NULL DEFAULT 'historique' : une ligne écrite par un processus qui ne connaît
-- pas encore la colonne (déploiement en deux temps) retombe sur `historique` au
-- lieu d'échouer. Le nom est distinct de l'« origine de la clé » d'US-188.
-- Idempotente. Rollback : rollback_v73.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE conso_tokens
    ADD COLUMN IF NOT EXISTS provenance VARCHAR(12) NOT NULL DEFAULT 'historique';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_conso_tokens_provenance') THEN
        ALTER TABLE conso_tokens
            ADD CONSTRAINT ck_conso_tokens_provenance
            CHECK (provenance IN ('usage', 'mesure', 'test', 'fond', 'historique'));
    END IF;
END $$;

COMMENT ON COLUMN conso_tokens.provenance IS
    '[US-306] usage | mesure | test | fond | historique (lignes d''avant la colonne, jamais reclassées)';

COMMIT;
