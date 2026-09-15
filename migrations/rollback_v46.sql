-- =============================================================================
-- rollback_v46.sql — Annule migration_v46.sql (calendrier cultural, US-068)
-- =============================================================================
-- Supprime `duree_culturale`, `fenetre_culturale` puis `itineraire_cultural`
-- (dans cet ordre : les deux premières référencent la troisième), et retire la
-- colonne `potagers.zone_climatique`.
--
-- `culture_config` et `referentiel_source` ne sont pas touchés : cette
-- migration ne semait aucune source (les calendriers s'importent sous des
-- sources déjà au registre, ou naissent sous `saisie_manuelle`).
--
-- Perte :
--   • tous les calendriers, importés comme corrigés au bot (/calendrier) — les
--     calendriers PERSONNALISÉS d'un potager ne se réimportent pas, ils se
--     ressaisissent : exporter les trois tables avant si des corrections existent ;
--   • les zones climatiques CHOISIES par les jardiniers (la zone déduite de la
--     localisation, elle, n'était pas stockée et ne se perd pas).
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces tables ni cette colonne : `app/services/calendrier_cultural.py`, le bloc
-- `cultures_calendriers` de `app/services/import_referentiel.py`, la commande
-- `/calendrier` de `bot.py` et `GET /cultures/{culture}/calendrier` de `main.py`.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS duree_culturale;
DROP TABLE IF EXISTS fenetre_culturale;
DROP TABLE IF EXISTS itineraire_cultural;

ALTER TABLE potagers DROP COLUMN IF EXISTS zone_climatique;

COMMIT;

-- Vérification : ce compteur doit valoir 0.
SELECT COUNT(*) AS objets_restants
FROM information_schema.columns
WHERE (table_name = 'potagers' AND column_name = 'zone_climatique')
   OR table_name IN ('itineraire_cultural', 'fenetre_culturale', 'duree_culturale');
