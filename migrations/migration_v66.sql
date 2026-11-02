-- =============================================================================
-- migration_v66.sql — Les messages spontanés du compagnon (US-267)
-- =============================================================================
-- Le distributeur fait partir dans Telegram ce que le veilleur a détecté (v65),
-- au bon moment et sous la bonne forme, sans plafond mais sans harceler :
-- thème coupé, plage de silence, résumé du matin, regroupement, passage en
-- résumé après trois messages sans réaction.
--
--   potager_membres (profil, partie 3 — par jardinier ET par potager)
--     proactivite_compagnon JSONB NULL  — le mode choisi par thème :
--         {"meteo": {"mode": "coupe", "le": "2026-10-30T18:00:00", "auto": false}, …}
--         mode immediat | resume | coupe ; thème absent = réglage par défaut.
--     silence_debut / silence_fin SMALLINT NULL  — heures (0-23) ; NULL = 21 h / 8 h.
--         Début égal à la fin : aucune plage de silence.
--     heure_resume SMALLINT NULL  — heure du point du matin ; NULL = 8 h.
--
--   signaux.etat : + « planifie » (le distributeur a pris le signal en charge).
--
--   messages_spontanes (nouvelle)  — un message parti vers UN jardinier :
--     genre signal | resume, themes, texte, redige agent | gabarit,
--     telegram_chat_id / telegram_message_id (gardés pour réécrire la carte, F2),
--     envoye_le, reaction_le (clic ou réponse : NULL = sans réaction).
--
--   envois_signaux (nouvelle)  — le sort d'un signal pour UN jardinier :
--     mode, etat en_attente | envoye | ignore, envoyer_le, motif,
--     annonce_bascule, message_id. UNIQUE (signal_id, user_id) : un signal n'est
--     planifié qu'une fois par jardinier, même si deux passages se croisent.
--
-- Horodatages en heure locale (Europe/Paris), comme les signaux.
-- ⚠️ RLS stricte (lecture comme écriture) sur les deux nouvelles tables, comme
-- `signaux` (v65) : le distributeur arme chaque potager à son tour.
--
-- Aucun backfill : sans réglage, les défauts s'appliquent (météo et rappels tout
-- de suite, le reste au point du matin, silence de 21 h à 8 h).
-- À exécuter avec le rôle propriétaire de la base. Droits de app_user : couverts
-- par les DEFAULT PRIVILEGES de migration_v18.
-- Idempotent. Rollback : migrations/rollback_v66.sql
-- =============================================================================

BEGIN;

ALTER TABLE potager_membres ADD COLUMN IF NOT EXISTS proactivite_compagnon JSONB;
ALTER TABLE potager_membres ADD COLUMN IF NOT EXISTS silence_debut SMALLINT;
ALTER TABLE potager_membres ADD COLUMN IF NOT EXISTS silence_fin SMALLINT;
ALTER TABLE potager_membres ADD COLUMN IF NOT EXISTS heure_resume SMALLINT;

ALTER TABLE potager_membres DROP CONSTRAINT IF EXISTS ck_potager_membres_heures_compagnon;
ALTER TABLE potager_membres ADD CONSTRAINT ck_potager_membres_heures_compagnon CHECK (
    (silence_debut IS NULL OR silence_debut BETWEEN 0 AND 23)
    AND (silence_fin IS NULL OR silence_fin BETWEEN 0 AND 23)
    AND (heure_resume IS NULL OR heure_resume BETWEEN 0 AND 23)
);

COMMENT ON COLUMN potager_membres.proactivite_compagnon IS
    'US-267 — Mode des messages spontanés par thème (immediat | resume | coupe) ; NULL = défauts.';

ALTER TABLE signaux DROP CONSTRAINT IF EXISTS ck_signaux_etat;
ALTER TABLE signaux ADD CONSTRAINT ck_signaux_etat
    CHECK (etat IN ('detecte', 'planifie', 'envoye', 'regroupe', 'ignore', 'repondu'));

