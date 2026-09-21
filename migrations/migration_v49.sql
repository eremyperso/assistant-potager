-- =============================================================================
-- migration_v49.sql — Abri et paillage d'une parcelle (US-181)
-- =============================================================================
-- Le moteur de confiance (US-178) traitait une serre comme un rang en plein
-- vent. La parcelle porte désormais deux attributs DÉCLARÉS par le jardinier :
--
-- [CA1] `parcelles.abri`     : aucun | voile | chassis | tunnel | serre.
--       Vocabulaire validé au point d'écriture (utils/parcelles.py), comme
--       `fenetre_culturale.phase` — pas de CHECK SQL, il se révise en Python.
--       NULL = jamais renseigné, distinct de 'aucun' (= déclaré sans abri).
-- [CA1] `parcelles.paillage` : BOOLEAN. NULL = jamais renseigné.
--
-- [CA7] Colonnes nullables, AUCUN backfill : on ne suppose rien de l'existant.
--       `est_pepiniere` n'est pas réinterprété comme un abri.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : ADD COLUMN IF NOT EXISTS.
-- Rollback : migrations/rollback_v49.sql
-- =============================================================================

BEGIN;

ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS abri     VARCHAR(16);
ALTER TABLE parcelles ADD COLUMN IF NOT EXISTS paillage BOOLEAN;

COMMIT;
