-- =============================================================================
-- rollback_v48.sql — Annule migration_v48.sql (rattrapage de 'bette')
-- =============================================================================
-- Retire 'bette' de culture_config, SEULEMENT si rien ne la référence déjà —
-- un événement ou une fiche de connaissance rattachée à cette culture rendrait
-- la suppression destructrice.
--
-- ⚠️ À exécuter uniquement si les fiches data/connaissance/agronomie/blette-*.md
-- ont été retirées du dépôt et réingérées (--elaguer) au préalable : sinon
-- l'ingestion suivante échouera de nouveau, pour la même raison (CA2).
-- =============================================================================

DELETE FROM culture_config
WHERE nom = 'bette'
  AND NOT EXISTS (SELECT 1 FROM evenements WHERE culture = 'bette')
  AND NOT EXISTS (
      SELECT 1 FROM knowledge_documents WHERE reference LIKE 'data/connaissance/agronomie/blette-%'
  );
