-- =============================================================================
-- migration_v46.sql — Référentiel de calendrier cultural (US-068)
-- =============================================================================
-- L'application ne savait rien du calendrier des cultures. Cette migration pose
-- le modèle des calendriers de semis — et non celui de la maquette :
--
--   culture_config ── itineraire_cultural   (« standard », « culture d'hiver »…)
--                        ├── fenetre_culturale   PAR ZONE climatique
--                        │     semis_pepiniere · semis_pleine_terre · recolte
--                        └── duree_culturale     COMMUNE à toutes les zones
--                              levee · recolte · repiquage
--   potagers.zone_climatique
--
-- [CA1] Une culture porte un ou plusieurs itinéraires — des CONDUITES, jamais
-- des variétés. Une culture sans itinéraire en lit un implicite, « standard »,
-- construit à la lecture : aucune ligne n'est semée pour cela.
--
-- [CA2, CA6] Une fenêtre par (itinéraire, zone, phase), au mois, bornes
-- incluses ; `mois_debut` > `mois_fin` chevauche la fin d'année. Une fenêtre
-- absente est une fenêtre VIDE.
--
-- [CA3, CA4] Une durée par (itinéraire, étape), en jours, fourchette possible,
-- ou mention libre (« vivace ») — jamais les deux (CHECK). Les durées ne sont
-- PAS déclinées par zone : le délai entre semis et récolte relève de la
-- physiologie de la plante, pas de la latitude.
--
-- [CA5] Aucune colonne d'écartement : `culture_config.espacement` et
-- `surface_m2` font foi.
--
-- [CA7, CA8] `potagers.zone_climatique` ne porte que le CHOIX du jardinier.
-- NULL = aucun choix : la zone se DÉDUIT de la localisation à la lecture
-- (app/services/calendrier_cultural.zone_depuis_localisation), puis retombe sur
-- la zone par défaut (CALENDRIER_ZONE_DEFAUT). Aucun backfill ici : réécrire la
-- règle de déduction en SQL en ferait deux définitions, qui divergeraient.
--
-- [CA11] `potager_id` NULL = calendrier partagé ; non NULL = calendrier
-- personnalisé d'un potager, qui remplace le partagé de même nom pour lui seul.
-- C'est la convention de fiche personnalisée de `culture_config` (migration_v16),
-- réappliquée ici parce qu'elle ne peut pas l'être sur `culture_config` même
-- (`nom` y est UNIQUE). `potager_id` est dénormalisé sur fenêtres et durées pour
-- porter la même policy RLS que `culture_bioagresseur`, sans jointure.
--
-- [CA9] Cette migration ne sème AUCUNE ligne de calendrier : le contenu arrive
-- par app/services/import_referentiel.py (bloc `cultures_calendriers`), qui
-- n'écrit que du partagé et ne crée aucune culture, ou par le bot (/calendrier).
--
-- [CA14, CA15] Aucune colonne existante n'est modifiée ; la seule colonne
-- ajoutée à une table existante (`potagers.zone_climatique`) est NULLABLE.
--
-- Pas de CHECK de vocabulaire sur `zone_climatique`, `phase` ni `etape` : même
-- arbitrage que migration_v39 et migration_v43 — fermé mais révisable en
-- produit, validé par app/services/calendrier_cultural.py, seul point
-- d'écriture. Les bornes numériques, elles, sont des faits : CHECK.
--
-- Droits de app_user : couverts par les DEFAULT PRIVILEGES de migration_v18.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS, CREATE TABLE/INDEX IF NOT EXISTS,
-- DROP POLICY IF EXISTS.
-- Rollback : migrations/rollback_v46.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ── [CA7] Zone climatique choisie par le jardinier ───────────────────────────
ALTER TABLE potagers ADD COLUMN IF NOT EXISTS zone_climatique VARCHAR(20) NULL;

COMMENT ON COLUMN potagers.zone_climatique IS
    'US-068/CA7 — Zone CHOISIE par le jardinier : oceanique | continental | mediterraneen | '
    'montagnard. NULL = aucun choix, zone déduite de la localisation à la lecture puis zone '
    'par défaut (CA8). Aucune zone déduite n''est jamais stockée ici.';

-- ── [CA1, CA11] Itinéraires culturaux ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS itineraire_cultural (
    id            SERIAL PRIMARY KEY,
    culture_id    INTEGER NOT NULL REFERENCES culture_config(id),
    nom           VARCHAR NOT NULL,
    nom_normalise VARCHAR NOT NULL,
    potager_id    INTEGER NULL REFERENCES potagers(id),
    source_id     INTEGER NOT NULL REFERENCES referentiel_source(id)
);

CREATE INDEX IF NOT EXISTS idx_itineraire_cultural_culture ON itineraire_cultural (culture_id);
CREATE INDEX IF NOT EXISTS idx_itineraire_cultural_potager ON itineraire_cultural (potager_id);
CREATE INDEX IF NOT EXISTS idx_itineraire_cultural_source  ON itineraire_cultural (source_id);

-- [CA11] Unicité PARTIELLE : un itinéraire partagé par (culture, nom), un
-- itinéraire personnalisé par (culture, nom, potager).
CREATE UNIQUE INDEX IF NOT EXISTS uq_itineraire_cultural_partage
    ON itineraire_cultural (culture_id, nom_normalise)
    WHERE potager_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_itineraire_cultural_local
    ON itineraire_cultural (culture_id, nom_normalise, potager_id)
    WHERE potager_id IS NOT NULL;

-- ── [CA2, CA6] Fenêtres conseillées, par zone ────────────────────────────────
CREATE TABLE IF NOT EXISTS fenetre_culturale (
    id              SERIAL PRIMARY KEY,
    itineraire_id   INTEGER NOT NULL REFERENCES itineraire_cultural(id) ON DELETE CASCADE,
    zone_climatique VARCHAR(20) NOT NULL,
    phase           VARCHAR(20) NOT NULL,
    mois_debut      INTEGER NOT NULL CHECK (mois_debut BETWEEN 1 AND 12),
    mois_fin        INTEGER NOT NULL CHECK (mois_fin BETWEEN 1 AND 12),
    potager_id      INTEGER NULL REFERENCES potagers(id),
    source_id       INTEGER NOT NULL REFERENCES referentiel_source(id),
    CONSTRAINT uq_fenetre_culturale UNIQUE (itineraire_id, zone_climatique, phase)
);

CREATE INDEX IF NOT EXISTS idx_fenetre_culturale_itineraire ON fenetre_culturale (itineraire_id);
CREATE INDEX IF NOT EXISTS idx_fenetre_culturale_potager    ON fenetre_culturale (potager_id);
CREATE INDEX IF NOT EXISTS idx_fenetre_culturale_source     ON fenetre_culturale (source_id);

-- ── [CA3, CA4] Durées conseillées, communes à toutes les zones ───────────────
CREATE TABLE IF NOT EXISTS duree_culturale (
    id            SERIAL PRIMARY KEY,
    itineraire_id INTEGER NOT NULL REFERENCES itineraire_cultural(id) ON DELETE CASCADE,
    etape         VARCHAR(20) NOT NULL,
    jours_min     INTEGER NULL CHECK (jours_min BETWEEN 1 AND 730),
    jours_max     INTEGER NULL CHECK (jours_max BETWEEN 1 AND 730),
    mention       VARCHAR(60) NULL,
    potager_id    INTEGER NULL REFERENCES potagers(id),
    source_id     INTEGER NOT NULL REFERENCES referentiel_source(id),
    CONSTRAINT uq_duree_culturale UNIQUE (itineraire_id, etape),
    -- [CA4] Un nombre de jours OU une mention, jamais les deux ni aucun.
    CONSTRAINT ck_duree_culturale_valeur CHECK (
        (jours_min IS NOT NULL AND jours_max IS NOT NULL AND jours_min <= jours_max AND mention IS NULL)
        OR (jours_min IS NULL AND jours_max IS NULL AND mention IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_duree_culturale_itineraire ON duree_culturale (itineraire_id);
CREATE INDEX IF NOT EXISTS idx_duree_culturale_potager    ON duree_culturale (potager_id);
CREATE INDEX IF NOT EXISTS idx_duree_culturale_source     ON duree_culturale (source_id);

-- ── [CA11] RLS — second verrou, motif culture_config de migration_v18 ────────
ALTER TABLE itineraire_cultural ENABLE ROW LEVEL SECURITY;
ALTER TABLE fenetre_culturale   ENABLE ROW LEVEL SECURITY;
ALTER TABLE duree_culturale     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_itineraire_cultural ON itineraire_cultural;
CREATE POLICY tenant_isolation_itineraire_cultural ON itineraire_cultural
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_fenetre_culturale ON fenetre_culturale;
CREATE POLICY tenant_isolation_fenetre_culturale ON fenetre_culturale
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_duree_culturale ON duree_culturale;
CREATE POLICY tenant_isolation_duree_culturale ON duree_culturale
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- ⚠️ Même conséquence que migration_v43 : une ligne PARTAGÉE n'est écrivable
-- que par le rôle propriétaire de la base. L'import d'un manifeste portant un
-- bloc `cultures_calendriers` tourne donc avec ce rôle, comme tout import.

COMMENT ON TABLE itineraire_cultural IS
    'US-068/CA1 — Itinéraire cultural (conduite, jamais variété). potager_id NULL = partagé, '
    'non NULL = calendrier personnalisé qui remplace le partagé de même nom pour ce potager (CA11).';

COMMENT ON TABLE fenetre_culturale IS
    'US-068/CA2, CA6 — Fenêtre conseillée par (itinéraire, zone, phase), au mois. Absente = vide. '
    'Aucune fenêtre n''est empruntée à une autre zone à la lecture (CA13).';

COMMENT ON TABLE duree_culturale IS
    'US-068/CA3, CA4 — Durée conseillée par (itinéraire, étape), en jours ou mention libre, '
    'commune à toutes les zones. Jamais présentée comme une date certaine.';

COMMIT;

-- ── Vérifications ────────────────────────────────────────────────────────────
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('itineraire_cultural', 'fenetre_culturale', 'duree_culturale')
ORDER BY table_name;

SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'potagers' AND column_name = 'zone_climatique';

-- [CA5] Contrôle structurel : aucune colonne d'écartement dupliquée. DOIT valoir 0.
SELECT COUNT(*) AS colonnes_ecartement_dupliquees
FROM information_schema.columns
WHERE table_name IN ('itineraire_cultural', 'fenetre_culturale', 'duree_culturale')
  AND (column_name ILIKE '%espacement%' OR column_name ILIKE '%surface%');
