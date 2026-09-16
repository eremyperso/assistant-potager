-- =============================================================================
-- migration_v48.sql — Rattrape 'bette' manquante dans culture_config
-- =============================================================================
-- migration_v6.sql insère 46 cultures avec des ids EXPLICITES (100-145), sous
-- un bare `ON CONFLICT DO NOTHING` — sans cible, il absorbe AUSSI un conflit de
-- clé primaire, pas seulement le conflit d'unicité sur `nom` qu'il visait.
--
-- Si une base avait déjà, avant l'exécution de v6, une culture personnalisée
-- occupant l'id 111 (SERIAL assigné par un jardinier), l'INSERT de 'bette'
-- (id=111) est alors silencieusement ignoré : aucune erreur, migration marquée
-- appliquée, et 'bette' n'existe jamais sur cette base précise — constaté en
-- dev le 16/09/2026 (tools/ingerer_connaissance.py refuse les deux fiches
-- data/connaissance/agronomie/blette-*.md, CA2 : une référence, jamais un
-- libellé). D'autres environnements peuvent porter le même défaut latent.
--
-- Correction PAR LE NOM, jamais par l'id — laisse SERIAL assigner un id libre,
-- ne rejoue rien si 'bette' existe déjà (contenu identique à migration_v6.sql).
-- Idempotent, sans BEGIN/COMMIT nécessaire (un seul statement conditionnel).
-- Rollback : migrations/rollback_v48.sql
-- =============================================================================

INSERT INTO culture_config (nom, type_organe_recolte, description_agronomique)
SELECT 'bette', 'reproducteur', 'Côtes et feuilles, récolte en coupe successive — plante bisannuelle'
WHERE NOT EXISTS (SELECT 1 FROM culture_config WHERE nom = 'bette');

-- ── Vérification ─────────────────────────────────────────────────────────────
SELECT id, nom FROM culture_config WHERE nom = 'bette';
-- Attendu : une ligne.
