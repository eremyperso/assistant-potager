-- =============================================================================
-- analyse_date_source.sql
-- Croisement date_source (US-169) × origine_parsing (US-094) × traces [CORR]
-- de production, pour mesurer quel CHEMIN se trompe sur les dates, pas
-- seulement combien de fois (CA11, CA12).
--
-- ⚠️ LECTURE SEULE — aucun ALTER, aucun DELETE, aucun UPDATE.
--    Ce n'est PAS une migration : ne jamais renommer en migration_vX,
--    ne jamais déplacer dans migrations/.
--
-- Usage :
--   psql -w "$DATABASE_URL" -v potager=1 -f tools/analyse_date_source.sql
--   psql -w "$DATABASE_URL" -v potager=1 -f tools/analyse_date_source.sql --csv -o date_source.csv
--
-- ⚠️ Le filtre multi-tenant est EXPLICITE et obligatoire (même garde-fou que
--    tools/analyse_corpus_echecs.sql : la RLS n'est PAS activée sur
--    `evenements`). Sans -v potager=<id>, les agrégats mélangent les
--    locataires en silence. Pour un balayage volontairement global :
--    -v potager=-1
--
-- Ce que cette requête donne, et ce qu'elle ne donne pas (voir US-169) :
--   * un DÉNOMINATEUR par valeur de date_source — jusqu'ici seul le
--     numérateur (35 traces [CORR] en prod) était mesurable ;
--   * un taux de correction PARTIEL par valeur : rapporté aux seules lignes
--     dont la correction porte explicitement sur le champ "date" (format de
--     trace : voir tools/analyse_corpus_echecs.sql, bot.py `_corr_apply`) ;
--   * PAS le taux d'erreur réel : une ligne fausse et jamais remarquée ne
--     laisse aucune trace [CORR]. Ce script mesure ce qui a été CORRIGÉ,
--     jamais ce qui est FAUX.
-- =============================================================================

\set ON_ERROR_STOP on
\pset pager off

-- Filtre tenant réutilisable : -1 = toutes les données.
\if :{?potager}
\else
  \set potager -1
  \echo '⚠️  Aucun -v potager=<id> fourni : balayage GLOBAL, tous potagers confondus.'
\endif


-- -------------------------------------------------------------
-- 1. Répartition brute de date_source — le dénominateur (CA11)
-- -------------------------------------------------------------
SELECT
    COALESCE(date_source, '(NULL — antérieur à l''US ou chemin non couvert)') AS date_source,
    count(*) AS nb_evenements
FROM evenements
WHERE (:potager = -1 OR potager_id = :potager)
GROUP BY 1
ORDER BY nb_evenements DESC;


-- -------------------------------------------------------------
-- 2. Ventilation par CHEMIN — date_source × origine_parsing (CA12)
-- Les deux colonnes ensemble disent quel chemin se trompe, pas seulement
-- combien de fois : c'est cette ventilation qui désignera la prochaine
-- règle à ajouter à la grammaire déterministe.
-- -------------------------------------------------------------
SELECT
    COALESCE(origine_parsing, '(NULL)') AS origine_parsing,
    COALESCE(date_source, '(NULL)')     AS date_source,
    count(*)                            AS nb_evenements
FROM evenements
WHERE (:potager = -1 OR potager_id = :potager)
GROUP BY 1, 2
ORDER BY 1, nb_evenements DESC;


-- -------------------------------------------------------------
-- 3. Corrections de DATE spécifiquement, croisées avec la source au moment
--    de l'écriture — le numérateur, ventilé par date_source/origine_parsing.
--
--    Format de la trace (bot.py `_corr_apply`, LABELS["date"] = "date") :
--      <phrase dictée> | [CORR AAAA-MM-JJ] date: 2026-05-20 → 2026-05-25, ...
--    Une trace peut porter plusieurs champs séparés par ', ' — la ligne
--    n'est retenue que si l'un d'eux est explicitement "date".
-- -------------------------------------------------------------
WITH traces AS (
    SELECT id, origine_parsing, date_source,
           substring(texte_original from '\[CORR[^\]]*\]\s*(.*)$') AS corr
    FROM evenements
    WHERE texte_original LIKE '%[CORR%'
      AND (:potager = -1 OR potager_id = :potager)
),
champs AS (
    SELECT id, origine_parsing, date_source,
           trim(split_part(trim(item), ':', 1)) AS champ_corrige
    FROM traces, unnest(string_to_array(corr, ', ')) AS item
    WHERE position(':' in item) > 0
)
SELECT
    COALESCE(origine_parsing, '(NULL)') AS origine_parsing,
    COALESCE(date_source, '(NULL)')     AS date_source,
    count(*)                            AS nb_corrections_de_date
FROM champs
WHERE champ_corrige = 'date'
GROUP BY 1, 2
ORDER BY nb_corrections_de_date DESC;


-- -------------------------------------------------------------
-- 4. Taux de correction de date PAR VALEUR de date_source — la mesure que
--    l'US existe pour rendre possible. Un ratio par ligne, jamais un
--    pourcentage agrégé qui masquerait les petits effectifs.
-- -------------------------------------------------------------
WITH corrections_date AS (
    SELECT e.id
    FROM evenements e
    WHERE e.texte_original LIKE '%[CORR%'
      AND e.texte_original ~ '\[CORR[^\]]*\]\s*(.*,\s*)?date:'
      AND (:potager = -1 OR e.potager_id = :potager)
)
SELECT
    COALESCE(e.date_source, '(NULL)')                       AS date_source,
    count(*)                                                 AS nb_evenements,
    count(cd.id)                                             AS nb_corriges_sur_date,
    round(100.0 * count(cd.id) / NULLIF(count(*), 0), 1)     AS taux_correction_pct
FROM evenements e
LEFT JOIN corrections_date cd ON cd.id = e.id
WHERE (:potager = -1 OR e.potager_id = :potager)
GROUP BY 1
ORDER BY taux_correction_pct DESC NULLS LAST;
