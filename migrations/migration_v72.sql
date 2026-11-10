-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v72.sql — [US-303] Résumé parlé d'une réponse du compagnon
-- ═════════════════════════════════════════════════════════════════════════════
-- Le compagnon vocal de la PWA lit une version COURTE de sa réponse (1 à 2 phrases),
-- distincte du texte affiché. Elle est calculée à la première demande de lecture,
-- puis gardée sur l'échange : une seconde lecture ne rappelle pas le modèle.
--
-- Colonne nulle : un échange jamais lu n'a pas de résumé. La RLS stricte de la
-- table (migration_v61) s'applique telle quelle.
-- Idempotente. Rollback : rollback_v72.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation
    ADD COLUMN IF NOT EXISTS texte_oral TEXT NULL;

COMMENT ON COLUMN echanges_conversation.texte_oral IS
    '[US-303] Résumé parlé de texte_compagnon, calculé à la première lecture (NULL = jamais lu)';

COMMIT;
