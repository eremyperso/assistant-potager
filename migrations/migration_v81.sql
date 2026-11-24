-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v81.sql — [US-343] Le fil complet de la conversation, gardé avec l'échange
-- ═════════════════════════════════════════════════════════════════════════════
-- Un tour de la boucle à capacités (US-342) garde ses MESSAGES COMPLETS : la phrase du
-- jardinier, les appels d'outils avec leurs arguments, les résultats (datés, tronqués
-- selon la règle de `app/services/compagnon/fil.py`) et la réponse du compagnon. C'est ce
-- que la boucle relit au tour suivant. NULL pour un échange de l'ancien moteur : le fil le
-- relit alors en deux messages (phrase, réponse).
--
-- Même table, même RLS stricte par potager (v61), même purge à 30 jours
-- (`conversations.purger`, RGPD US-132) : la durée de conservation du fil est celle des
-- échanges. Additive, sans backfill. Idempotente. Rollback : rollback_v81.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation ADD COLUMN IF NOT EXISTS messages JSONB NULL;

COMMENT ON COLUMN echanges_conversation.messages IS
    '[US-343 / CA1] Messages complets du tour (phrase, appels d''outils, résultats datés, réponse) ; NULL pour l''ancien moteur';

COMMIT;
