-- =============================================================================
-- rollback_v44.sql — Annule migration_v44.sql (journal d'interprétation, US-172)
-- =============================================================================
-- Retire les deux colonnes ajoutées à `routage_logs`. Aucune autre table n'est
-- touchée : la migration n'ajoutait rien d'autre, ni index, ni contrainte, ni
-- politique RLS.
--
-- Perte : l'historique des commandes interprétées et de leur issue. C'est la
-- seule trace qui dit quelles formulations le jardinier refuse ou abandonne,
-- donc lesquelles enrichir ensuite (CA18) — l'exporter avant d'exécuter ce
-- script si l'on compte s'en servir :
--
--   \copy (SELECT cree_le, potager_id, question_normalisee, commande_interpretee,
--                 issue_interpretation, origine_classification, confiance, latence_ms
--          FROM routage_logs WHERE commande_interpretee IS NOT NULL)
--   TO 'interpretations.csv' CSV HEADER;
--
-- Le reste du journal de routage (US-097, US-098) est intact : ces deux
-- colonnes sont nullables et ne portent rien pour une demande qui n'est pas
-- passée par l'interpréteur.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne les écrit
-- plus : `app/services/interpreteur_commandes.persister_journal` et les points
-- d'appel de `bot.py`, sans quoi l'écriture du journal échouerait — sans
-- conséquence sur le service rendu (la journalisation ne lève jamais), mais
-- avec un avertissement à chaque commande dictée.
-- =============================================================================

BEGIN;

ALTER TABLE routage_logs DROP COLUMN IF EXISTS issue_interpretation;
ALTER TABLE routage_logs DROP COLUMN IF EXISTS commande_interpretee;

COMMIT;

-- ── Contrôle post-rollback ──────────────────────────────────────────────────
-- Attendu : 0 ligne.
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'routage_logs'
  AND column_name IN ('commande_interpretee', 'issue_interpretation');
