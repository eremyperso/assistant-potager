-- =============================================================================
-- migration_v27.sql — Procédure stockée supprimer_utilisateur (admin/pgAdmin)
-- =============================================================================
-- Supprime définitivement un utilisateur et tout ce qui lui appartient :
-- potagers dont il est propriétaire (vidés intégralement : évènements,
-- parcelles, fiches culture personnalisées, adhésions des autres membres,
-- invitations liées), ses propres adhésions à des potagers d'autrui, ses
-- invitations émises, sa liaison Telegram.
--
-- Aucune contrainte FK du schéma n'est en ON DELETE CASCADE (cf. ERD pgAdmin) :
-- l'ordre ci-dessous est nécessaire, notamment le détachement préalable de
-- users.potager_actif_id (chez le propriétaire ou un autre membre), sinon
-- users_potager_actif_id_fkey bloque le DELETE FROM potagers.
--
-- Usage (pgAdmin4, Query Tool — un CALL est une commande SQL standard, pas
-- une méta-commande psql, donc pas besoin de l'outil PSQL) :
--
--   CALL supprimer_utilisateur(12);
--
-- ⚠️ Exécutée avec le rôle qui l'appelle. Si l'exécution est un jour accordée
-- à app_user (GRANT EXECUTE), noter que evenements/parcelles/culture_config
-- sont protégées par RLS (migration_v18) et que le rôle propriétaire des
-- migrations, lui, contourne RLS (ENABLE, pas FORCE) — donc un appel via
-- pgAdmin (connecté en admin) supprime bien tout, un appel futur en tant
-- qu'app_user serait lui filtré par app.potager_id.
--
-- Idempotent : DROP PROCEDURE IF EXISTS avant CREATE (CREATE OR REPLACE
-- PROCEDURE existe depuis PG14, mais on garde le même style que les POLICY
-- de migration_v18.sql pour rester portable).
-- Rollback : migrations/rollback_v27.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

DROP PROCEDURE IF EXISTS supprimer_utilisateur(integer);

CREATE PROCEDURE supprimer_utilisateur(p_user_id integer)
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id) THEN
        RAISE EXCEPTION 'Utilisateur % introuvable', p_user_id;
    END IF;

    -- Détacher tout potager_actif_id (le sien ou celui d'un autre membre)
    -- pointant vers un potager que cet utilisateur possède.
    UPDATE users
    SET potager_actif_id = NULL
    WHERE potager_actif_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);

    -- Vider les potagers dont l'utilisateur est propriétaire.
    DELETE FROM culture_config
        WHERE potager_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);
    DELETE FROM evenements
        WHERE potager_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);
    DELETE FROM parcelles
        WHERE potager_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);
    DELETE FROM invitations
        WHERE potager_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);
    DELETE FROM potager_membres
        WHERE potager_id IN (SELECT id FROM potagers WHERE proprietaire_id = p_user_id);

    DELETE FROM potagers WHERE proprietaire_id = p_user_id;

    -- Ce qui reste, propre à l'utilisateur (potagers d'autrui).
    DELETE FROM invitations       WHERE invite_par_id = p_user_id;
    DELETE FROM liaisons_telegram WHERE user_id = p_user_id;
    DELETE FROM potager_membres   WHERE user_id = p_user_id;

    DELETE FROM users WHERE id = p_user_id;

    RAISE NOTICE 'Utilisateur % supprimé', p_user_id;
END;
$$;

COMMIT;

-- Vérification post-migration
SELECT proname, pronargs FROM pg_proc WHERE proname = 'supprimer_utilisateur';
