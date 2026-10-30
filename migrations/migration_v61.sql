-- =============================================================================
-- migration_v61.sql — Conversation et propositions en base, communes aux canaux (US-259)
-- =============================================================================
-- Le compagnon se souvient de ce qu'on vient de se dire et de ce qu'il a
-- proposé, même après un redémarrage du bot et quel que soit le canal.
-- Jusqu'ici, les propositions vivaient en mémoire du processus (`_INTERP_PENDING`
-- du bot, `_sessions` de l'API, échanges du contexte court d'US-238), et la file
-- d'US-224 (`gestes_intentions`) était un second magasin d'attente. Deux magasins
-- auraient fait deux moteurs : deux règles d'expiration, deux relances.
--
-- 1. **Une seule table de propositions.** `gestes_intentions` est RENOMMÉE en
--    `propositions` : chaque geste en attente reste la même ligne — même `id`,
--    même `code`, donc même lien `?start=` déjà envoyé, même `expire_le`, même
--    relance. C'est la migration des gestes en attente (CA6), sans copie.
--    `nature` distingue le geste préparé (`geste`, toutes les lignes existantes)
--    de la commande et du plan proposés en conversation (`commande`, `plan`).
--    `geste` devient `contenu` : la colonne porte désormais aussi une commande.
--
-- 2. **Les états prennent la forme d'une proposition** (CA2) : en_attente,
--    confirmee, abandonnee, perimee, remplacee. Reprise des trois états sortis
--    d'US-224 (confirme, abandonne, perime) entre les marqueurs REPRISE,
--    exécutés tels quels par tests/test_us259_conversation_propositions.py.
--
-- 3. **Durée de vie** (CA5) : 30 min pour une proposition de conversation, la
--    durée de la file (3 jours) pour une proposition NOTIFIÉE. Les gestes de la
--    file sont notifiés (relances) : `notifiee = TRUE` à la reprise.
--
-- 4. **`echanges_conversation`** (CA1) : les échanges récents, par jardinier et
--    par potager, lus sur 30 minutes glissantes, purgés à 30 jours.
--
-- ⚠️ RLS (CA9).
--    * `propositions` garde la policy de migration_v50, renommée : tolérante au
--      GUC non armé en LECTURE (le bot retrouve une proposition par son code
--      avant de savoir de quel potager elle relève), stricte en ÉCRITURE — le
--      bot arme le potager DE LA PROPOSITION avant de la mettre à jour.
--    * `echanges_conversation` est stricte en lecture comme en écriture : un
--      échange s'écrit et se lit dans le potager où il a eu lieu.
--
-- À exécuter avec le rôle propriétaire de la base. Droits de app_user : couverts
-- par les DEFAULT PRIVILEGES de migration_v18.
-- Idempotent. Rollback : migrations/rollback_v61.sql
-- =============================================================================

BEGIN;

-- ── 1. gestes_intentions → propositions ──────────────────────────────────────
-- ⚠️ Une table `propositions` VIDE peut exister avant cette migration : l'API et
-- le bot exécutent `Base.metadata.create_all` à leur démarrage, et un service
-- relancé sur le nouveau modèle l'a créée (ainsi qu'`echanges_conversation`).
-- Vide, elle est supprimée pour laisser place au renommage ; non vide, la
-- migration s'arrête plutôt que de perdre ce qu'elle contient.
DO $$
BEGIN
    IF to_regclass('public.gestes_intentions') IS NOT NULL
       AND to_regclass('public.propositions') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM propositions) THEN
            RAISE EXCEPTION 'gestes_intentions et propositions existent toutes deux, et propositions '
                            'n''est pas vide : fusion manuelle requise avant migration_v61';
        END IF;
        -- CASCADE retire la clé étrangère d'echanges_conversation, remise au §4.
        DROP TABLE propositions CASCADE;
    END IF;
    IF to_regclass('public.gestes_intentions') IS NOT NULL
       AND to_regclass('public.propositions') IS NULL THEN
        ALTER TABLE gestes_intentions RENAME TO propositions;
        ALTER SEQUENCE IF EXISTS gestes_intentions_id_seq RENAME TO propositions_id_seq;
        ALTER INDEX IF EXISTS ix_gestes_intentions_expire_le  RENAME TO ix_propositions_expire_le;
        ALTER INDEX IF EXISTS ix_gestes_intentions_potager_id RENAME TO ix_propositions_potager_id;
        ALTER INDEX IF EXISTS ix_gestes_intentions_user_etat  RENAME TO ix_propositions_user_etat;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'propositions' AND column_name = 'geste'
    ) THEN
        ALTER TABLE propositions RENAME COLUMN geste TO contenu;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polname = 'tenant_isolation_gestes_intentions'
          AND polrelid = to_regclass('public.propositions')
    ) THEN
        ALTER POLICY tenant_isolation_gestes_intentions ON propositions
            RENAME TO tenant_isolation_propositions;
    END IF;
END $$;

ALTER TABLE propositions
    ADD COLUMN IF NOT EXISTS nature           VARCHAR(16) NOT NULL DEFAULT 'geste',
    ADD COLUMN IF NOT EXISTS canal            VARCHAR(16),
    ADD COLUMN IF NOT EXISTS notifiee         BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS remplacee_par_id INTEGER REFERENCES propositions(id) ON DELETE SET NULL;

