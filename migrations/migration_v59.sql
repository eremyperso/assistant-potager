-- =============================================================================
-- migration_v59.sql — Outils appelés par l'agent interpréteur (US-235)
-- =============================================================================
-- US-235 branche l'agent interpréteur à la place du repli modèle de US-172.
-- Le journal des commandes interprétées (`routage_logs`) porte déjà la commande,
-- l'origine (`origine_classification`, qui reçoit la valeur 'agent') et l'issue
-- (`issue_interpretation`, qui reçoit 'ombre' en AGENT_MODE=ombre). Il manquait
-- le nom des OUTILS appelés (CA14) : la commande ne dit pas, par exemple, que
-- l'agent a choisi `poser_question` plutôt qu'une commande.
--
-- [CA14] `routage_logs.outils_agent` : texte NULLABLE (128), noms d'outils
--       séparés par des virgules. NULL pour toute ligne qui n'est pas de l'agent.
--       Aucun backfill : l'agent n'existait pas avant cette migration.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent. Rollback : migrations/rollback_v59.sql
-- =============================================================================

BEGIN;

ALTER TABLE routage_logs
    ADD COLUMN IF NOT EXISTS outils_agent VARCHAR(128);

COMMENT ON COLUMN routage_logs.outils_agent IS
    '[US-235] Outils appelés par l''agent interpréteur, séparés par des virgules. '
    'NULL hors origine_classification = ''agent''.';

COMMIT;
