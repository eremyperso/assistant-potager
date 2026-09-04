-- =============================================================================
-- rollback_v42.sql — Annule migration_v42.sql (socle de connaissance, US-098)
-- =============================================================================
-- Supprime `knowledge_chunks`, `knowledge_documents` et les deux colonnes de
-- journalisation ajoutées à `routage_logs`. Aucune table préexistante n'est
-- modifiée autrement : `culture_config` et `potagers`, seulement référencées,
-- ne sont pas touchées.
--
-- Perte : la totalité du corpus INDEXÉ. Ce n'est pas une perte de contenu — le
-- contenu vit dans le dépôt (arbitrage tranché de l'US : « la base est l'index,
-- le dépôt est la source »), il se réingère intégralement avec
-- `python tools/ingerer_connaissance.py`. La seule chose réellement perdue est
-- la connaissance PRIVÉE d'un potager qui ne viendrait pas d'un fichier
-- versionné (US-141, non livrée à ce jour — aucune ligne de ce type n'existe
-- encore) : l'exporter avant d'exécuter ce script le jour où elle existera.
--
-- Perte annexe : les scores et issues de recherche déjà journalisés
-- (`routage_logs.score_savoir` / `issue_savoir`, CA14). Les lignes de
-- `routage_logs` elles-mêmes sont conservées.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces tables : `app/services/connaissance.py`, la branche QUESTION_SAVOIR de
-- `llm/routeur.py::repondre_avec_cascade` et `tools/ingerer_connaissance.py`,
-- sans quoi ces chemins échoueraient en base.
-- =============================================================================

BEGIN;

-- Les policies partent avec les tables (DROP TABLE les supprime), inutile de
-- les retirer une par une.
DROP TABLE IF EXISTS knowledge_chunks;
DROP TABLE IF EXISTS knowledge_documents;

ALTER TABLE routage_logs DROP COLUMN IF EXISTS score_savoir;
ALTER TABLE routage_logs DROP COLUMN IF EXISTS issue_savoir;

-- La configuration de recherche n'est utilisée que par le socle : elle part
-- avec lui. L'extension `unaccent`, en revanche, n'est PAS retirée — elle est
-- susceptible d'être utilisée ailleurs, la retirer casserait ces usages, et une
-- extension installée sans utilisateur ne coûte rien. Pour l'ôter délibérément :
--     DROP EXTENSION unaccent;   -- échouera si un objet en dépend encore
DROP TEXT SEARCH CONFIGURATION IF EXISTS french_sans_accent;

-- Rétablit la borne d'origine de `migration_v36`. Les entrées de cache qui
-- portent une référence plus longue sont retirées AVANT, sinon l'ALTER échoue :
-- elles dérivent toutes de fragments qui disparaissent avec les tables
-- ci-dessus, donc elles n'ont plus d'objet.
DELETE FROM questions_cache WHERE length(fragment_id) > 120;
ALTER TABLE questions_cache ALTER COLUMN fragment_id TYPE VARCHAR(120);

COMMIT;

-- Vérification : ce compteur doit valoir zéro (les deux tables ont disparu).
SELECT COUNT(*) AS tables_restantes
FROM information_schema.tables
WHERE table_name IN ('knowledge_documents', 'knowledge_chunks');

-- Vérification : ce compteur doit valoir zéro (les deux colonnes ont disparu).
SELECT COUNT(*) AS colonnes_restantes
FROM information_schema.columns
WHERE table_name = 'routage_logs' AND column_name IN ('score_savoir', 'issue_savoir');

-- Vérification : ce compteur doit valoir zéro (la configuration a disparu)…
SELECT COUNT(*) AS configurations_restantes
FROM pg_ts_config WHERE cfgname = 'french_sans_accent';

-- …et `french`, configuration système, doit être intacte.
SELECT cfgname FROM pg_ts_config WHERE cfgname = 'french';