-- ── 2, 3. Reprise des gestes de la file d'US-224 ─────────────────────────────
-- Un geste en attente reste en attente, avec son code et son expiration : sa
-- relance part comme avant. Seuls les états SORTIS changent de forme.
-- -- REPRISE:DEBUT --
UPDATE propositions SET etat = 'confirmee'  WHERE etat = 'confirme';
UPDATE propositions SET etat = 'abandonnee' WHERE etat = 'abandonne';
UPDATE propositions SET etat = 'perimee'    WHERE etat = 'perime';
UPDATE propositions
   SET notifiee = TRUE,
       canal = COALESCE(canal, 'pwa')
 WHERE nature = 'geste'
   AND notifiee = FALSE;
-- -- REPRISE:FIN --

ALTER TABLE propositions DROP CONSTRAINT IF EXISTS ck_propositions_nature;
ALTER TABLE propositions
    ADD CONSTRAINT ck_propositions_nature
    CHECK (nature IN ('geste', 'commande', 'plan'));

ALTER TABLE propositions DROP CONSTRAINT IF EXISTS ck_propositions_etat;
ALTER TABLE propositions
    ADD CONSTRAINT ck_propositions_etat
    CHECK (etat IN ('en_attente', 'confirmee', 'abandonnee', 'perimee', 'remplacee'));

-- La proposition en cours d'un jardinier dans un potager : la lecture de chaque phrase.
CREATE INDEX IF NOT EXISTS ix_propositions_conversation
    ON propositions (user_id, potager_id, nature, etat);

COMMENT ON TABLE propositions IS
    'US-259 — Une chose proposée au jardinier, en attente de sa réponse, commune aux canaux. '
    'nature = geste : un geste préparé par la PWA (la file d''US-224) ; commande | plan : '
    'proposé en conversation. Rien ici n''est un événement : seule la confirmation écrit.';
COMMENT ON COLUMN propositions.nature IS
    'US-259 — geste | commande | plan. Le geste en file n''est qu''une nature parmi d''autres.';
COMMENT ON COLUMN propositions.contenu IS
    'US-224/US-259 — Pour un geste : l''item pré-parsé (contrat de llm.parseur_deterministe). '
    'Pour une commande ou un plan : la proposition sérialisée, rejouable après un redémarrage.';
COMMENT ON COLUMN propositions.etat IS
    'US-259/CA2 — en_attente | confirmee | abandonnee | perimee | remplacee. La sortie de '
    'l''attente est ATOMIQUE (UPDATE … WHERE etat = ''en_attente'') : deux confirmations '
    'simultanées n''exécutent qu''une fois.';
COMMENT ON COLUMN propositions.notifiee IS
    'US-259/CA5 — Une proposition notifiée vit la durée de la file d''US-224 (3 jours, '
    'avertissement avant purge) ; une proposition restée dans la conversation, 30 min.';
COMMENT ON COLUMN propositions.remplacee_par_id IS
    'US-259 — « non, 4 rangs » : la nouvelle proposition qui a remplacé celle-ci.';

-- ── 4. Les échanges de la conversation ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS echanges_conversation (
    id              SERIAL      PRIMARY KEY,
    user_id         INTEGER     NOT NULL REFERENCES users(id),
    potager_id      INTEGER     NOT NULL REFERENCES potagers(id),
    canal           VARCHAR(16) NOT NULL,
    texte_jardinier TEXT        NOT NULL DEFAULT '',
    texte_compagnon TEXT        NOT NULL DEFAULT '',
    outils          JSONB,
    proposition_id  INTEGER     REFERENCES propositions(id) ON DELETE SET NULL,
    signal          VARCHAR(64),
    cree_le         TIMESTAMP   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_echanges_conversation_fil
    ON echanges_conversation (user_id, potager_id, cree_le);

-- Une table créée avant la migration par `create_all` (voir §1) a perdu sa clé
-- étrangère vers `propositions` au DROP … CASCADE : elle est remise. Ses
-- `proposition_id` sont tous NULL — la table supprimée était vide.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'echanges_conversation'::regclass
          AND confrelid = 'propositions'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE echanges_conversation
            ADD CONSTRAINT echanges_conversation_proposition_id_fkey
            FOREIGN KEY (proposition_id) REFERENCES propositions(id) ON DELETE SET NULL;
    END IF;
END $$;

COMMENT ON TABLE echanges_conversation IS
    'US-259/CA1 — Mémoire courte du compagnon, commune à Telegram et à la PWA : les 10 '
    'derniers échanges par jardinier et par potager, lus sur 30 minutes glissantes, purgés '
    'à 30 jours. Les résultats des lectures n''y sont pas, seul le texte du compagnon.';
COMMENT ON COLUMN echanges_conversation.signal IS
    'US-259/CA1 — Signal d''origine d''un message spontané (veilleur) ; NULL pour une phrase.';

ALTER TABLE echanges_conversation ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_echanges_conversation ON echanges_conversation;
CREATE POLICY tenant_isolation_echanges_conversation ON echanges_conversation
    USING      (potager_id = current_setting('app.potager_id')::int)
    WITH CHECK (potager_id = current_setting('app.potager_id')::int);

COMMIT;

-- Vérification post-migration
SELECT relname, relrowsecurity FROM pg_class
 WHERE relname IN ('propositions', 'echanges_conversation');
SELECT polname FROM pg_policy
 WHERE polname IN ('tenant_isolation_propositions', 'tenant_isolation_echanges_conversation');
SELECT nature, etat, count(*) FROM propositions GROUP BY nature, etat ORDER BY 1, 2;
