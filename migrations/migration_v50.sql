-- =============================================================================
-- migration_v50.sql — Intentions de geste préparées par la PWA (US-196)
-- =============================================================================
-- La PWA ne sait rien enregistrer : le seul chemin d'écriture de l'application
-- est le bot (US-094 / US-021). US-196 n'en ouvre pas un second — elle ajoute
-- une PRÉPARATION : la PWA dépose un geste pré-parsé, de courte durée, et
-- ouvre le compagnon par un lien profond `?start=<code>` (US-091). Le bot le
-- présente dans son flux de confirmation habituel. Rien n'est écrit tant que
-- le jardinier n'a pas appuyé sur « Confirmer ».
--
-- [CA4] La table existe parce que l'API et le bot sont DEUX PROCESSUS : un
--       cache mémoire (le motif d'US-179, `_CONFIANCE_PENDING`) ne traverse
--       pas cette frontière.
--
-- [CA3] `code` : opaque, 128 bits d'aléa minimum, alphabet `A-Za-z0-9_-` et
--       64 caractères au plus — les deux bornes du paramètre `start` de
--       Telegram. Préfixe réservé `g` (minuscule) : `liaisons_telegram.code`
--       fait exactement 6 caractères d'un alphabet majuscule sans ambiguïté,
--       les deux familles ne peuvent donc pas se confondre à la lecture.
--
-- [CA2] `geste` porte l'item PRÉ-PARSÉ, au contrat de `llm.parseur_deterministe`
--       (US-094) : c'est ce même contrat que `saisie._parse_and_save` reçoit
--       déjà du bouton « Enregistrer » d'US-179. Aucun vocabulaire nouveau.
--
-- ⚠️ RLS : policy TOLÉRANTE au GUC non armé, et c'est délibéré (arbitrage du
--    21/09/2026). Le bot cherche l'intention PAR SON CODE avant de savoir de
--    quel potager elle relève — c'est justement la ligne qui le lui apprend —
--    et il a déjà armé `app.potager_id` sur le potager par défaut au dispatch.
--    Une policy stricte masquerait donc systématiquement la ligne. La lecture
--    du bot se fait GUC désarmé (`tenant_scope(None)`, un seul appelant :
--    `app/services/intentions_geste.consommer_intention`) ; tout chemin qui a
--    un contexte tenant — l'API, seule à ÉCRIRE ici — reste strictement isolé,
--    en lecture comme en écriture. Les deux autres tables de codes du projet
--    (`liaisons_telegram`, `invitations`) n'ont, elles, aucune RLS du tout.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : IF NOT EXISTS partout.
-- Rollback : migrations/rollback_v50.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS gestes_intentions (
    id          SERIAL      PRIMARY KEY,
    code        VARCHAR(64) NOT NULL UNIQUE,
    user_id     INTEGER     NOT NULL REFERENCES users(id),
    potager_id  INTEGER     NOT NULL REFERENCES potagers(id),
    geste       JSONB       NOT NULL,
    ecran       VARCHAR(32),
    cree_le     TIMESTAMP   NOT NULL DEFAULT now(),
    expire_le   TIMESTAMP   NOT NULL,
    consomme_le TIMESTAMP
);

-- Purge (`supprimer_intentions_expirees`) : balayage par date d'expiration.
CREATE INDEX IF NOT EXISTS ix_gestes_intentions_expire_le  ON gestes_intentions (expire_le);
CREATE INDEX IF NOT EXISTS ix_gestes_intentions_potager_id ON gestes_intentions (potager_id);

COMMENT ON TABLE gestes_intentions IS
    'US-196/CA4 — Geste pré-parsé préparé par la PWA, en attente de confirmation dans le '
    'compagnon Telegram. Éphémère (15 min), à usage unique. N''est NI un événement, NI un '
    'stock, NI une statistique : rien ici n''apparaît au Journal.';

COMMENT ON COLUMN gestes_intentions.code IS
    'US-196/CA3 — Opaque, ≥128 bits d''aléa, préfixe réservé « g », alphabet et longueur '
    'compatibles avec le paramètre `start` d''un lien profond Telegram. Le lien ne '
    'transporte QUE ce code : aucun nom de culture, aucune donnée du potager n''apparaît '
    'dans l''adresse ni dans les journaux du serveur web.';

COMMENT ON COLUMN gestes_intentions.geste IS
    'US-196/CA1, CA5 — Item pré-parsé au contrat de llm.parseur_deterministe (US-094), '
    'celui-là même que `saisie._parse_and_save` reçoit du bouton « Enregistrer » d''US-179. '
    'La parcelle y est un NOM (résolu à la préparation puis re-résolu à la confirmation), '
    'jamais un identifiant : le flux du bot ne connaît que des noms.';

COMMENT ON COLUMN gestes_intentions.ecran IS
    'US-196/CA1 — Écran d''origine (plan | stocks | pepiniere | fiche_culture…), pour la '
    'mesure d''usage. Jamais lu par le flux d''enregistrement.';

COMMENT ON COLUMN gestes_intentions.consomme_le IS
    'US-196/CA6 — Usage unique, même motif que `liaisons_telegram.utilise_le` (US-045) : '
    'une intention consommée est refusée, elle n''est pas supprimée, pour que le refus '
    'puisse être motivé en clair (« déjà utilisé ») plutôt que confondu avec un code inconnu.';

-- ── [CA4] RLS — policy tolérante au GUC non armé (voir l'en-tête) ────────────
ALTER TABLE gestes_intentions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_gestes_intentions ON gestes_intentions;
CREATE POLICY tenant_isolation_gestes_intentions ON gestes_intentions
    USING (
        current_setting('app.potager_id', true) IS NULL
        OR current_setting('app.potager_id', true) = ''
        OR potager_id = current_setting('app.potager_id', true)::int
    )
    WITH CHECK (potager_id = current_setting('app.potager_id', true)::int);

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'gestes_intentions';
SELECT polname FROM pg_policy WHERE polname = 'tenant_isolation_gestes_intentions';
