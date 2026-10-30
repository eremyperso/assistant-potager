-- =============================================================================
-- migration_v63.sql — Calendrier personnalisé remplacé par le référentiel (US-279)
-- =============================================================================
-- La première correction d'un potager copie l'itinéraire partagé en itinéraire
-- personnalisé (US-068 / CA11), que l'import ne touche jamais (CA9). Pour dire
-- au jardinier que le référentiel a évolué DEPUIS sa copie, la copie mémorise
-- l'empreinte du partagé qu'elle a copié — ou qu'il a choisi de garder.
--
--   itineraire_cultural.empreinte_reference VARCHAR(64) NULL
--     NULL = base inconnue : copie faite avant cette migration (comparée alors
--     valeur par valeur au partagé), ou itinéraire partagé (jamais renseignée).
--
-- Aucun backfill : la base d'une copie existante n'a jamais été gardée, on ne
-- la reconstitue pas. Pas de RLS ajoutée : la policy d'`itineraire_cultural`
-- (migration_v46) couvre la colonne.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v63.sql
-- =============================================================================

BEGIN;

ALTER TABLE itineraire_cultural
    ADD COLUMN IF NOT EXISTS empreinte_reference VARCHAR(64);

COMMENT ON COLUMN itineraire_cultural.empreinte_reference IS
    '[US-279] Copie personnalisée : empreinte du partagé copié ou gardé. NULL = base inconnue.';

COMMIT;
