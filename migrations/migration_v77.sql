-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v77.sql — [US-323] Ce que le jardinier avait sous les yeux, gardé avec l'échange
-- ═════════════════════════════════════════════════════════════════════════════
-- Ouvert depuis le plan, le panneau du compagnon envoie un contexte d'écran (culture,
-- parcelle, rang) avec chaque phrase. `echanges_conversation.contexte` le garde, pour
-- mesurer son effet sur l'interprétation (CA6) : {"niveau", "parcelle_id", "parcelle",
-- "culture", "variete", "rang"}. NULL sans contexte (Telegram, conversation libre).
--
-- Additive, sans backfill, sans RLS ajoutée (celle de la table, v61, s'applique).
-- Les migrations v73 à v75 appartiennent à la branche du pilotage LLM (US-306→309).
-- Idempotente. Rollback : rollback_v77.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE echanges_conversation ADD COLUMN IF NOT EXISTS contexte JSONB NULL;

COMMENT ON COLUMN echanges_conversation.contexte IS
    '[US-323 / CA6] Contexte d''écran de la PWA (culture, parcelle, rang) ; NULL sans contexte';

COMMIT;
