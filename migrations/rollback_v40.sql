-- =============================================================================
-- rollback_v40.sql — Retire Wind River Greens du registre (US-161)
-- =============================================================================
-- ⚠️ À exécuter dans cet ordre, et pas autrement : les valeurs qui dérivent de
-- la source doivent être effacées AVANT la ligne de registre, sinon les clés
-- étrangères refusent la suppression — et c'est tant mieux : c'est précisément
-- le garde-fou que CA3 d'US-161 met en place. Aucune valeur ne doit survivre à
-- la disparition de son origine.
--
-- C'est aussi la procédure à suivre si cette source devenait litigieuse, sans
-- rollback de migration : `python tools/importer_referentiel.py --derive-de
-- wind_river_greens` liste d'abord tout ce qui en dérive, ce script l'efface.
--
-- Perte : les expositions et besoins en eau importés depuis ce jeu de données.
-- Les valeurs corrigées au bot portent l'origine `saisie_manuelle` et ne sont
-- PAS touchées — c'est le sens même de la traçabilité par attribut.
--
-- ⚠️ À exécuter APRÈS avoir redéployé un code qui ne cite plus cette source
-- (app/services/adaptateur_wind_river.py et l'entrée `wind_river_greens` de
-- referentiel_sources.SOURCES_SOCLE), sans quoi un appel à `garantir_source`
-- la recréerait aussitôt.
-- =============================================================================

BEGIN;

-- [CA3] Les valeurs d'abord, et leur origine avec elles : une valeur sans
-- origine serait un attribut orphelin, exactement ce que l'US interdit.
UPDATE culture_config c
   SET exposition = NULL, exposition_source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND c.exposition_source_id = s.id;

UPDATE culture_config c
   SET besoin_eau = NULL, besoin_eau_source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND c.besoin_eau_source_id = s.id;

UPDATE culture_config c
   SET profondeur_semis_cm = NULL, profondeur_semis_source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND c.profondeur_semis_source_id = s.id;

UPDATE culture_config c
   SET rusticite_min_c = NULL, rusticite_min_source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND c.rusticite_min_source_id = s.id;

-- Les familles, au cas où une reprise ultérieure les rattacherait à cette source.
UPDATE familles_botaniques f
   SET source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND f.source_id = s.id;

UPDATE culture_config c
   SET famille_source_id = NULL
  FROM referentiel_source s
 WHERE s.code = 'wind_river_greens' AND c.famille_source_id = s.id;

DELETE FROM referentiel_source WHERE code = 'wind_river_greens';

COMMIT;

-- Vérification : ce compteur doit valoir zéro.
SELECT COUNT(*) AS source_restante
FROM referentiel_source WHERE code = 'wind_river_greens';
