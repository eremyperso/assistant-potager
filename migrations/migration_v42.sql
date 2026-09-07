-- =============================================================================
-- migration_v42.sql — Socle de connaissance interrogeable en plein texte (US-098)
-- =============================================================================
-- Cette migration livre **le contenant, pas le contenu** : deux tables, un
-- index plein texte français, aucune ligne semée. Les trois familles de
-- connaissance (`agronomie`, `doc_app`, `memoire_potager`) sont remplies par
-- US-099, US-140 et US-141, via `tools/ingerer_connaissance.py`.
--
-- [CA1] `knowledge_documents` — une ligne par document versionné dans le dépôt.
-- `potager_id` NULL = savoir global partagé entre tous les potagers ; non NULL =
-- savoir privé d'un potager (US-141). Exactement le motif déjà éprouvé sur
-- `culture_config` (CA3), pas un régime nouveau.
--
-- `reference` (hors énumération du CA1) est l'identité STABLE du document —
-- pour un document ingéré, son chemin relatif dans le dépôt. C'est elle qui
-- rend l'ingestion idempotente (CA10) : sans identité stable, un rejeu créerait
-- un second document au lieu de retrouver le premier. `empreinte` (SHA-256 du
-- fichier source) répond à la question « ce document a-t-il changé ? » sans
-- comparer le texte entier.
--
-- [CA2] `knowledge_chunks` — le fragment est l'unité de recherche.
-- `potager_id` y est DÉNORMALISÉ depuis le document : le filtre d'isolation du
-- CA5 se pose alors directement sur la table interrogée, sans jointure — une
-- jointure oubliée est un chemin de fuite, une colonne absente n'en est pas un.
--
-- [CA2 amendé le 25/08/2026 — docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.3]
-- La culture d'un fragment est une RÉFÉRENCE (`culture_id` → `culture_config`),
-- jamais un libellé texte. Un libellé ici serait exactement l'erreur corrigée
-- par `migration_v12` sur `evenements.parcelle` : une culture renommée depuis
-- le bot orphelinerait silencieusement ses fragments (CA2bis). Nullable — un
-- fragment de la famille `doc_app` ne se rattache à aucune culture.
--
-- [CA2] `recherche_fts` est un TSVECTOR MAINTENU À L'ÉCRITURE par
-- `app/services/connaissance.py`, jamais recalculé à chaque requête (note
-- technique de l'US), et jamais par un trigger ni une colonne GENERATED : le
-- projet tourne aussi sur SQLite en test, et une colonne calculée par le moteur
-- y serait ingérable. `app/services/connaissance.py` est le SEUL point
-- d'écriture de cette table — une insertion faite ailleurs laisserait le
-- vecteur vide, donc le fragment introuvable.
--
-- [CA2] `embedding` est créée, nullable et INUTILISÉE. Arbitrage tranché de
-- l'US : pas de pgvector à ce stade, aucune extension, aucune dépendance
-- nouvelle. Le type est TEXT (le vecteur y sera sérialisé en JSON le jour venu)
-- plutôt qu'un type d'extension absent : créer la colonne coûte zéro
-- aujourd'hui et évite d'ouvrir cette table quand la recherche sémantique sera
-- décidée — décision qui n'interviendra que si la mesure du CA13 montre que les
-- questions mal formulées échouent réellement.
--
-- [CA4] L'index plein texte est un GIN sur `recherche_fts`, et la configuration
-- de recherche est EXPLICITE partout : sur `default`, l'index serait muet sur
-- la lemmatisation — « semé » ne retrouverait pas « semer », « arrosé » pas
-- « arroser ». La configuration de la migration et celle du code applicatif
-- doivent rester identiques — voir `app/services/connaissance.CONFIG_FTS` —,
-- car elle sert à l'ÉCRITURE du vecteur COMME à l'interrogation : deux valeurs
-- différentes ne dégraderaient pas la recherche, elles la rendraient muette.
--
-- Cette configuration n'est PAS `french` telle quelle, et ce n'est pas un
-- raffinement. `french` lemmatise mais **ne replie pas les accents** :
--
--     SELECT to_tsvector('french', 'récolter recolter');
--     →  'recolt':2 'récolt':1        -- deux lexèmes sans rapport
--
-- Constaté sur le corpus agronomique réel le 04/09/2026 : à fiches et
-- jardinier identiques, « quand recolter mes carottes ? » servait une réponse
-- sur les carottes fourchues, là où la même question accentuée trouvait la
-- bonne section. Sur un clavier mobile, taper sans accent est la norme, pas
-- l'exception — et le corpus, lui, est rédigé avec les accents. Le défaut
-- touche donc les mots les plus courants du potager : récolter, éclaircir,
-- flétrir, arroser, semer, oïdium, développé.
--
-- D'où `french_sans_accent`, créée ci-dessous : `french` + le dictionnaire
-- `unaccent`. Effet de bord bienvenu — le repli SQLite des tests passe par
-- `unidecode`, donc il retirait DÉJÀ les accents. Les deux moteurs
-- divergeaient en silence, et toute mesure locale était systématiquement
-- optimiste sur les termes accentués ; ils s'accordent désormais, et une
-- mesure en test redevient prédictive de la production.
--
-- ⚠️ Ne pas attendre de la lemmatisation ce qu'elle ne fait pas : `french_stem`
-- rend « mildiou » et « mildious » comme deux lexèmes DISTINCTS — le stemmer
-- Snowball ne traite pas ce pluriel. Un pluriel irrégulier se déclare dans le
-- « On parle aussi de » de la section, comme n'importe quel autre alias.
--
-- [CA5 / CA9] RLS en défense en profondeur, motif `culture_config` de
-- migration_v18 : le USING accepte le potager courant OU NULL (savoir global
-- partagé), le WITH CHECK n'accepte PAS NULL — depuis le rôle applicatif on ne
-- crée jamais de savoir global. `tools/ingerer_connaissance.py` doit donc être
-- exécuté avec le rôle propriétaire (hors RLS), comme
-- `tools/importer_referentiel.py` l'est déjà pour le référentiel partagé.
-- La protection première reste applicative (`app.services.connaissance`,
-- filtre porté par la fonction de recherche elle-même) : RLS est le second
-- verrou, pas le premier.
--
-- [CA14] `routage_logs` gagne deux colonnes nullables — `score_savoir` et
-- `issue_savoir` — pour que « quelles questions ne trouvent rien ? » soit une
-- requête SQL et non une lecture de fichiers de logs. Nullables : aucune ligne
-- existante à reprendre, et une question qui ne traverse pas l'étage du savoir
-- n'a légitimement ni score ni issue.
--
-- Idempotent : CREATE TABLE/INDEX IF NOT EXISTS, ADD COLUMN IF NOT EXISTS,
-- DROP POLICY IF EXISTS avant chaque CREATE POLICY.
-- Rollback : migrations/rollback_v42.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- [CA4] La configuration de recherche, AVANT les tables : c'est elle que
-- `app/services/connaissance.CONFIG_FTS` nomme, et rien du socle ne fonctionne
-- sans elle.
-- ─────────────────────────────────────────────────────────────────────────────

-- `unaccent` fournit le dictionnaire qui replie « é » sur « e ». Extension
-- CONTRIB standard, présente dans toute distribution PostgreSQL usuelle.
-- ⚠️ `CREATE EXTENSION` demande des droits élevés : si le rôle courant ne les a
-- pas, faire installer l'extension une fois par un administrateur, puis
-- réexécuter — les instructions suivantes n'en ont pas besoin.
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Configuration DÉRIVÉE de `french` : on ne modifie pas `french`, qui est un
-- objet système partagé par tout ce qui tourne sur cette base.
DROP TEXT SEARCH CONFIGURATION IF EXISTS french_sans_accent;
CREATE TEXT SEARCH CONFIGURATION french_sans_accent (COPY = french);

-- L'ordre compte : `unaccent` d'abord (il replie les accents), `french_stem`
-- ensuite (il lemmatise la forme repliée). `hword` / `hword_part` couvrent les
-- mots composés (« porte-greffe »).
ALTER TEXT SEARCH CONFIGURATION french_sans_accent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, french_stem;


-- ── [CA1] Documents ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id               SERIAL PRIMARY KEY,
    potager_id       INTEGER NULL REFERENCES potagers(id),
    reference        VARCHAR NOT NULL UNIQUE,
    titre            VARCHAR NOT NULL,
    famille          VARCHAR NOT NULL,
    source           VARCHAR NOT NULL,
    niveau_confiance VARCHAR NOT NULL,
    empreinte        VARCHAR NOT NULL,
    cree_le          TIMESTAMP NOT NULL DEFAULT now(),
    mis_a_jour_le    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_potager ON knowledge_documents (potager_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_famille ON knowledge_documents (famille);

COMMENT ON TABLE knowledge_documents IS
    'US-098 — Document de connaissance versionné dans le dépôt : titre, famille '
    '(agronomie|doc_app|memoire_potager), source, niveau de confiance '
    '(verifie|indicatif). potager_id NULL = savoir global partagé (CA1, CA3).';

COMMENT ON COLUMN knowledge_documents.reference IS
    'US-098/CA10 — Identité stable du document (chemin relatif du .md dans le dépôt). '
    'Clé de l''idempotence de l''ingestion : un rejeu retrouve le document, il n''en crée pas un second.';

COMMENT ON COLUMN knowledge_documents.empreinte IS
    'US-098/CA10 — SHA-256 du fichier source. Inchangée = document inchangé = aucune réécriture de fragments.';

-- ── [CA2] Fragments ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id             SERIAL PRIMARY KEY,
    document_id    INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    potager_id     INTEGER NULL REFERENCES potagers(id),
    reference      VARCHAR NOT NULL UNIQUE,
    ordre          INTEGER NOT NULL,
    titre_document VARCHAR NOT NULL,
    intitule       VARCHAR NULL,
    contenu        TEXT NOT NULL,
    culture_id     INTEGER NULL REFERENCES culture_config(id),
    type           VARCHAR NULL,
    saison         VARCHAR NULL,
    recherche_fts  TSVECTOR NULL,
    embedding      TEXT NULL
);

-- [CA4] L'index qui rend la recherche possible. GIN plutôt que GiST : la table
-- est lue bien plus souvent qu'écrite (l'écriture n'a lieu qu'à l'ingestion).
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
    ON knowledge_chunks USING GIN (recherche_fts);

-- [CA5] Le filtre d'isolation est posé à CHAQUE recherche : il doit être indexé.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_potager  ON knowledge_chunks (potager_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document ON knowledge_chunks (document_id);
-- [CA6] Restriction par métadonnée quand le routeur en a détecté une.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_culture  ON knowledge_chunks (culture_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_type     ON knowledge_chunks (type);

COMMENT ON TABLE knowledge_chunks IS
    'US-098 — Fragment autonome d''un document de connaissance (CA12 : une idée répondable '
    'par fragment, titre du document conservé). Unité de la recherche plein texte.';

COMMENT ON COLUMN knowledge_chunks.reference IS
    'US-098/CA11 — Identité stable du fragment, reportée dans questions_cache.fragment_id : '
    'c''est par elle qu''une réingestion invalide les réponses figées qui en dérivaient.';

COMMENT ON COLUMN knowledge_chunks.potager_id IS
    'US-098/CA2, CA5 — Dénormalisé depuis knowledge_documents pour que le filtre d''isolation '
    'se pose sans jointure. NULL = savoir global partagé.';

COMMENT ON COLUMN knowledge_chunks.culture_id IS
    'US-098/CA2 amendé, CA2bis — Référence vers culture_config, JAMAIS un libellé : '
    'une culture renommée depuis le bot ne doit pas orpheliner ses fragments (motif migration_v12).';

COMMENT ON COLUMN knowledge_chunks.recherche_fts IS
    'US-098/CA4 — to_tsvector(''french'', ...) maintenu à l''écriture par app/services/connaissance.py, '
    'jamais recalculé par requête. Configuration french explicite : ''default'' serait muet sur accents et lemmes.';

COMMENT ON COLUMN knowledge_chunks.embedding IS
    'US-098/CA2 — Créée, nullable et INUTILISÉE. Pas de pgvector à ce stade (arbitrage tranché) : '
    'la colonne existe pour éviter de rouvrir cette table le jour où la recherche sémantique sera décidée.';

-- ── [CA5 / CA9] RLS — second verrou, motif culture_config de migration_v18 ────
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_knowledge_documents ON knowledge_documents;
CREATE POLICY tenant_isolation_knowledge_documents ON knowledge_documents
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_knowledge_chunks ON knowledge_chunks;
CREATE POLICY tenant_isolation_knowledge_chunks ON knowledge_chunks
    USING      (potager_id = current_setting('app.potager_id')::int OR potager_id IS NULL)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- ── [CA11] `questions_cache.fragment_id` doit pouvoir contenir une référence ──
-- `migration_v36` avait dimensionné cette colonne à VARCHAR(120) alors qu'aucun
-- fragment n'existait encore. `knowledge_chunks.reference`, lui, n'a pas de
-- borne : c'est un chemin de dépôt suivi d'un numéro d'ordre et d'un intitulé
-- de section réduit en ardoise. Sur le premier corpus agronomique réel, 19 des
-- 96 fragments dépassaient 120 caractères — par exemple :
--
--   .../chou-recolte-conservation.md#01-couper-la-pomme-sans-salir-les-feuilles-interieures
--
-- Toute réponse dérivée d'un de ces fragments échouait à la mémorisation sur un
-- DataError PostgreSQL (constaté le 04/09/2026). L'échec était rattrapé et
-- journalisé, donc invisible du jardinier — mais la question repayait un appel
-- modèle complet à CHAQUE fois qu'elle était reposée, indéfiniment.
--
-- Sans borne plutôt qu'avec une borne plus haute : toute valeur choisie ici
-- serait arbitraire, et la longueur d'une référence dépend de l'arborescence du
-- dépôt, que cette migration ne gouverne pas. Sous PostgreSQL, un VARCHAR sans
-- longueur ne coûte rien de plus qu'un VARCHAR(n).
ALTER TABLE questions_cache ALTER COLUMN fragment_id TYPE VARCHAR;

-- ── [CA14] Journalisation de la recherche dans routage_logs (US-097) ─────────
ALTER TABLE routage_logs ADD COLUMN IF NOT EXISTS score_savoir DOUBLE PRECISION NULL;
ALTER TABLE routage_logs ADD COLUMN IF NOT EXISTS issue_savoir VARCHAR(16) NULL;

COMMENT ON COLUMN routage_logs.score_savoir IS
    'US-098/CA14 — Score de confiance global de la recherche de savoir. NULL = la question '
    'n''a pas traversé l''étage du savoir.';

COMMENT ON COLUMN routage_logs.issue_savoir IS
    'US-098/CA14 — Issue de la recherche : servi (réponse directe, zéro jeton) | transmis '
    '(contexte descendu à l''étage de raisonnement) | vide (aucun passage trouvé). '
    'Les lignes ''vide'' définissent le contenu à écrire ensuite.';

COMMIT;

-- =============================================================================
-- Vérifications post-migration
-- =============================================================================
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'knowledge_documents'
ORDER BY ordinal_position;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'knowledge_chunks'
ORDER BY ordinal_position;

-- [CA4] L'index GIN doit exister : sans lui, la recherche fonctionne mais
-- dégénère en balayage complet dès que le corpus grossit.
SELECT indexname FROM pg_indexes
WHERE tablename = 'knowledge_chunks' AND indexname = 'idx_knowledge_chunks_fts';

-- [CA4] La configuration de recherche doit exister. Cette requête doit
-- retourner une ligne ; c'est elle que le code nomme, à l'écriture du vecteur
-- comme à l'interrogation — sans elle, le socle échoue en base.
SELECT cfgname FROM pg_ts_config WHERE cfgname = 'french_sans_accent';

-- [CA4] LE contrôle du repli des accents. Attendu : 'recolt':1,2 — UN SEUL
-- lexème à deux positions. S'il en rend deux ('recolt':2 'récolt':1), le
-- mapping `unaccent` n'a pas été appliqué, et un jardinier qui tape sans accent
-- manquera tous les termes accentués du corpus.
SELECT to_tsvector('french_sans_accent', 'récolter recolter') AS doit_etre_un_seul_lexeme;

-- [CA4] Et la lemmatisation française doit rester intacte.
-- Attendu : 'arros':3,4 'sem':1,2
SELECT to_tsvector('french_sans_accent', 'semé semer arrosé arroser') AS lemmatisation_intacte;

-- [CA4] Contrôle croisé : une question sans accent doit rencontrer un vecteur
-- écrit avec accents. Attendu : true.
SELECT to_tsvector('french_sans_accent', 'Savoir si une racine est assez développée')
       @@ plainto_tsquery('french_sans_accent', 'racine developpee') AS accord_sans_accent;

-- [CA11] La colonne qui reçoit une référence de fragment ne doit plus être
-- bornée. Attendu : character_maximum_length à NULL.
SELECT character_maximum_length AS doit_etre_null
FROM information_schema.columns
WHERE table_name = 'questions_cache' AND column_name = 'fragment_id';

-- [CA5 / CA9] Les deux tables doivent être sous RLS.
SELECT relname, relrowsecurity FROM pg_class
WHERE relname IN ('knowledge_documents', 'knowledge_chunks');

-- [CA2] Aucun fragment ne doit jamais porter un potager_id différent de celui
-- de son document : ce compteur doit valoir zéro à tout instant.
SELECT COUNT(*) AS fragments_desynchronises
FROM knowledge_chunks c
JOIN knowledge_documents d ON d.id = c.document_id
WHERE c.potager_id IS DISTINCT FROM d.potager_id;
