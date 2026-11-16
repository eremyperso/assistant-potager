-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v74.sql — [US-307] Relier les appels d'un même échange, avec canal, version et unité
-- ═════════════════════════════════════════════════════════════════════════════
-- `conso_tokens` gagne quatre colonnes :
--   * echange_ref : l'échange (la réponse) auquel l'appel a servi — dictée, agent, résumé
--     parlé et voix d'une même réponse le partagent. Nul pour l'existant, indexé.
--   * canal       : telegram | pwa | mcp | fond | outil | inconnu. L'existant : inconnu.
--   * version_app : contenu du fichier VERSION au démarrage du processus. Nul pour l'existant.
--   * unite       : jeton | seconde | caractere — ce que tokens_in / tokens_out comptent.
--     L'existant est REJOUÉ d'après le type d'appel : dictee → seconde, voix → caractere,
--     le reste → jeton (aucune heuristique : c'est le type d'appel qui dit l'unité, US-299).
-- `echanges_conversation.echange_ref` retrouve les lignes de consommation d'un échange du
-- compagnon, SANS clé étrangère (la mesure ne bloque jamais la conversation).
--
-- Additive, sans RLS ajoutée. Idempotente. Rollback : rollback_v74.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE conso_tokens
    ADD COLUMN IF NOT EXISTS echange_ref VARCHAR(40) NULL,
    ADD COLUMN IF NOT EXISTS canal       VARCHAR(12) NOT NULL DEFAULT 'inconnu',
    ADD COLUMN IF NOT EXISTS version_app VARCHAR(40) NULL,
    ADD COLUMN IF NOT EXISTS unite       VARCHAR(10) NOT NULL DEFAULT 'jeton';

-- L'existant : l'unité se déduit du type d'appel. Rejouable (ne touche que ce qui diffère).
UPDATE conso_tokens SET unite = 'seconde'   WHERE appel_type = 'dictee' AND unite <> 'seconde';
UPDATE conso_tokens SET unite = 'caractere' WHERE appel_type = 'voix'   AND unite <> 'caractere';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_conso_tokens_canal') THEN
        ALTER TABLE conso_tokens
            ADD CONSTRAINT ck_conso_tokens_canal
            CHECK (canal IN ('telegram', 'pwa', 'mcp', 'fond', 'outil', 'inconnu'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_conso_tokens_unite') THEN
        ALTER TABLE conso_tokens
            ADD CONSTRAINT ck_conso_tokens_unite
            CHECK (unite IN ('jeton', 'seconde', 'caractere'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_conso_tokens_echange_ref ON conso_tokens (echange_ref);

ALTER TABLE echanges_conversation
    ADD COLUMN IF NOT EXISTS echange_ref VARCHAR(40) NULL;

CREATE INDEX IF NOT EXISTS ix_echanges_conversation_echange_ref ON echanges_conversation (echange_ref);

COMMENT ON COLUMN conso_tokens.echange_ref IS
    '[US-307] Identifiant de l''échange servi (sans clé étrangère) ; NULL = avant v74';
COMMENT ON COLUMN conso_tokens.canal IS
    '[US-307] telegram | pwa | mcp | fond | outil | inconnu';
COMMENT ON COLUMN conso_tokens.version_app IS
    '[US-307] Fichier VERSION lu au démarrage du processus';
COMMENT ON COLUMN conso_tokens.unite IS
    '[US-307] jeton | seconde | caractere — ce que tokens_in / tokens_out comptent';
COMMENT ON COLUMN echanges_conversation.echange_ref IS
    '[US-307] Retrouve les lignes de conso_tokens de cet échange';

COMMIT;
