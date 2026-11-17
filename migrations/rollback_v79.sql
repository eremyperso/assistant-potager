-- ═════════════════════════════════════════════════════════════════════════════
-- rollback_v79.sql — annule migration_v79.sql [US-316]
-- ═════════════════════════════════════════════════════════════════════════════
-- Perd les seuils réglés et l'historique des alertes (les seuils par défaut se recréent au premier
-- passage du code, s'il est encore là). Aucune donnée de jardinier. Idempotent.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP TABLE IF EXISTS alertes_pilotage;
DROP TABLE IF EXISTS seuils_pilotage;

COMMIT;
