-- =============================================================================
-- migration_v36.sql — Cache de questions récurrentes (US-095 / CA1, CA2, CA4, CA10)
-- =============================================================================
-- Crée la table `questions_cache`, étage 0bis de la cascade de réponses
-- (`llm/routeur.py::repondre_avec_cascade`), alimentée et lue par
-- `app/services/cache_questions.py`.
--
-- Deux natures de réponse mémorisée, qu'il ne faut jamais confondre :
--
--   * type_reponse = 'template_sql' — SEULS le motif et l'aiguillage sont
--     mémorisés (famille du catalogue, culture, parcelle). Les VALEURS sont
--     recalculées à chaque service par l'étage des données (US-096). La
--     réponse est donc juste par construction, personnalisée à chaque appel,
--     et coûte zéro jeton. `reponse_figee` reste NULL.
--
--   * type_reponse = 'figee' — texte mémorisé tel quel, réservé au savoir
--     général qui ne dépend d'AUCUN potager (« à quelle profondeur semer les
--     carottes ? »). `potager_id` est alors NULL : l'entrée est partageable
--     entre tous les potagers, ce qui est aussi la raison pour laquelle elle
--     ne doit jamais contenir de donnée issue d'un potager (CA8, contrôle à
--     l'écriture côté service). `template` reste NULL.
--
-- DEUX NATURES DE RÉPONSE, DONC DEUX ESPACES DE CLÉS (CA2) :
--
--   * `cle_aiguillage` ('famille|culture|parcelle') est la clé des entrées
--     `template_sql`. Elle est BORNÉE par construction — quelques centaines de
--     valeurs pour un potager — là où l'espace des formulations ne l'est pas.
--     « quel est ma production de concombre », « ma production de concombre »
--     et « production de concombre » sont trois phrases pour une seule
--     question : une seule ligne, et le cache sert enfin.
--   * `motif_normalise` est la clé des entrées `figee` : pour du savoir
--     général il n'existe aucun aiguillage, la phrase est tout ce qu'on a. Sur
--     une entrée `template_sql` la colonne reste renseignée, mais pour l'AUDIT
--     seulement — elle dit quelle formulation a créé l'entrée.
--
-- Colonnes de justesse (CA4/CA5) — c'est le cœur de l'US :
--   * culture  : culture concernée par l'entrée, NULL si l'entrée porte sur
--                l'ensemble du potager (stock global, rendement global) ;
--   * natures  : natures de donnée dont l'entrée dérive, encadrées de '|'
--                pour un test d'appartenance portable
--                (ex. '|stock|recolte|journal|'), voir
--                utils/dependances_donnee.py. VIDE pour une réponse figée :
--                elle ne dérive d'aucun potager, aucun évènement ne peut la
--                contredire.
-- Toute écriture d'évènement supprime les entrées du potager dont la culture
-- et les natures recoupent celles de l'évènement. L'invalidation est une
-- SUPPRESSION, pas un marquage : une entrée périmée qui subsisterait est
-- exactement le défaut que l'US existe pour empêcher.
--
-- `fragment_id` (CA10) : identifiant du fragment de connaissance dont une
-- réponse figée est issue. Reste NULL tant que le socle de connaissance
-- (US-098) n'existe pas — aucune réponse figée d'origine RAG n'est produite
-- aujourd'hui. La colonne est créée maintenant pour que la correction d'une
-- fiche agronomique puisse invalider ses réponses dérivées sans migration
-- supplémentaire le jour où elle existera.
--
-- Pas de contrainte UNIQUE sur les clés : `potager_id` est NULL pour les
-- entrées de savoir général, et une contrainte UNIQUE portant sur une colonne
-- nullable ne contraint rien en PostgreSQL — deux lignes NULL sont toujours
-- distinctes. L'unicité est donc tenue côté service (lecture-puis-écriture
-- dans la même transaction), et les index ci-dessous servent la recherche,
-- pas la contrainte.
--
-- Purement additive : aucune table existante n'est modifiée, aucun
-- comportement applicatif ne dépend de la présence de données ici — un cache
-- vide se comporte exactement comme avant cette US.
--
-- Idempotent, et REJOUABLE sur une base où une version antérieure de ce
-- fichier a déjà créé la table : `CREATE TABLE IF NOT EXISTS` ne l'aurait pas
-- mise à jour, c'est l'`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` ci-dessous
-- qui s'en charge.
-- Rollback : migrations/rollback_v36.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS questions_cache (
    id              SERIAL PRIMARY KEY,
    -- NULL = savoir général, partageable entre tous les potagers (CA1).
    potager_id      INTEGER      NULL     REFERENCES potagers(id),
    -- [CA2] Question normalisée par la MÊME fonction que le routeur
    -- (llm.routeur.normaliser_question) — jamais une variante. Clé des entrées
    -- figées ; trace d'audit sur les entrées paramétrées.
    motif_normalise VARCHAR(500) NOT NULL,
    -- [CA2] Clé des entrées paramétrées : 'famille|culture|parcelle'.
    cle_aiguillage  VARCHAR(300) NULL,
    -- template_sql | figee
    type_reponse    VARCHAR(16)  NOT NULL,
    -- [CA3] Aiguillage sérialisé (JSON) d'une réponse paramétrée : famille du
    -- catalogue + culture + parcelle. Jamais de valeur chiffrée.
    template        TEXT         NULL,
    -- Texte mémorisé tel quel d'une réponse figée.
    reponse_figee   TEXT         NULL,
    -- sql | rag | llm — étage qui a produit la réponse, pour audit (CA1).
    source_etage    VARCHAR(8)   NOT NULL,
    -- [CA4] Dépendances de l'entrée.
    culture         VARCHAR(120) NULL,
    natures         VARCHAR(200) NOT NULL DEFAULT '',
    -- [CA10] Fragment de connaissance dont dérive une réponse figée.
    fragment_id     VARCHAR(120) NULL,
    -- [CA11] Écartée à la lecture au-delà de cette date, nettoyée au fil de
    -- l'eau à l'écriture suivante — aucun job planifié n'est ajouté.
    valide_jusqu_au TIMESTAMP    NULL,
    cree_le         TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Mise à niveau d'une table créée par la première version de ce fichier, qui
-- ne connaissait pas `cle_aiguillage` et clefait les réponses paramétrées sur
-- la formulation. Sans effet sur une table fraîchement créée ci-dessus.
ALTER TABLE questions_cache
    ADD COLUMN IF NOT EXISTS cle_aiguillage VARCHAR(300);

ALTER TABLE questions_cache
    ALTER COLUMN natures SET DEFAULT '';

-- Les lignes éventuellement présentes sont clefées sur l'ancienne convention
-- (une ligne par formulation) : elles ne seraient plus jamais retrouvées, et
-- occuperaient la borne par potager sans jamais servir. Les effacer est SANS
-- PERTE — c'est un cache : les entrées paramétrées ne mémorisent qu'un
-- aiguillage que l'étage des données recalcule de toute façon, et les entrées
-- figées seront reproduites au prochain passage. Même argument que
-- rollback_v36.sql, redit ici pour que ce DELETE ne surprenne pas.
DELETE FROM questions_cache;

-- Requête de service d'une réponse paramétrée : « ce potager a-t-il déjà
-- répondu à cette question, quelle qu'en soit la formulation ? »
CREATE INDEX IF NOT EXISTS idx_questions_cache_aiguillage
    ON questions_cache (cle_aiguillage, potager_id);

-- Requête de service d'une réponse figée : la phrase est la seule clé.
CREATE INDEX IF NOT EXISTS idx_questions_cache_motif
    ON questions_cache (motif_normalise, potager_id);

-- Requête d'invalidation (CA5) : toutes les entrées d'un potager, filtrées
-- ensuite sur la culture et les natures.
CREATE INDEX IF NOT EXISTS idx_questions_cache_potager
    ON questions_cache (potager_id);

-- Requête d'invalidation par fragment de connaissance (CA10). Index partiel :
-- la colonne reste NULL sur toutes les lignes tant qu'US-098 n'existe pas.
CREATE INDEX IF NOT EXISTS idx_questions_cache_fragment
    ON questions_cache (fragment_id)
    WHERE fragment_id IS NOT NULL;

COMMENT ON TABLE questions_cache IS
    'US-095 — étage 0bis : réponses mémorisées. template_sql = motif + '
    'aiguillage seuls (valeurs recalculées à chaque service, jamais périmées), '
    'clefées sur cle_aiguillage ; figee = savoir général, potager_id NULL, '
    'sans aucune donnée de potager, clefée sur motif_normalise.';

COMMENT ON COLUMN questions_cache.cle_aiguillage IS
    'US-095/CA2 — "famille|culture|parcelle" : identité d''une question '
    'débarrassée de sa formulation. Borne l''espace des clés (quelques '
    'centaines par potager) là où les formulations sont sans limite. '
    'NULL sur une entrée figée, qui n''a pas d''aiguillage.';

COMMENT ON COLUMN questions_cache.natures IS
    'US-095/CA4 — natures de donnée dont l''entrée dérive, encadrées de "|" '
    '(stock|recolte|semis|plan|pepiniere|journal). Support de l''invalidation '
    'événementielle : toute écriture d''évènement supprime les entrées dont '
    'les natures recoupent celles du geste enregistré. VIDE sur une entrée '
    'figée : aucun évènement ne peut contredire du savoir général.';

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'questions_cache'
ORDER BY ordinal_position;

SELECT COALESCE(type_reponse, '(vide)') AS type_reponse, COUNT(*)
FROM questions_cache
GROUP BY 1;
