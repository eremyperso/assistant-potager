-- ═════════════════════════════════════════════════════════════════════════════
-- migration_v76.sql — [US-326] Géométrie du potager, de ses parcelles et de leurs rangs
-- ═════════════════════════════════════════════════════════════════════════════
-- Le plan sur vue du dessus (ÉPIC 19) a besoin de la place réelle des parcelles :
--
-- potagers  : emprise (longueur × largeur, m), angle du plan, orientation du nord
--             (8 directions). Le fond photo et son recalage relèvent d'US-335.
-- parcelles : forme (planche, bac, butte, serre, pépinière — champ libre de toute
--             cohérence avec `abri` et `type_pepiniere`, arbitrage P7), position
--             x / y (m), largeur (m), rotation (°), sens des rangs. La LONGUEUR
--             reste `longueur_m` (US-225) : pas de second champ (G1). x et y NULL =
--             parcelle « à placer ».
-- evenements : position du rang (1 à nb_rangs) dite à l'installation, et longueur
--             occupée sur un rang partagé (m). `rang` reste le MULTIPLICATEUR
--             d'US-198 (« sur 3 rangs ») : les deux sens du mot ne se mélangent pas.
--
-- Nullable partout, AUCUN backfill de position : une parcelle existante est à
-- placer, une culture existante garde la numérotation d'installation (G3).
-- Les migrations v73 à v75 appartiennent à la branche du pilotage LLM (US-306→309).
-- Idempotente. Rollback : rollback_v76.sql.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── Potager ─────────────────────────────────────────────────────────────────
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS emprise_longueur_m NUMERIC(6,1) NULL;
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS emprise_largeur_m  NUMERIC(6,1) NULL;
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS angle_deg          NUMERIC(5,1) NULL;
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS orientation_nord   VARCHAR(2)   NULL;

ALTER TABLE potagers DROP CONSTRAINT IF EXISTS ck_potagers_geometrie;
ALTER TABLE potagers ADD CONSTRAINT ck_potagers_geometrie CHECK (
    (emprise_longueur_m IS NULL OR emprise_longueur_m BETWEEN 1 AND 2000)
    AND (emprise_largeur_m IS NULL OR emprise_largeur_m BETWEEN 1 AND 2000)
    AND (angle_deg IS NULL OR (angle_deg >= 0 AND angle_deg < 360))
    AND (orientation_nord IS NULL OR orientation_nord IN ('n','ne','e','se','s','so','o','no'))
);

-- ── Parcelle ────────────────────────────────────────────────────────────────
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS forme        VARCHAR(12)  NULL;
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS x_m          NUMERIC(6,2) NULL;
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS y_m          NUMERIC(6,2) NULL;
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS largeur_m    NUMERIC(5,1) NULL;
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS rotation_deg NUMERIC(5,1) NULL;
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS sens_rangs   VARCHAR(10)  NULL;

ALTER TABLE parcelles DROP CONSTRAINT IF EXISTS ck_parcelles_geometrie;
ALTER TABLE parcelles ADD CONSTRAINT ck_parcelles_geometrie CHECK (
    (forme IS NULL OR forme IN ('planche','bac','butte','serre','pepiniere'))
    -- placée = les DEUX coordonnées, jamais une seule
    AND ((x_m IS NULL) = (y_m IS NULL))
    AND (x_m IS NULL OR (x_m BETWEEN 0 AND 2000 AND y_m BETWEEN 0 AND 2000))
    AND (largeur_m IS NULL OR largeur_m BETWEEN 0.1 AND 200)
    AND (rotation_deg IS NULL OR (rotation_deg >= 0 AND rotation_deg < 360))
    AND (sens_rangs IS NULL OR sens_rangs IN ('longueur','travers'))
);

-- ── Position du rang d'une culture ──────────────────────────────────────────
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS rang_position   SMALLINT     NULL;
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS rang_longueur_m NUMERIC(5,1) NULL;

ALTER TABLE evenements DROP CONSTRAINT IF EXISTS ck_evenements_rang_position;
ALTER TABLE evenements ADD CONSTRAINT ck_evenements_rang_position CHECK (
    (rang_position IS NULL OR rang_position BETWEEN 1 AND 99)
    AND (rang_longueur_m IS NULL OR (rang_longueur_m > 0 AND rang_position IS NOT NULL))
);

COMMENT ON COLUMN parcelles.x_m IS '[US-326] Position sur le plan (m) ; NULL avec y_m = parcelle à placer';
COMMENT ON COLUMN parcelles.sens_rangs IS '[US-326] longueur | travers';
COMMENT ON COLUMN evenements.rang_position IS '[US-326] POSITION du premier rang (1 à nb_rangs) ; rang reste le multiplicateur';
COMMENT ON COLUMN evenements.rang_longueur_m IS '[US-326 / P4] Longueur occupée sur un rang partagé (m) ; exige la longueur de la parcelle';

COMMIT;
