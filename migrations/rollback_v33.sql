-- =============================================================================
-- rollback_v33.sql — Annule migration_v33.sql (backfill unité pied/pieds →
-- plants, US-168)
-- =============================================================================
-- Restaure sur `evenements.unite` les valeurs sauvegardées avant le backfill
-- (table _backfill_v33_unite_avant), puis supprime cette table de sauvegarde.
-- Contrairement à un simple UPDATE inverse ('plants' → 'pieds'), ceci restitue
-- la valeur EXACTE de chaque ligne (certaines étaient 'pied', d'autres
-- 'pieds').
--
-- Ne rejouer que si aucune nouvelle saisie n'a réutilisé entre-temps l'une de
-- ces lignes avec une autre unité — le rollback écraserait alors une valeur
-- plus récente et légitime par l'ancienne.
-- =============================================================================

BEGIN;

UPDATE evenements e
SET unite = b.unite_avant
FROM _backfill_v33_unite_avant b
WHERE e.id = b.evenement_id;

DROP TABLE IF EXISTS _backfill_v33_unite_avant;

COMMIT;
