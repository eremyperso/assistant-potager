-- =============================================================================
-- rollback_v51.sql — Annule migration_v51.sql (file de gestes, US-224)
-- =============================================================================
-- Ramène `gestes_intentions` à la forme d'US-196 (laissez-passer à usage
-- unique) et retire la table de relance.
--
-- Perte : l'état des gestes en file, leur motif de refus, la trace des
-- avertissements, et tous les réglages de relance (dont les coupures demandées
-- par les jardiniers — elles seront à redemander). Aucun événement n'est
-- concerné : un geste en attente n'a jamais rien écrit, c'est toute sa raison
-- d'être.
--
-- ⚠️ Les gestes en attente au moment du rollback redeviennent des liens à usage
-- unique de quinze minutes : ceux déposés il y a plus de quinze minutes seront
-- refusés « expiré » au prochain clic. C'est le comportement d'US-196, qui est
-- précisément ce que cette migration remplaçait.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit/écrit plus
-- ces colonnes : `app/services/file_gestes.py`, `app/services/relances_file.py`,
-- `app/bot/file_gestes.py`, `database/models.py` (GesteIntention,
-- FileGestesReglage), les endpoints `/gestes/…` d'`app/api/main.py`.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS files_gestes_reglages;

DROP INDEX IF EXISTS ix_gestes_intentions_user_etat;

-- `traite_le` reprend son ancien nom ET son ancienne sémantique : un geste sorti
-- de la file redevient « un lien déjà utilisé ». Les gestes encore en attente
-- gardent `traite_le` à NULL et restent donc ouvrables — dans la limite des
-- quinze minutes d'US-196.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'gestes_intentions' AND column_name = 'traite_le'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'gestes_intentions' AND column_name = 'consomme_le'
    ) THEN
        ALTER TABLE gestes_intentions RENAME COLUMN traite_le TO consomme_le;
    END IF;
END $$;

ALTER TABLE gestes_intentions DROP COLUMN IF EXISTS avertissement_le;
ALTER TABLE gestes_intentions DROP COLUMN IF EXISTS motif_refus;
ALTER TABLE gestes_intentions DROP COLUMN IF EXISTS etat;

COMMIT;
