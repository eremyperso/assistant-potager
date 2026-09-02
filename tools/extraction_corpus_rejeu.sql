-- =============================================================================
-- extraction_corpus_rejeu.sql — Extraction du corpus de rejeu « action »
-- depuis la PRODUCTION, en vue de l'Action 0 (deux rejeux de corpus, cf.
-- docs/decisions-prerequis-vague2-piste-a.md §6).
-- =============================================================================
--
-- LECTURE SEULE — aucun ALTER, aucun INSERT, aucun UPDATE, aucun DELETE.
-- Ce n'est PAS une migration : ne jamais renommer en migration_vX,
-- ne jamais déplacer dans migrations/.
--
-- Le rejeu lui-même NE tourne PAS sur la prod : le routeur (US-093/096/097)
-- n'y est pas déployé. Ce fichier ne fait que SORTIR les données ; la mesure
-- se fait en dev, sur la branche epic-6, contre une base rechargée.
--
--
-- ATTENTION : la meta-commande de copie psql ne fait PAS d'interpolation de
-- variable (le reste de la ligne est pris litteralement). Le potager y est
-- donc ecrit EN DUR (= 1, potager de production). Seule l'etape 1, du SQL
-- pur, utilise `-v potager=`.
--
-- Usage (prod, lecture seule) :
--   psql -w "$DATABASE_URL_PROD" -v potager=1 -f tools/extraction_corpus_rejeu.sql
--
-- Le filtre multi-tenant est EXPLICITE : la RLS n'est pas activée sur
-- `evenements` (cf. tools/analyse_corpus_echecs.sql). Sans -v potager=<id>,
-- les locataires se mélangent en silence.
-- =============================================================================

\set ON_ERROR_STOP on

\echo '── 1/5 · Contrôle de volume (doit afficher 225 saisies réelles) ─────────'

WITH perimetre AS (
    SELECT * FROM evenements WHERE potager_id = :potager
)
SELECT 'total lignes'                    AS mesure, count(*) FROM perimetre
UNION ALL SELECT 'bulletins [AUTO-METEO]', count(*) FROM perimetre
    WHERE texte_original = '[AUTO-METEO]'
UNION ALL SELECT 'texte vide ou NULL',     count(*) FROM perimetre
    WHERE texte_original IS NULL OR trim(texte_original) = ''
UNION ALL SELECT 'SAISIES REJOUABLES',     count(*) FROM perimetre
    WHERE texte_original IS DISTINCT FROM '[AUTO-METEO]'
      AND texte_original IS NOT NULL AND trim(texte_original) <> ''
UNION ALL SELECT 'dont porteuses de [CORR]', count(*) FROM perimetre
    WHERE texte_original LIKE '%[CORR%';

\echo '── 2/5 · Corpus de rejeu « action » → rejeu_action.csv ──────────────────'

-- `question` = le message TEL QU'IL A ÉTÉ DICTÉ : les traces [CORR ...]
-- ajoutées après coup ne faisaient pas partie de l'entrée du routeur, les
-- rejouer fausserait la classification.
\copy (SELECT e.id, left(e.texte_original, coalesce(nullif(position('[CORR' in e.texte_original), 0) - 1, length(e.texte_original))) AS question, 'ACTION' AS nature_attendue, e.type_action, e.culture, e.unite, e.parcelle_id, e.date FROM evenements e WHERE e.potager_id = 1 AND e.texte_original IS DISTINCT FROM '[AUTO-METEO]' AND e.texte_original IS NOT NULL AND trim(e.texte_original) <> '' ORDER BY e.date, e.id) TO 'rejeu_action.csv' CSV HEADER

\echo '── 3/5 · Catalogue du potager → catalogue_parcelles.csv ─────────────────'

-- Indispensable : la règle catalogue d'US-093 appelle
-- `reponses_chiffrees.reconnait_famille`, qui résout les noms de parcelles en
-- base. Une base dev sans les parcelles de prod ne route PAS pareil.
\copy (SELECT id, nom, nom_normalise, exposition, superficie_m2, ordre, actif, est_pepiniere, type_sol, potager_id FROM parcelles WHERE potager_id = 1 ORDER BY id) TO 'catalogue_parcelles.csv' CSV HEADER

\echo '── 4/5 · Cultures connues du potager → catalogue_cultures.csv ───────────'

-- Même raison : `cultures_connues(db, potager_id)` lit les cultures distinctes
-- des évènements. Elles arrivent avec le dump des évènements ci-dessous, ce
-- fichier ne sert qu'au contrôle de fidélité après rechargement en dev.
\copy (SELECT DISTINCT lower(culture) AS culture, count(*) OVER (PARTITION BY lower(culture)) AS occurrences FROM evenements WHERE potager_id = 1 AND culture IS NOT NULL ORDER BY 1) TO 'catalogue_cultures.csv' CSV HEADER

\echo '── 5/5 · Dump rechargeable des évènements → evenements_potager1.csv ─────'

-- Lignes complètes, ordre de colonnes natif : rechargeables en dev par
--   \copy evenements FROM 'evenements_potager1.csv' CSV HEADER
-- ⚠️ Suppose un schéma `evenements` identique entre prod et la branche dev.
-- La branche epic-6 n'a ajouté aucune colonne à `evenements` à ce jour ;
-- après l'insertion 2 (`date_source`), ce dump devra être rechargé en
-- nommant les colonnes explicitement.
\copy (SELECT * FROM evenements WHERE potager_id = 1 ORDER BY id) TO 'evenements_potager1.csv' CSV HEADER

\echo '── Terminé. Quatre CSV écrits dans le répertoire courant. ───────────────'
