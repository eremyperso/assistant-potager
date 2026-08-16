-- =============================================================================
-- migration_v22.sql — Invitations à rejoindre un potager (US-048)
-- =============================================================================
-- [US-048] Table des codes d'invitation permettant à un owner de faire entrer
-- un nouveau membre dans son potager, avec un rôle proposé (editor|lecteur).
-- Même principe que liaisons_telegram (US-045 / migration_v20) : code court
-- unique, TTL calculé côté application, usage strictement unique.
--
-- code          : court, alphanumérique non ambigu (8 caractères), unique.
-- potager_id    : potager cible de l'invitation.
-- invite_par_id : compte (owner) ayant généré l'invitation.
-- email_invite  : optionnel — e-mail de la personne invitée (traçabilité,
--                 pas d'envoi automatique tant que l'infra mail n'existe pas).
-- role_propose  : rôle attribué à l'acceptation ('editor' | 'lecteur').
-- cree_le       : horodatage de génération.
-- expire_le     : cree_le + TTL (calculé côté application, 7 jours par défaut).
-- utilisee_le   : NULL tant que non consommée — usage strict à usage unique.
--
-- Idempotent : CREATE TABLE IF NOT EXISTS.
-- Rollback : migrations/rollback_v22.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS invitations (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(8) NOT NULL UNIQUE,
    potager_id    INTEGER NOT NULL REFERENCES potagers(id),
    invite_par_id INTEGER NOT NULL REFERENCES users(id),
    email_invite  VARCHAR(255) NULL,
    role_propose  VARCHAR(10) NOT NULL,
    cree_le       TIMESTAMP NOT NULL DEFAULT now(),
    expire_le     TIMESTAMP NOT NULL,
    utilisee_le   TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_invitations_code ON invitations (code);
CREATE INDEX IF NOT EXISTS idx_invitations_potager ON invitations (potager_id);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'invitations'
ORDER BY ordinal_position;
