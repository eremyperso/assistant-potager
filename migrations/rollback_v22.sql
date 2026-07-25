-- =============================================================================
-- rollback_v22.sql — Annule migration_v22.sql (invitations)
-- =============================================================================
-- [US-048] Supprime la table des codes d'invitation. Les membres déjà insérés
-- dans potager_membres suite à une invitation acceptée ne sont PAS affectés —
-- seule la table des codes disparaît.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS invitations;

COMMIT;
