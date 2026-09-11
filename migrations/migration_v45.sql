-- =============================================================================
-- migration_v45.sql — Symptômes et relation symptôme × bioagresseur (US-165)
-- =============================================================================
-- Pose les deux dernières tables du référentiel : une IDENTITÉ pour chaque
-- symptôme observable, et une arête PONDÉRÉE entre lui et les bioagresseurs
-- qu'il peut évoquer.
--
-- Ce que cette migration rend possible, et qui manquait : un jardinier qui
-- décrit « des taches marron sur les feuilles du bas de mes tomates » reçoit
-- aujourd'hui soit un silence, soit une fiche entière à lire. Le chaînon absent
-- n'était pas le texte — US-140 l'a écrit — mais la STRUCTURE qui relie des mots
-- de jardinier à des noms de bioagresseurs déjà rattachés à ses cultures.
--
-- [CA1] Un symptôme n'appartient à AUCUNE culture, et c'est la décision de
-- conception centrale de cette migration. « Des traits orange qui partent en
-- poussière » est le même symptôme sur l'ail et sur le poireau ; c'est le
-- CROISEMENT avec `culture_bioagresseur` (US-162) qui décide de la piste, pas le
-- symptôme. Une colonne `culture_id` ici aurait dupliqué chaque symptôme autant
-- de fois qu'il y a de cultures qui le montrent, et aurait rendu le cas de
-- désambiguïsation du CA14 — la rouille de l'ail contre celle du poireau —
-- structurellement impossible à traiter.
--
-- [CA1] `synonymes` est le CŒUR de la table, pas un complément. La mesure du
-- 25/08/2026 (docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md) a invalidé
-- l'hypothèse de départ : le vocabulaire des fiches est technique (« oïdium »,
-- « nécrose apicale »), celui des questions est courant (« poudre blanche »,
-- « cul noir »). Écrire les deux registres dans cette colonne supprime la
-- majeure partie du besoin de recherche sémantique — c'est l'arbitrage tranché
-- de l'US, et `recherche_fts` est ce qui le rend exécutable.
--
-- [CA2] `poids` exprime une PLAUSIBILITÉ RELATIVE, dans ]0, 1]. Il ORDONNE, il
-- ne se montre jamais : aucun chemin de lecture ne le fait remonter jusqu'au
-- jardinier (app/services/prediagnostic.py ne le verse pas dans ce qu'il rend).
-- Un pourcentage affiché serait lu comme une probabilité mesurée, alors que ce
-- nombre n'est que la transcription d'un ordre déjà écrit en toutes lettres dans
-- les fiches d'US-140 (« évoque en premier lieu », « vient loin derrière »).
--
-- [CA6] `niveau_confiance` reprend le vocabulaire d'US-098 (`verifie` |
-- `indicatif`) plutôt que d'en inventer un second. Une arête `indicatif` est
-- servie avec la réserve de US-140/CA8, mot pour mot la même
-- (`connaissance.RESERVE_INDICATIF`) : deux formulations de la même prudence
-- divergeraient, et celle qui compte finirait par ne plus se voir.
--
-- [CA7] Ce que ces tables N'ONT PAS, et n'auront pas : aucune colonne de
-- produit, de dosage ni de conduite à tenir. Même garantie structurelle que
-- migration_v43 — l'absence de colonne, et non une consigne de rédaction, est ce
-- qui rend impossible de servir une prescription.
--
-- [CA3 d'US-162, réappliqué tel quel] `potager_id` NULL = connaissance
-- partagée ; un potager peut décrire SON symptôme sans polluer les autres, et
-- cet ajout n'est jamais promu au partagé automatiquement.
--
-- Cette migration ne sème AUCUNE ligne. Le contenu arrive par
-- app/services/import_referentiel.py (blocs `symptomes` et
-- `symptomes_bioagresseurs` d'un manifeste), à partir de
-- data/referentiel/symptomes_redaction_interne.json.
--
-- Idempotent : CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.
-- Rollback : migrations/rollback_v45.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ── [CA1] Identité d'un symptôme observable ──────────────────────────────────
CREATE TABLE IF NOT EXISTS symptome (
    id                SERIAL PRIMARY KEY,
    libelle           VARCHAR NOT NULL,
    libelle_normalise VARCHAR NOT NULL,
    organe            VARCHAR NOT NULL,
    synonymes         TEXT NULL,
    -- [CA9] Vecteur maintenu à l'ÉCRITURE, jamais recalculé par requête — même
    -- mécanique et même configuration de dictionnaire que knowledge_chunks
    -- (migration_v42) : `french_sans_accent`, parce qu'un jardinier tape sans
    -- accent sur un clavier mobile.
    recherche_fts     TSVECTOR NULL,
    potager_id        INTEGER NULL REFERENCES potagers(id),
    source_id         INTEGER NOT NULL REFERENCES referentiel_source(id)
);

CREATE INDEX IF NOT EXISTS idx_symptome_libelle ON symptome (libelle_normalise);
CREATE INDEX IF NOT EXISTS idx_symptome_potager ON symptome (potager_id);
CREATE INDEX IF NOT EXISTS idx_symptome_source  ON symptome (source_id);

-- [CA9] L'index GIN est ce qui tient la promesse « déterministe ET immédiat » :
-- sans lui, la recherche plein texte dégénère en balayage complet de la table.
CREATE INDEX IF NOT EXISTS idx_symptome_fts ON symptome USING GIN (recherche_fts);

-- Unicité PARTIELLE, motif de migration_v43 : un seul symptôme PARTAGÉ par
-- libellé, mais un potager reste libre de décrire le sien.
CREATE UNIQUE INDEX IF NOT EXISTS uq_symptome_libelle_partage
    ON symptome (libelle_normalise)
    WHERE potager_id IS NULL;

-- ── [CA2] L'arête pondérée symptôme × bioagresseur ───────────────────────────
CREATE TABLE IF NOT EXISTS symptome_bioagresseur (
    id               SERIAL PRIMARY KEY,
    symptome_id      INTEGER NOT NULL REFERENCES symptome(id),
    bioagresseur_id  INTEGER NOT NULL REFERENCES bioagresseur(id),
    poids            REAL NOT NULL,
    niveau_confiance VARCHAR NOT NULL DEFAULT 'indicatif',
    potager_id       INTEGER NULL REFERENCES potagers(id),
    source_id        INTEGER NOT NULL REFERENCES referentiel_source(id)
);

CREATE INDEX IF NOT EXISTS idx_symptome_bio_symptome ON symptome_bioagresseur (symptome_id);
CREATE INDEX IF NOT EXISTS idx_symptome_bio_bio      ON symptome_bioagresseur (bioagresseur_id);
CREATE INDEX IF NOT EXISTS idx_symptome_bio_potager  ON symptome_bioagresseur (potager_id);
CREATE INDEX IF NOT EXISTS idx_symptome_bio_source   ON symptome_bioagresseur (source_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_symptome_bio_partage
    ON symptome_bioagresseur (symptome_id, bioagresseur_id)
    WHERE potager_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_symptome_bio_local
    ON symptome_bioagresseur (symptome_id, bioagresseur_id, potager_id)
    WHERE potager_id IS NOT NULL;

-- ── [CA3 d'US-162] RLS — second verrou, motif culture_config de migration_v18 ─
ALTER TABLE symptome              ENABLE ROW LEVEL SECURITY;
ALTER TABLE symptome_bioagresseur ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_symptome ON symptome;
CREATE POLICY tenant_isolation_symptome ON symptome
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_symptome_bioagresseur ON symptome_bioagresseur;
CREATE POLICY tenant_isolation_symptome_bioagresseur ON symptome_bioagresseur
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- ⚠️ Conséquence identique à migration_v42 et v43 : une ligne PARTAGÉE
-- (`potager_id IS NULL`) est LISIBLE par tous mais n'est ÉCRIVABLE que par le
-- rôle propriétaire de la base. L'import du manifeste de symptômes doit donc
-- tourner avec ce rôle, comme tools/ingerer_connaissance.py.

COMMENT ON TABLE symptome IS
    'US-165/CA1 — Ce que le jardinier VOIT, décrit avec ses mots. Aucune colonne culture_id : '
    'un symptôme n''appartient à aucune culture, c''est le croisement avec culture_bioagresseur '
    '(US-162) qui décide de la piste — sans quoi le cas de désambiguïsation du CA14 (rouille de '
    'l''ail contre rouille du poireau) serait structurellement intraitable.';

COMMENT ON COLUMN symptome.synonymes IS
    'US-165/CA1 — LE cœur de la table. Les deux registres, celui du jardinier (« poudre blanche », '
    '« cul noir ») ET celui de l''agronome (« oïdium », « nécrose apicale »). C''est cette colonne '
    'qui fait fonctionner la recherche plein texte sans moteur vectoriel, pour quelques minutes de '
    'rédaction par symptôme là où le vectoriel coûte une infrastructure.';

COMMENT ON COLUMN symptome.organe IS
    'US-165/CA1 — feuille | fruit | tige | racine | plant entier | fleur | graine | bulbe. '
    'Vocabulaire fermé mais RÉVISABLE, '
    'validé par app/services/prediagnostic.py — jamais par un CHECK (même arbitrage que '
    'migration_v39, v41 et v43).';

COMMENT ON TABLE symptome_bioagresseur IS
    'US-165/CA2 — Arête PONDÉRÉE. Aucune colonne de produit, de dosage ni de conduite à tenir '
    '(CA7) : l''absence de colonne est la garantie qu''aucune prescription ne peut être servie.';

COMMENT ON COLUMN symptome_bioagresseur.poids IS
    'US-165/CA2 — Plausibilité RELATIVE dans ]0, 1]. Elle ORDONNE et ne s''affiche jamais : '
    'app/services/prediagnostic.py ne la verse pas dans ce qu''il rend. Un pourcentage montré se '
    'lirait comme une probabilité mesurée, alors que ce nombre transcrit un ordre déjà écrit en '
    'toutes lettres dans les fiches d''US-140.';

COMMENT ON COLUMN symptome_bioagresseur.niveau_confiance IS
    'US-165/CA6 — verifie | indicatif, le vocabulaire d''US-098 et non un second. Une arête '
    'indicatif est servie avec la réserve de US-140/CA8, mot pour mot.';

COMMIT;

-- ── Vérifications ────────────────────────────────────────────────────────────
-- Les deux tables existent.
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('symptome', 'symptome_bioagresseur')
ORDER BY table_name;

-- [CA7] Contrôle structurel : aucune colonne de prescription. DOIT valoir 0.
SELECT COUNT(*) AS colonnes_de_prescription
FROM information_schema.columns
WHERE table_name IN ('symptome', 'symptome_bioagresseur')
  AND (column_name ILIKE '%dose%' OR column_name ILIKE '%produit%'
       OR column_name ILIKE '%traitement%' OR column_name ILIKE '%posologie%');

-- [CA1] Contrôle structurel : aucun rattachement direct à une culture. DOIT
-- valoir 0 — le croisement passe par culture_bioagresseur, jamais par le
-- symptôme lui-même.
SELECT COUNT(*) AS colonnes_de_culture
FROM information_schema.columns
WHERE table_name = 'symptome' AND column_name ILIKE '%culture%';

-- [CA9] La configuration de dictionnaire est bien celle de migration_v42 :
-- « recolter » sans accent doit retrouver « récolter ».
SELECT to_tsvector('french_sans_accent', 'récolter recolter') AS un_seul_lexeme_attendu;
