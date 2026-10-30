-- =============================================================================
-- migration_v62.sql — Les actions menées, et où une proposition a été traitée (US-261, US-260)
-- =============================================================================
-- 1. **`actions_menees`** (US-261) — la mémoire de ce que le compagnon a fait
--    pour le jardinier, quel que soit le canal : une entrée par écriture
--    exécutée (un geste enregistré, une commande confirmée, une étape de plan).
--    Elle est écrite par le CHEMIN D'EXÉCUTION, jamais par le modèle : aucun
--    outil de l'agent n'y écrit. L'agent en reçoit les cinq dernières des 24 h
--    sous des références opaques (A1…A5) pour pouvoir dire « mon dernier semis ».
--
--    Une entrée porte : la nature de l'action, la référence de la cible en base
--    (`cible_type` + `cible_id`, ou `cible_nom` quand l'exécuteur ne rend pas
--    d'identifiant), un résumé, les valeurs AVANT / APRÈS quand l'exécuteur les
--    connaît, le canal et le statut.
--
-- 2. **`propositions.traite_canal`** (US-260 / CA5) — le canal qui a fait sortir
--    une proposition de l'attente. « Oui » dit après un clic sur le bouton ne
--    refait rien et répond OÙ et QUAND elle a été traitée. `canal` reste le canal
--    d'origine de la proposition ; les deux peuvent différer (proposée dans la
--    PWA, confirmée au bouton de Telegram).
--
-- ⚠️ RLS : `actions_menees` est stricte en lecture comme en écriture — une action
--    s'écrit et se lit dans le potager où elle a eu lieu. Les actions d'un
--    potager ne sont jamais visibles depuis un autre (US-261 / CA6).
--
-- À exécuter avec le rôle propriétaire de la base. Droits de app_user : couverts
-- par les DEFAULT PRIVILEGES de migration_v18.
-- Idempotent. Rollback : migrations/rollback_v62.sql
-- =============================================================================

BEGIN;

-- ── 1. Les actions menées ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS actions_menees (
    id             SERIAL       PRIMARY KEY,
    user_id        INTEGER      REFERENCES users(id),
    potager_id     INTEGER      NOT NULL REFERENCES potagers(id),
    canal          VARCHAR(16)  NOT NULL DEFAULT 'inconnu',
    nature         VARCHAR(16)  NOT NULL,
    cible_type     VARCHAR(32),
    cible_id       INTEGER,
    cible_nom      VARCHAR(120),
    resume         TEXT         NOT NULL DEFAULT '',
    avant          JSONB,
    apres          JSONB,
    statut         VARCHAR(16)  NOT NULL DEFAULT 'reussie',
    proposition_id INTEGER      REFERENCES propositions(id) ON DELETE SET NULL,
    cree_le        TIMESTAMP    NOT NULL DEFAULT now()
);

ALTER TABLE actions_menees DROP CONSTRAINT IF EXISTS ck_actions_menees_nature;
ALTER TABLE actions_menees
    ADD CONSTRAINT ck_actions_menees_nature
    CHECK (nature IN ('geste', 'commande'));

ALTER TABLE actions_menees DROP CONSTRAINT IF EXISTS ck_actions_menees_statut;
ALTER TABLE actions_menees
    ADD CONSTRAINT ck_actions_menees_statut
    CHECK (statut IN ('reussie', 'echouee'));

-- Les cinq dernières actions d'un potager sur 24 h : la lecture de chaque phrase.
CREATE INDEX IF NOT EXISTS ix_actions_menees_fil
    ON actions_menees (potager_id, cree_le);

COMMENT ON TABLE actions_menees IS
    'US-261 — Mémoire des actions menées par le compagnon, tous canaux : une entrée par '
    'écriture exécutée. Écrite par le chemin d''exécution, jamais par le modèle.';
COMMENT ON COLUMN actions_menees.nature IS
    'US-261/CA1 — geste (un événement enregistré) | commande (une commande confirmée ou une étape de plan).';
COMMENT ON COLUMN actions_menees.cible_id IS
    'US-261/CA1 — Référence en base de la cible (id de l''événement, de la parcelle…) quand '
    'l''exécuteur la connaît ; sinon cible_nom.';
COMMENT ON COLUMN actions_menees.avant IS
    'US-261/CA1 — Valeurs avant l''action (NULL pour une création).';
COMMENT ON COLUMN actions_menees.apres IS
    'US-261/CA1 — Valeurs après l''action (NULL pour une suppression).';
COMMENT ON COLUMN actions_menees.statut IS
    'US-261/CA1 — reussie | echouee. Seules les réussies sont transmises à l''agent.';

ALTER TABLE actions_menees ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_actions_menees ON actions_menees;
CREATE POLICY tenant_isolation_actions_menees ON actions_menees
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

-- ── 2. Où une proposition a été traitée ──────────────────────────────────────
ALTER TABLE propositions
    ADD COLUMN IF NOT EXISTS traite_canal VARCHAR(16);

COMMENT ON COLUMN propositions.traite_canal IS
    'US-260/CA5 — telegram | pwa : le canal qui a fait sortir la proposition de l''attente. '
    'NULL pour une proposition traitée avant cette colonne.';

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'actions_menees';
SELECT polname FROM pg_policy WHERE polname = 'tenant_isolation_actions_menees';
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'propositions' AND column_name = 'traite_canal';
