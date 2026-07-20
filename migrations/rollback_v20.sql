-- =============================================================================
-- rollback_v20.sql — Annule migration_v20.sql (liaisons_telegram)
-- =============================================================================
-- [US-045] Supprime la table des codes de liaison. Les telegram_chat_id déjà
-- écrits sur `users` (liaisons déjà effectuées) ne sont PAS affectés — seule
-- la table des codes disparaît.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS liaisons_telegram;

COMMIT;
