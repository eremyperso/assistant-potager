-- =============================================================================
-- migration_v34.sql — Origine du parsing d'un évènement (US-094 / CA10)
-- =============================================================================
-- Ajoute `evenements.origine_parsing` : 'deterministe' quand la saisie a été
-- reconnue par la grammaire de `llm/parseur_deterministe.py` (zéro jeton,
-- zéro ligne dans `conso_tokens` — CA11), 'llm' quand elle est passée par le
-- modèle, NULL pour tout l'historique antérieur à cette US.
--
-- À quoi elle sert, et à quoi elle ne sert PAS :
--   * elle MESURE la couverture réelle du parseur en production, là où le
--     corpus versionné dans les tests ne mesure qu'un instantané. C'est elle
--     qui dira quelles formes tombent encore en repli, donc quelle règle
--     mérite d'être ajoutée à la grammaire (arbitrage « pas d'apprentissage
--     automatique » : l'enrichissement reste une tâche de maintenance
--     humaine, mais outillée) ;
--   * elle n'est lue par AUCUNE condition métier, aucun gabarit de réponse et
--     aucun message utilisateur. Un évènement se comporte exactement pareil
--     quelle que soit sa valeur — c'est de l'instrumentation, pas de l'état.
--
-- NULL n'est pas 'llm' : avant cette US, l'information n'existait pas, et
-- c'est la seule chose vraie qu'on puisse dire des lignes antérieures. Aucun
-- backfill, délibérément.
--
-- Purement additive : colonne nullable, sans défaut, sans contrainte — aucune
-- écriture existante n'a à changer pour rester valide.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS.
-- Rollback : migrations/rollback_v34.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS origine_parsing VARCHAR(16);

COMMENT ON COLUMN evenements.origine_parsing IS
    'US-094/CA10 — deterministe | llm | NULL (antérieur à l''US). '
    'Instrumentation seule : jamais lue par une condition métier.';

-- Requête cible : « quelle part des saisies est traitée sans appel modèle,
-- par période ». L'index partiel évite de peser sur les lignes historiques,
-- toutes à NULL.
CREATE INDEX IF NOT EXISTS idx_evenements_origine_parsing
    ON evenements (origine_parsing, date)
    WHERE origine_parsing IS NOT NULL;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'evenements' AND column_name = 'origine_parsing';

SELECT COALESCE(origine_parsing, '(historique)') AS origine, COUNT(*)
FROM evenements
GROUP BY 1
ORDER BY 2 DESC;
