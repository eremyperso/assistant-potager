-- =============================================================================
-- rollback_v31.sql — Annule migration_v31.sql (mesure de consommation LLM, US-092)
-- =============================================================================
-- Supprime la table `conso_tokens` et ses index. Aucune fonctionnalité
-- utilisateur n'en dépend : la passerelle LLM continue de fonctionner sans
-- elle (l'écriture de la mesure est déjà tolérante à l'échec, elle logue un
-- WARNING et rend la main). En revanche, TOUT l'historique de consommation est
-- perdu — c'est exactement la matière que l'US de quotas attend pour fixer un
-- prix. Ne rejouer ce rollback qu'en connaissance de cause.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_conso_tokens_type;
DROP INDEX IF EXISTS idx_conso_tokens_potager_date;

DROP TABLE IF EXISTS conso_tokens;

COMMIT;
