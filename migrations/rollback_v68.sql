-- =============================================================================
-- rollback_v68.sql — Annule « une proposition, deux fenêtres » (US-272)
-- =============================================================================
-- ⚠️ Les cartes déjà postées dans Telegram ne seront plus réécrites ; la règle
-- « la première réponse l'emporte » reste intacte. Les comptes sans Telegram
-- seront invités à nouveau une fois.
-- =============================================================================

BEGIN;

ALTER TABLE propositions DROP COLUMN IF EXISTS telegram_message_id;
ALTER TABLE propositions DROP COLUMN IF EXISTS telegram_chat_id;
ALTER TABLE users DROP COLUMN IF EXISTS invitation_telegram_le;

COMMIT;
