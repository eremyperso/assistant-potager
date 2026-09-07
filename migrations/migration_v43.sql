-- =============================================================================
-- migration_v43.sql — Bioagresseurs et relation culture × bioagresseur (US-162)
-- =============================================================================
-- Crée les deux tables qui manquaient au référentiel : une IDENTITÉ pour chaque
-- bioagresseur, et une ARÊTE entre lui et les cultures qu'il attaque.
--
-- Aujourd'hui « mildiou » est une chaîne dans un commentaire d'événement.
-- L'application ne sait donc pas que le même mildiou touche les pommes de terre
-- de la parcelle d'à côté, ni qu'il est favorisé par la pluviométrie qu'elle
-- affiche déjà sur son propre tableau de bord. C'est ce chaînon que cette
-- migration pose.
--
-- [CA1] `bioagresseur.code_eppo` est la SEULE clé de rapprochement fiable entre
-- sources (docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md §7) — les
-- libellés d'usage E-Phy, eux, sont du texte structuré culture × traitement ×
-- cible. Nullable : un bioagresseur saisi au bot n'en porte aucun et ne doit pas
-- être refusé pour autant.
--
-- [CA2] `culture_bioagresseur` est une TABLE DE LIAISON, jamais un texte : c'est
-- elle qui rend « qu'est-ce qui attaque mes poireaux » résoluble à zéro jeton
-- (§5.2, étage 1). Écrite dans une fiche, la même information ne serait ni
-- joignable, ni triable, ni comptable. `frequence` porte l'ordre de restitution,
-- `periode_risque` reste NULLABLE — une période inconnue se lit « non
-- renseignée », jamais « toute l'année ».
--
-- Ni `categorie` ni `frequence` ne portent de CHECK de vocabulaire : même
-- arbitrage que migration_v39 (`culture_config.exposition`) et migration_v41
-- (`association_culture.nature`) — un vocabulaire fermé mais RÉVISABLE en
-- produit, validé par app/services/bioagresseurs.py, seul point d'écriture.
--
-- [CA3] `potager_id` NULL = connaissance partagée — le pattern d'isolation du
-- projet (culture_config, knowledge_documents), réappliqué tel quel. Un potager
-- ajoute SON bioagresseur local sans polluer les 499 autres, et cet ajout n'est
-- jamais promu au partagé automatiquement : c'est une décision humaine, pas un
-- effet de bord de la saisie. D'où les index d'unicité PARTIELS ci-dessous —
-- un UNIQUE simple sur `code_eppo` ferait échouer la saisie locale du deuxième
-- potager qui déclare « mildiou » chez lui.
--
-- [CA4] `source_id` NOT NULL des deux côtés : aucune identité ni aucune arête
-- anonyme, y compris saisie au bot. L'attribution est une obligation par
-- enregistrement, pas une ligne de README.
--
-- [CA5] Les index d'unicité partiels sont ce qui rend l'idempotence de l'import
-- vérifiable EN BASE et pas seulement dans le service : les fichiers E-Phy sont
-- mis à jour chaque semaine, rejouer doit rester banal.
--
-- [CA7] Sème la source `eppo` au registre. Ses conditions d'utilisation ont été
-- LUES et consignées — data/referentiel/eppo/SOURCE.md — comme le CA7 en fait un
-- préalable bloquant. La « EPPO Codes Open Data Licence » (EPPO, Paris,
-- 17/11/2014) accorde un droit mondial, perpétuel, gratuit et non exclusif de
-- reproduire, publier et transmettre les codes, d'en dériver de l'information et
-- de les exploiter commercialement en les incluant dans son propre produit. La
-- reprise en base n'est donc PAS interdite, et le repli « codes saisis à la main
-- sur les dix cultures » prévu par le CA7 n'a pas lieu d'être. Deux obligations :
-- citer EPPO ET la date du dernier téléchargement (portée par
-- `date_dernier_import`, jamais figée dans l'attribution), sans reproduire le
-- logo EPPO.
--
-- [CA10, CA11] Ce que ces tables N'ONT PAS, et n'auront pas : aucune colonne de
-- produit, de dosage ni de conduite à tenir — l'absence de colonne est la
-- garantie structurelle qu'aucune prescription ne peut être stockée, donc
-- restituée. Aucune colonne de description narrative non plus : symptômes et
-- biologie relèvent d'US-140, ingérés par US-098, et se RATTACHENT à ces
-- identités au lieu de les dupliquer.
--
-- Cette migration ne sème AUCUNE ligne `bioagresseur` ni `culture_bioagresseur`.
-- Le contenu arrive par app/services/import_referentiel.py (blocs
-- `bioagresseurs` et `cultures_bioagresseurs` d'un manifeste) ou par la saisie
-- au bot (`/bioagresseur`).
--
-- Idempotent : CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- ON CONFLICT DO NOTHING.
-- Rollback : migrations/rollback_v43.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ── [CA1, CA3, CA4] Identité d'un bioagresseur ───────────────────────────────
CREATE TABLE IF NOT EXISTS bioagresseur (
    id               SERIAL PRIMARY KEY,
    code_eppo        VARCHAR NULL,
    nom_commun_fr    VARCHAR NOT NULL,
    nom_normalise    VARCHAR NOT NULL,
    nom_scientifique VARCHAR NULL,
    categorie        VARCHAR NOT NULL,
    potager_id       INTEGER NULL REFERENCES potagers(id),
    source_id        INTEGER NOT NULL REFERENCES referentiel_source(id)
);

CREATE INDEX IF NOT EXISTS idx_bioagresseur_code_eppo ON bioagresseur (code_eppo);
CREATE INDEX IF NOT EXISTS idx_bioagresseur_nom       ON bioagresseur (nom_normalise);
CREATE INDEX IF NOT EXISTS idx_bioagresseur_potager   ON bioagresseur (potager_id);
CREATE INDEX IF NOT EXISTS idx_bioagresseur_source    ON bioagresseur (source_id);

-- [CA1, CA3] Unicité PARTIELLE : une seule identité PARTAGÉE par code EPPO et
-- par nom, mais un potager reste libre de déclarer la sienne.
CREATE UNIQUE INDEX IF NOT EXISTS uq_bioagresseur_code_eppo_partage
    ON bioagresseur (code_eppo)
    WHERE code_eppo IS NOT NULL AND potager_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_bioagresseur_nom_partage
    ON bioagresseur (nom_normalise)
    WHERE potager_id IS NULL;

-- ── [CA2] L'arête culture × bioagresseur ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS culture_bioagresseur (
    id              SERIAL PRIMARY KEY,
    culture_id      INTEGER NOT NULL REFERENCES culture_config(id),
    bioagresseur_id INTEGER NOT NULL REFERENCES bioagresseur(id),
    frequence       VARCHAR NOT NULL,
    periode_risque  VARCHAR NULL,
    potager_id      INTEGER NULL REFERENCES potagers(id),
    source_id       INTEGER NOT NULL REFERENCES referentiel_source(id)
);

CREATE INDEX IF NOT EXISTS idx_culture_bioagresseur_culture ON culture_bioagresseur (culture_id);
CREATE INDEX IF NOT EXISTS idx_culture_bioagresseur_bio     ON culture_bioagresseur (bioagresseur_id);
CREATE INDEX IF NOT EXISTS idx_culture_bioagresseur_potager ON culture_bioagresseur (potager_id);
CREATE INDEX IF NOT EXISTS idx_culture_bioagresseur_source  ON culture_bioagresseur (source_id);

-- [CA5] Idempotence de l'import garantie en base, pas seulement dans le service.
CREATE UNIQUE INDEX IF NOT EXISTS uq_culture_bioagresseur_partage
    ON culture_bioagresseur (culture_id, bioagresseur_id)
    WHERE potager_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_culture_bioagresseur_local
    ON culture_bioagresseur (culture_id, bioagresseur_id, potager_id)
    WHERE potager_id IS NOT NULL;

-- ── [CA7] La source EPPO entre au registre, conditions lues et consignées ────
INSERT INTO referentiel_source (code, libelle, licence, attribution, url, partageable, importee) VALUES
    ('eppo', 'EPPO Global Database — codes EPPO', 'EPPO Codes Open Data Licence',
     'Contains EPPO Codes (www.eppo.int) — EPPO Codes Open Data Licence',
     'https://data.eppo.int/', TRUE, TRUE)
ON CONFLICT (code) DO NOTHING;

-- ── [CA3] RLS — second verrou, motif culture_config de migration_v18 ─────────
ALTER TABLE bioagresseur         ENABLE ROW LEVEL SECURITY;
ALTER TABLE culture_bioagresseur ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_bioagresseur ON bioagresseur;
CREATE POLICY tenant_isolation_bioagresseur ON bioagresseur
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_culture_bioagresseur ON culture_bioagresseur;
CREATE POLICY tenant_isolation_culture_bioagresseur ON culture_bioagresseur
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- ⚠️ Conséquence directe, identique à migration_v42 : une ligne PARTAGÉE
-- (`potager_id IS NULL`) est LISIBLE par tous mais n'est ÉCRIVABLE que par le
-- rôle propriétaire de la base — `WITH CHECK` l'interdit à `app_user`. L'import
-- d'un manifeste (tools/importer_referentiel.py) doit donc tourner avec le rôle
-- propriétaire, exactement comme tools/ingerer_connaissance.py.

COMMENT ON TABLE bioagresseur IS
    'US-162/CA1 — Identité propre d''un bioagresseur : nom commun FR, nom scientifique, '
    'catégorie et code EPPO. AUCUNE colonne de produit, dosage ou conduite à tenir (CA10), '
    'AUCUNE description narrative (CA11 — elle relève d''US-140/US-098 et se rattache ici).';

COMMENT ON COLUMN bioagresseur.code_eppo IS
    'US-162/CA1 — Seule clé de rapprochement fiable entre sources. Unicité PARTIELLE '
    '(uq_bioagresseur_code_eppo_partage) : sur les lignes partagées seulement, sinon la '
    'première saisie locale bloquerait tous les autres potagers (CA3).';

COMMENT ON COLUMN bioagresseur.categorie IS
    'US-162/CA1 — champignon | insecte | mollusque | nematode | bacterie | virus | abiotique | '
    'carence. Vocabulaire fermé mais RÉVISABLE, validé par app/services/bioagresseurs.py — jamais '
    'par un CHECK (même arbitrage que migration_v39 et migration_v41) : c''est ce qui a permis '
    'd''ajouter mollusque et nematode sans migration, quand la relecture d''un référentiel réel a '
    'montré que les limaces tombaient en insecte faute de case.';

COMMENT ON COLUMN bioagresseur.potager_id IS
    'US-162/CA3 — NULL = connaissance partagée. Un ajout local n''est JAMAIS promu au partagé '
    'automatiquement : la promotion est une décision humaine.';

COMMENT ON TABLE culture_bioagresseur IS
    'US-162/CA2 — Table de liaison, jamais un texte : c''est elle qui rend « qu''est-ce qui '
    'attaque mes poireaux » résoluble à zéro jeton (conception §5.2, étage 1). L''absence de '
    'ligne pour une culture n''est PAS une absence de risque (CA12) — cette honnêteté est '
    'portée par app/services/bioagresseurs.lire_bioagresseurs, aucune colonne ne peut la porter.';

COMMENT ON COLUMN culture_bioagresseur.frequence IS
    'US-162/CA2 — courant | occasionnel | rare. Porte l''ordre de restitution (ORDRE_FREQUENCE), '
    'qui est un ordre MÉTIER et non un score.';

COMMENT ON COLUMN culture_bioagresseur.periode_risque IS
    'US-162/CA2 — Libellé court (« juin-septembre »). NULL = période non renseignée, jamais '
    '« toute l''année ».';

COMMIT;

-- ── Vérifications ────────────────────────────────────────────────────────────
-- Les deux tables existent.
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('bioagresseur', 'culture_bioagresseur')
ORDER BY table_name;

-- [CA7] La source EPPO est au registre avec sa licence exacte.
SELECT code, licence, attribution FROM referentiel_source WHERE code = 'eppo';

-- [CA10] Contrôle structurel : aucune colonne de prescription n'existe sur ces
-- tables. Ce compteur DOIT valoir 0 — c'est la garantie que rien ne pourra être
-- restitué, faute d'endroit où le stocker.
SELECT COUNT(*) AS colonnes_de_prescription
FROM information_schema.columns
WHERE table_name IN ('bioagresseur', 'culture_bioagresseur')
  AND (column_name ILIKE '%dose%' OR column_name ILIKE '%produit%'
       OR column_name ILIKE '%traitement%' OR column_name ILIKE '%posologie%');
