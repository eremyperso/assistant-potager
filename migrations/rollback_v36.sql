-- =============================================================================
-- rollback_v36.sql — Annule migration_v36.sql (cache de questions, US-095)
-- =============================================================================
-- Supprime la table `questions_cache` et ses index.
--
-- Sans perte fonctionnelle : la table ne contient que des réponses
-- reconstituables. Les entrées `template_sql` ne mémorisent qu'un aiguillage
-- — leurs valeurs étaient de toute façon recalculées à chaque service par
-- l'étage des données (US-096), qui continue de répondre exactement pareil
-- sans elles. Les entrées `figee` ne portent que du savoir général, que
-- l'étage de raisonnement reproduira au prochain passage.
--
-- Ce qui est perdu : la latence et le coût économisés par l'étage 0bis, et la
-- mesure du taux de service depuis le cache (US-097/CA12). Aucune donnée de
-- potager n'est perdue — il n'en existe aucune ici, par construction.
--
-- ⚠️ À exécuter APRÈS avoir déployé une version du code qui n'appelle plus
-- `app/services/cache_questions.py` — sans quoi chaque question journaliserait
-- un échec de lecture du cache (sans conséquence pour le jardinier : l'étage
-- 0bis rend la main à la cascade en cas d'erreur, mais le journal serait
-- pollué à chaque question).
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_questions_cache_fragment;
DROP INDEX IF EXISTS idx_questions_cache_potager;
DROP INDEX IF EXISTS idx_questions_cache_motif;
DROP INDEX IF EXISTS idx_questions_cache_aiguillage;

DROP TABLE IF EXISTS questions_cache;

COMMIT;
