-- =============================================================================
-- migration_v67.sql — La question en attente du compagnon (US-284)
-- =============================================================================
-- « Supprime la planche » → « Laquelle : planche test ou plant tubercule ? » →
-- « la planche test » : la réponse courte arrive seule, sans verbe. Le compagnon
-- garde donc la question qu'il vient de poser sur l'échange qui la porte :
--
--   echanges_conversation
--     question JSONB NULL  — {"phrase": la phrase d'origine (ancrée),
--                             "question": le texte posé, "choix": [noms cités]}
--         Seul le DERNIER échange du jardinier dans ce potager compte, 10 minutes
--         au plus : la phrase suivante, quelle qu'elle soit, la consomme.
--
-- Aucune donnée à reprendre : NULL = pas de question en attente.
-- RLS inchangée (stricte par potager, migration_v61).
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v67.sql
-- =============================================================================

BEGIN;

ALTER TABLE echanges_conversation ADD COLUMN IF NOT EXISTS question JSONB NULL;

COMMIT;
