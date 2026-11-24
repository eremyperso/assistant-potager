-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v81.sql — annule migration_v81.sql [US-343]
-- ═════════════════════════════════════════════════════════════════════════════
-- Perd les messages complets des tours de la boucle à capacités : le fil retombe sur la
-- phrase et la réponse de chaque échange. Aucune phrase, aucune réponse, aucun geste n'est
-- perdu. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation DROP COLUMN IF EXISTS messages;

COMMIT;
