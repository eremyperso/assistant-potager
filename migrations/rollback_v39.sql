-- =============================================================================
-- rollback_v39.sql — Annule migration_v39.sql (attributs agronomiques, US-161)
-- =============================================================================
-- Retire les quatre attributs de conduite et leurs quatre colonnes d'origine.
-- L'ordre importe peu ici (aucune table n'est supprimée), mais les colonnes
-- d'origine partent d'abord, comme dans la v38 : une FK ne survit jamais à ce
-- qu'elle qualifie.
--
-- Perte : la totalité des valeurs d'exposition, de besoin en eau, de profondeur
-- de semis et de rusticité — **y compris les corrections saisies au bot par le
-- jardinier**, qui ne sont stockées nulle part ailleurs. C'est la perte la plus
-- coûteuse de ce rollback : une valeur importée se réimporte, une correction de
-- terrain ne se retrouve pas. Exporter `culture_config` avant d'exécuter ce
-- script si des corrections ont eu lieu.
--
-- Le reste de `culture_config` n'est PAS touché : type d'organe de récolte,
-- description agronomique, espacement, surface au sol, famille botanique et son
-- origine survivent tels quels. L'application retombe exactement sur le
-- comportement d'US-166, où une culture porte sa famille mais aucune
-- caractéristique de conduite.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit plus ces
-- colonnes : `app/services/attributs_culture.py`, le bloc `cultures_attributs`
-- de `app/services/import_referentiel.py`, les sous-commandes `/culture
-- exposition|eau|profondeur|rusticite|attributs` de `bot.py` et les quatre
-- entrées correspondantes de `referentiel_sources.TABLES_RATTACHEES` — sans
-- quoi ces chemins échoueraient en base.
-- =============================================================================

BEGIN;

ALTER TABLE culture_config
    DROP COLUMN IF EXISTS exposition_source_id,
    DROP COLUMN IF EXISTS besoin_eau_source_id,
    DROP COLUMN IF EXISTS profondeur_semis_source_id,
    DROP COLUMN IF EXISTS rusticite_min_source_id;

ALTER TABLE culture_config
    DROP COLUMN IF EXISTS exposition,
    DROP COLUMN IF EXISTS besoin_eau,
    DROP COLUMN IF EXISTS profondeur_semis_cm,
    DROP COLUMN IF EXISTS rusticite_min_c;

COMMIT;