CREATE TABLE IF NOT EXISTS messages_spontanes (
    id                  SERIAL       PRIMARY KEY,
    potager_id          INTEGER      NOT NULL REFERENCES potagers(id),
    user_id             INTEGER      NOT NULL REFERENCES users(id),
    genre               VARCHAR(10)  NOT NULL,
    themes              JSONB        NOT NULL,
    texte               TEXT         NOT NULL,
    redige              VARCHAR(8)   NOT NULL,
    telegram_chat_id    BIGINT,
    telegram_message_id BIGINT,
    envoye_le           TIMESTAMP    NOT NULL,
    reaction_le         TIMESTAMP,
    CONSTRAINT ck_messages_spontanes_genre CHECK (genre IN ('signal', 'resume')),
    CONSTRAINT ck_messages_spontanes_redige CHECK (redige IN ('agent', 'gabarit'))
);

CREATE INDEX IF NOT EXISTS ix_messages_spontanes_destinataire
    ON messages_spontanes (potager_id, user_id, envoye_le);
CREATE INDEX IF NOT EXISTS ix_messages_spontanes_id ON messages_spontanes (id);

COMMENT ON TABLE messages_spontanes IS
    'US-267 — Un message spontané parti vers un jardinier. L''identifiant Telegram est gardé '
    'pour réécrire la carte (F2) ; reaction_le compte les messages restés sans réponse.';

CREATE TABLE IF NOT EXISTS envois_signaux (
    id              SERIAL       PRIMARY KEY,
    potager_id      INTEGER      NOT NULL REFERENCES potagers(id),
    signal_id       INTEGER      NOT NULL REFERENCES signaux(id) ON DELETE CASCADE,
    user_id         INTEGER      NOT NULL REFERENCES users(id),
    mode            VARCHAR(10)  NOT NULL,
    etat            VARCHAR(12)  NOT NULL DEFAULT 'en_attente',
    envoyer_le      TIMESTAMP    NOT NULL,
    motif           VARCHAR(32),
    annonce_bascule BOOLEAN      NOT NULL DEFAULT false,
    message_id      INTEGER      REFERENCES messages_spontanes(id) ON DELETE SET NULL,
    traite_le       TIMESTAMP,
    CONSTRAINT uq_envois_signaux_signal_user UNIQUE (signal_id, user_id),
    CONSTRAINT ck_envois_signaux_mode CHECK (mode IN ('immediat', 'resume', 'coupe')),
    CONSTRAINT ck_envois_signaux_etat CHECK (etat IN ('en_attente', 'envoye', 'ignore'))
);

CREATE INDEX IF NOT EXISTS ix_envois_signaux_a_envoyer ON envois_signaux (potager_id, etat, envoyer_le);
CREATE INDEX IF NOT EXISTS ix_envois_signaux_id ON envois_signaux (id);

COMMENT ON TABLE envois_signaux IS
    'US-267 — Le sort d''un signal pour un jardinier : planifié une fois (UNIQUE), consommé '
    'de façon atomique (en_attente → envoye | ignore), par le seul planificateur du bot.';

ALTER TABLE messages_spontanes ENABLE ROW LEVEL SECURITY;
ALTER TABLE envois_signaux ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_messages_spontanes ON messages_spontanes;
CREATE POLICY tenant_isolation_messages_spontanes ON messages_spontanes
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

DROP POLICY IF EXISTS tenant_isolation_envois_signaux ON envois_signaux;
CREATE POLICY tenant_isolation_envois_signaux ON envois_signaux
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('messages_spontanes', 'envois_signaux');
SELECT polname FROM pg_policy
 WHERE polname IN ('tenant_isolation_messages_spontanes', 'tenant_isolation_envois_signaux');
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'potager_membres'
   AND column_name IN ('proactivite_compagnon', 'silence_debut', 'silence_fin', 'heure_resume');
