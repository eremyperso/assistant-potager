-- =============================================================================
-- migration_v71.sql — Préférences vocales du compagnon (US-300)
-- =============================================================================
-- Une table de COMPTE, sans RLS (même traitement que `files_gestes_reglages`) :
-- le choix de la voix de Gaston est une préférence de la PERSONNE, pas du potager.
-- Un jardinier membre de deux potagers garde sa voix. Une ligne par jardinier,
-- créée à la première écriture (une lecture sans ligne rend les défauts, sans rien
-- écrire). Le service ne lit et n'écrit que la ligne du jardinier connecté.
--
--   mode_vocal    faux par défaut : sans lui, ni micro ni lecture dans la PWA
--   voix_id       identifiant Mistral de la voix (ex. voice_592) ; NULL = voix
--                 par défaut de la configuration (VOIX_PAR_DEFAUT)
--   lecture_auto  vrai par défaut : lecture de la réponse après une dictée
--
-- Supprimer un compte supprime ses préférences (ON DELETE CASCADE).
-- Additive, aucune donnée à reprendre. Idempotent. Rôle propriétaire de la base.
-- Rollback : migrations/rollback_v71.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS preferences_voix (
    user_id      INTEGER     PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    mode_vocal   BOOLEAN     NOT NULL DEFAULT FALSE,
    voix_id      VARCHAR(64) NULL,
    lecture_auto BOOLEAN     NOT NULL DEFAULT TRUE,
    maj_le       TIMESTAMP   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE preferences_voix IS
    'US-300 — réglages vocaux du compagnon, par jardinier (table de compte, sans RLS).';
COMMENT ON COLUMN preferences_voix.voix_id IS
    'US-300 — identifiant Mistral de la voix ; NULL = VOIX_PAR_DEFAUT de la configuration.';

COMMIT;
