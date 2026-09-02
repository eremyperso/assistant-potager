-- =============================================================================
-- rollback_v37.sql — Annule migration_v37.sql (familles botaniques, US-067)
-- =============================================================================
-- Retire `culture_config.famille_id` puis supprime `familles_botaniques`.
--
-- Perte : la famille botanique et le délai de retour enregistrés (les 4
-- corrections manuelles éventuelles depuis le bot, comme le pré-remplissage).
-- Rien d'autre n'en dépend : le regroupement de l'écran Pépinière retombe sur
-- son ancien repli 100% "Autres" (aucune donnée serveur à lire), exactement le
-- comportement d'avant US-061/US-067 — aucune autre lecture (Stocks,
-- Statistiques, bot) n'est affectée par ce rollback (CA9).
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit plus
-- `culture_config.famille_id` ni `familles_botaniques` (app/services/familles.py,
-- commande bot /culture) — sans quoi ces chemins échoueraient en base.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_culture_config_famille;

ALTER TABLE culture_config
    DROP COLUMN IF EXISTS famille_id;

DROP TABLE IF EXISTS familles_botaniques;

COMMIT;
