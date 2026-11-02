-- =============================================================================
-- rollback_v66.sql — Annule les messages spontanés du compagnon (US-267)
-- =============================================================================
-- ⚠️ Perd les messages envoyés, le sort des signaux par jardinier et les
-- réglages de proactivité et de silence. Les signaux restent (v65) ; ceux qui
-- étaient « planifie » reviennent à « detecte ».
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_envois_signaux ON envois_signaux;
DROP TABLE IF EXISTS envois_signaux;

DROP POLICY IF EXISTS tenant_isolation_messages_spontanes ON messages_spontanes;
DROP TABLE IF EXISTS messages_spontanes;

UPDATE signaux SET etat = 'detecte' WHERE etat = 'planifie';
ALTER TABLE signaux DROP CONSTRAINT IF EXISTS ck_signaux_etat;
ALTER TABLE signaux ADD CONSTRAINT ck_signaux_etat
    CHECK (etat IN ('detecte', 'envoye', 'regroupe', 'ignore', 'repondu'));

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_heures_compagnon;
ALTER TABLE potager_membres DROP COLUMN IF EXISTS heure_resume;
ALTER TABLE potager_membres DROP COLUMN IF EXISTS silence_fin;
ALTER TABLE potager_membres DROP COLUMN IF EXISTS silence_debut;
ALTER TABLE potager_membres DROP COLUMN IF EXISTS proactivite_compagnon;

COMMIT;
