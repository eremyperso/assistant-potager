-- =============================================================================
-- rollback_v32.sql — Annule migration_v32.sql (observabilité cascade + retour
-- jardinier, US-097)
-- =============================================================================
-- Supprime `routage_retours` puis `routage_logs` (ordre imposé par la clé
-- étrangère routage_retours.routage_log_id) et leurs index. Aucune
-- fonctionnalité de réponse au jardinier n'en dépend : l'écriture du journal et
-- du retour est déjà tolérante à l'échec (log WARNING, ne bloque jamais une
-- réponse). En revanche, TOUT l'historique de routage et les avis déjà
-- recueillis sont perdus — c'est exactement la matière que cette US existe
-- pour produire. Ne rejouer ce rollback qu'en connaissance de cause.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_routage_retours_potager;
DROP TABLE IF EXISTS routage_retours;

DROP INDEX IF EXISTS idx_routage_logs_cree_le;
DROP INDEX IF EXISTS idx_routage_logs_potager_date;
DROP TABLE IF EXISTS routage_logs;

COMMIT;
