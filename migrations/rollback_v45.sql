-- =============================================================================
-- rollback_v45.sql — Annule migration_v45.sql (symptômes, US-165)
-- =============================================================================
-- Supprime `symptome_bioagresseur` puis `symptome` (dans cet ordre : la seconde
-- est référencée par la première).
--
-- Aucune table existante n'est modifiée : cette migration n'ajoutait que deux
-- tables, leurs index et leurs politiques RLS. `bioagresseur`,
-- `culture_bioagresseur`, `culture_config`, `potagers` et `referentiel_source`
-- ne sont pas touchés — le référentiel d'US-162 survit intact, et
-- `/bioagresseur lister` continue de répondre.
--
-- Perte :
--   • la totalité des symptômes et de leurs synonymes en langage courant, qui
--     sont le vrai livrable de l'US — quelques minutes de rédaction par
--     symptôme, jamais reconstituables par extraction ;
--   • en conséquence, le pré-diagnostic : une description de symptôme retombe
--     alors à l'étage de raisonnement, exactement comme avant l'US.
-- Exporter les deux tables avant d'exécuter ce script. Le manifeste
-- data/referentiel/symptomes_redaction_interne.json permet de rejouer le
-- contenu PARTAGÉ ; les symptômes saisis LOCALEMENT par un potager, eux, ne s'y
-- trouvent pas et ne se réimportent pas.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces tables : `app/services/prediagnostic.py`, les blocs `symptomes` /
-- `symptomes_bioagresseurs` de `app/services/import_referentiel.py` et la
-- famille `prediagnostic_symptome` de `app/services/reponses_chiffrees.py`,
-- sans quoi ces chemins échoueraient en base.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS symptome_bioagresseur;
DROP TABLE IF EXISTS symptome;

COMMIT;

-- Vérification : ce compteur doit être vide (les tables n'existent plus).
SELECT COUNT(*) AS tables_restantes
FROM information_schema.tables
WHERE table_name IN ('symptome', 'symptome_bioagresseur');
