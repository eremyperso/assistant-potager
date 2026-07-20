-- =============================================================================
-- migration_v21.sql — Potager actif par utilisateur (US-046)
-- =============================================================================
-- [US-046] Ajoute la colonne mémorisant le potager actuellement sélectionné
-- par chaque utilisateur — utilisée pour construire le TenantContext de
-- chaque requête (bot Telegram et API web), à la place de la valeur en dur
-- DEFAULT_POTAGER_ID = 1 utilisée jusqu'ici (US-041/US-044/US-045).
--
-- Nullable : un utilisateur peut ne pas avoir encore de potager actif choisi
-- (sélection automatique silencieuse s'il n'a qu'un seul potager — CA1 — ou
-- choix explicite via /potager / le sélecteur PWA sinon — CA2).
--
-- Idempotent : ADD COLUMN IF NOT EXISTS.
-- Rollback : migrations/rollback_v21.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS potager_actif_id INTEGER REFERENCES potagers(id);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'potager_actif_id';
