-- =============================================================================
-- rollback_v41.sql — Annule migration_v41.sql (associations de cultures, US-163)
-- =============================================================================
-- Supprime `association_culture` et l'index composite ajouté à `evenements`.
-- `evenements`, `culture_config`, `familles_botaniques` et `referentiel_source`
-- ne sont pas touchés : cette migration ne faisait qu'ajouter une table de
-- relation et un index, aucune colonne existante n'a été modifiée.
--
-- Perte : la totalité des associations saisies/corrigées au bot
-- (`/association saisir`) — c'est le coût assumé de l'arbitrage « associations
-- saisies, pas importées » (docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §2.1) :
-- rien ne se réimporte, tout se ressaisit. Exporter `association_culture` avant
-- d'exécuter ce script si des associations ont été saisies.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- cette table : `app/services/associations.py`, `app/services/rotation.py`
-- (la requête de rotation ne dépend pas du schéma retiré ici, mais perd son
-- index composite — non bloquant, juste plus lent) et les sous-commandes
-- `/association` et `/rotation` de `bot.py`, sans quoi ces chemins échoueraient
-- en base.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS association_culture;

DROP INDEX IF EXISTS idx_evenements_parcelle_date;

COMMIT;

-- Vérification : ce compteur doit être vide (la table n'existe plus).
SELECT COUNT(*) AS table_restante
FROM information_schema.tables
WHERE table_name = 'association_culture';
