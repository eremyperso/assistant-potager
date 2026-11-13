-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v76.sql — annule migration_v76.sql [US-326]
-- ═════════════════════════════════════════════════════════════════════════════
-- Perd la géométrie posée (emprise, places, formes, rotations) et les positions
-- de rang dites : le plan retombe sur la numérotation d'installation d'US-198.
-- Aucune quantité, aucun geste n'est perdu. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE evenements DROP CONSTRAINT IF EXISTS ck_evenements_rang_position;
ALTER TABLE evenements DROP COLUMN IF EXISTS rang_longueur_m;
ALTER TABLE evenements DROP COLUMN IF EXISTS rang_position;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS ck_parcelles_geometrie;
ALTER TABLE parcelles DROP COLUMN IF EXISTS sens_rangs;
ALTER TABLE parcelles DROP COLUMN IF EXISTS rotation_deg;
ALTER TABLE parcelles DROP COLUMN IF EXISTS largeur_m;
ALTER TABLE parcelles DROP COLUMN IF EXISTS y_m;
ALTER TABLE parcelles DROP COLUMN IF EXISTS x_m;
ALTER TABLE parcelles DROP COLUMN IF EXISTS forme;

ALTER TABLE potagers DROP CONSTRAINT IF EXISTS ck_potagers_geometrie;
ALTER TABLE potagers DROP COLUMN IF EXISTS orientation_nord;
ALTER TABLE potagers DROP COLUMN IF EXISTS angle_deg;
ALTER TABLE potagers DROP COLUMN IF EXISTS emprise_largeur_m;
ALTER TABLE potagers DROP COLUMN IF EXISTS emprise_longueur_m;

COMMIT;
