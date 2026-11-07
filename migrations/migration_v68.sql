-- =============================================================================
-- migration_v68.sql — Une proposition, deux fenêtres (US-272)
-- =============================================================================
-- Une proposition née dans la PWA part aussi dans Telegram dès sa création
-- (D13). Au changement d'état, sa carte Telegram est RÉÉCRITE (F2, F3) : il
-- faut donc garder l'identifiant du message qui la porte.
--
--   propositions
--     telegram_chat_id    BIGINT NULL — le chat où la carte a été postée
--     telegram_message_id BIGINT NULL — le message à réécrire (editMessageText)
--         NULL : pas de carte dans Telegram (compte sans Telegram lié, envoi
--         perdu, ou carte antérieure à US-272). La règle « la première réponse
--         l'emporte » (F1) ne dépend PAS de ces colonnes.
--
--   users
--     invitation_telegram_le TIMESTAMP NULL — [CA9] le jour où un compte sans
--         Telegram lié a été invité à le lier, depuis le panneau. Une seule fois.
--
-- Aucune donnée à reprendre. RLS inchangée (propositions : migration_v61).
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v68.sql
-- =============================================================================

BEGIN;

ALTER TABLE propositions ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT NULL;
ALTER TABLE propositions ADD COLUMN IF NOT EXISTS telegram_message_id BIGINT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS invitation_telegram_le TIMESTAMP NULL;

COMMIT;
