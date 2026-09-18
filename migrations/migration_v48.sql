-- =============================================================================
-- migration_v48.sql — Altitude du potager (US-193)
-- =============================================================================
-- La zone climatique DÉDUITE d'un potager (US-068 / CA7) ne lisait que latitude
-- et longitude : jamais « montagnard », et Briançon (1 326 m) recevait le
-- calendrier océanique. La recherche de ville (Open-Meteo) renvoie déjà
-- l'altitude avec les coordonnées ; elle n'était simplement pas conservée.
--
-- [CA1] `potagers.altitude` : mètres, NULLABLE. NULL = inconnue — la zone
-- déduite ne suppose alors JAMAIS « montagnard » (CA3).
--
-- [CA3] REPRISE DES POTAGERS DÉJÀ LOCALISÉS — une altitude ne se calcule pas en
-- SQL : elle est lue auprès d'Open-Meteo par
--     python tools/renseigner_altitude_potagers.py
-- lancé JUSTE APRÈS les migrations (deploy.yml, deploy-dev.yml,
-- scripts/update_dev.ps1). L'outil ne touche que les lignes à altitude NULL et
-- coordonnées connues : rejoué, il ne réécrit rien.
--
-- [CA11] `zone_climatique` (le CHOIX du jardinier) n'est pas touchée : seule la
-- zone déduite, calculée à la lecture, peut changer.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : ADD COLUMN IF NOT EXISTS.
-- Rollback : migrations/rollback_v48.sql
-- =============================================================================

BEGIN;

ALTER TABLE potagers
    ADD COLUMN IF NOT EXISTS altitude DOUBLE PRECISION;

COMMENT ON COLUMN potagers.altitude IS
    'US-193 — altitude (m) de la ville du potager, renseignée avec latitude/longitude ; NULL = inconnue';

COMMIT;
