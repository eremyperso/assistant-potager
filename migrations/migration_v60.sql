-- =============================================================================
-- migration_v60.sql — Profil d'échange du compagnon (US-258)
-- =============================================================================
-- Le compagnon appelle le jardinier par son prénom et parle sur le ton qu'il a
-- choisi. Le profil est propre au COUPLE (jardinier × potager) : un même
-- jardinier peut préférer « sobre » sur un potager partagé et « voisin » sur le
-- sien (CA8). Ce couple est déjà la clé de `potager_membres` : le profil s'y
-- ajoute en colonnes, sans nouvelle table.
--
--   prenom_compagnon    VARCHAR(30) NULL — NULL = jamais donné (le compagnon le demande) ;
--   registre_compagnon  VARCHAR(12) NOT NULL DEFAULT 'voisin' — sobre | voisin | gouailleur ;
--   compagnon_accueilli BOOLEAN NOT NULL DEFAULT FALSE — le premier contact a eu lieu.
--
-- Aucun backfill : chaque membre existant est accueilli une fois, au premier
-- échange suivant la mise en service, et garde le registre par défaut.
-- Pas de RLS ajoutée : `potager_membres` garde la protection qu'elle avait.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v60.sql
-- =============================================================================

BEGIN;

ALTER TABLE potager_membres
    ADD COLUMN IF NOT EXISTS prenom_compagnon    VARCHAR(30),
    ADD COLUMN IF NOT EXISTS registre_compagnon  VARCHAR(12) NOT NULL DEFAULT 'voisin',
    ADD COLUMN IF NOT EXISTS compagnon_accueilli BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_registre_compagnon;
ALTER TABLE potager_membres
    ADD CONSTRAINT ck_potager_membres_registre_compagnon
    CHECK (registre_compagnon IN ('sobre', 'voisin', 'gouailleur'));

COMMENT ON COLUMN potager_membres.prenom_compagnon IS
    '[US-258] Prénom dont le compagnon appelle ce jardinier sur ce potager. NULL = jamais donné.';
COMMENT ON COLUMN potager_membres.registre_compagnon IS
    '[US-258] Ton du compagnon : sobre | voisin (défaut) | gouailleur. Change le ton, jamais le fond.';

COMMIT;
