-- =============================================================================
-- rollback_v43.sql — Annule migration_v43.sql (bioagresseurs, US-162)
-- =============================================================================
-- Supprime `culture_bioagresseur` puis `bioagresseur` (dans cet ordre : la
-- seconde est référencée par la première), et retire la source `eppo` du
-- registre si — et seulement si — plus rien n'en dérive.
--
-- Aucune table existante n'est modifiée : cette migration n'ajoutait que deux
-- tables, leurs index, leurs politiques RLS et une ligne de registre.
-- `culture_config`, `potagers` et `referentiel_source` ne sont pas touchés.
--
-- Perte :
--   • la totalité des identités de bioagresseurs et des arêtes culture ×
--     bioagresseur, importées comme saisies au bot (`/bioagresseur`) ;
--   • en conséquence, `/bioagresseur lister` et tout ce qui s'appuie dessus.
-- Exporter les deux tables avant d'exécuter ce script si des saisies locales ont
-- été faites : elles ne se réimportent pas, elles se ressaisissent.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces tables : `app/services/bioagresseurs.py`, les blocs `bioagresseurs` /
-- `cultures_bioagresseurs` de `app/services/import_referentiel.py` et la
-- commande `/bioagresseur` de `bot.py`, sans quoi ces chemins échoueraient en
-- base.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS culture_bioagresseur;
DROP TABLE IF EXISTS bioagresseur;

-- La source `eppo` n'est retirée que si plus RIEN n'en dérive. Les deux tables
-- viennent d'être supprimées, mais un code EPPO pourrait avoir été rattaché
-- ailleurs entre-temps (US-165) : `donnees_derivees` reste la question à poser
-- avant tout retrait de source (US-166/CA4), et ce DELETE conditionnel en est la
-- transcription SQL — il ne fait rien plutôt que de casser une FK.
DELETE FROM referentiel_source
WHERE code = 'eppo'
  AND NOT EXISTS (SELECT 1 FROM familles_botaniques  f WHERE f.source_id = referentiel_source.id)
  AND NOT EXISTS (SELECT 1 FROM association_culture  a WHERE a.source_id = referentiel_source.id)
  AND NOT EXISTS (
      SELECT 1 FROM culture_config c
      WHERE referentiel_source.id IN (
          c.famille_source_id, c.exposition_source_id, c.besoin_eau_source_id,
          c.profondeur_semis_source_id, c.rusticite_min_source_id
      )
  );

COMMIT;

-- Vérification : ce compteur doit être vide (les tables n'existent plus).
SELECT COUNT(*) AS tables_restantes
FROM information_schema.tables
WHERE table_name IN ('bioagresseur', 'culture_bioagresseur');
