-- =============================================================================
-- migration_v51.sql — La file de gestes en attente (US-224)
-- =============================================================================
-- US-196 avait posé le bon principe — la PWA prépare, le compagnon confirme,
-- rien n'est écrit avant « Confirmer » — avec un véhicule qui ne tient pas à
-- l'usage : un laissez-passer à usage unique, valable quinze minutes. Trois
-- façons de perdre un geste préparé, aucune de le rejouer.
--
-- Cette migration transforme ce laissez-passer en FILE D'ATTENTE. Ce que la
-- PWA dépose y reste jusqu'à confirmation ou abandon explicite ; le compagnon
-- invite à la traiter ; le jardinier la reprend quand il veut.
--
-- Trois changements, et rien d'autre :
--
-- [CA3]  `etat` — en_attente | confirme | abandonne | perime. `consomme_le`
--        devient `traite_le` : ce n'est plus « ce lien a servi » (à
--        l'ouverture) mais « ce geste est sorti de la file » (à la
--        confirmation ou à l'abandon). Le renommage est délibéré : garder
--        l'ancien nom aurait laissé cohabiter deux sémantiques opposées sous
--        la même colonne, exactement ce qui a rendu US-196 fausse à l'usage.
--        `expire_le` ne change pas de forme, seulement de valeur : le code
--        l'écrit désormais à trois jours du dépôt, PAR GESTE — la péremption
--        ne se compte jamais par pile (un geste déposé le troisième jour n'est
--        pas emporté par la purge de ceux du premier).
--
-- [CA12] `motif_refus` — un geste dont le contexte a disparu entre le dépôt et
--        la confirmation (parcelle supprimée, potager quitté, rôle devenu
--        lecteur) est refusé EN CLAIR et retiré de la file. Le motif est écrit
--        ici pour que l'application puisse le redire, et pour qu'un refus
--        récurrent se retrouve sans relire les journaux du bot.
--
-- [CA17] `avertissement_le` — l'avertissement « ce geste sera vidé dans quatre
--        heures » part UNE FOIS par geste. Par geste, et non par compte :
--        deux gestes déposés à deux jours d'écart ont deux échéances.
--
-- [CA14, CA15, CA19, CA20] `files_gestes_reglages` — tout ce qui relève de la
--        RELANCE, qui n'appartient à aucun geste en particulier : le réglage
--        de coupure, la trace de la dernière invitation, celle de la dernière
--        relance, et l'identifiant du message à remplacer plutôt qu'à empiler.
--        Une ligne par compte, créée à la demande.
--
-- ⚠️ RLS — inchangée sur `gestes_intentions`, et c'est un choix. La policy de
--    v50 tolère le GUC non armé en LECTURE (le bot cherche un geste avant de
--    savoir de quel potager il relève) mais l'exige en ÉCRITURE. US-224 fait du
--    bot un écrivain sur cette table : il arme donc `app.potager_id` sur le
--    potager DU GESTE avant chaque mise à jour (`file_gestes._ecriture`), ce
--    qui garde la policy stricte là où elle protège. Relâcher le WITH CHECK
--    aurait été plus court et aurait ouvert l'écriture croisée entre potagers.
--
--    `files_gestes_reglages` n'a PAS de RLS : elle ne porte aucune donnée de
--    potager. Même traitement que `liaisons_telegram` (US-045), pour la même
--    raison — c'est une table de compte, pas une table de jardin.
--
-- À exécuter avec le rôle propriétaire de la base.
-- Idempotent : chaque ajout est gardé.
-- Rollback : migrations/rollback_v51.sql
-- =============================================================================

BEGIN;

-- ── [CA3] L'état d'un geste ─────────────────────────────────────────────────
ALTER TABLE gestes_intentions
    ADD COLUMN IF NOT EXISTS etat VARCHAR(16) NOT NULL DEFAULT 'en_attente';

-- [CA12] Le motif du refus, quand il y en a un.
ALTER TABLE gestes_intentions
    ADD COLUMN IF NOT EXISTS motif_refus VARCHAR(200);

-- [CA17] L'avertissement avant purge, une fois par geste.
ALTER TABLE gestes_intentions
    ADD COLUMN IF NOT EXISTS avertissement_le TIMESTAMP;

-- `consomme_le` → `traite_le` : la colonne ne dit plus la même chose.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'gestes_intentions' AND column_name = 'consomme_le'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'gestes_intentions' AND column_name = 'traite_le'
    ) THEN
        ALTER TABLE gestes_intentions RENAME COLUMN consomme_le TO traite_le;
    END IF;
END $$;

ALTER TABLE gestes_intentions
    ADD COLUMN IF NOT EXISTS traite_le TIMESTAMP;

-- Reprise des lignes d'US-196 encore présentes : un lien déjà ouvert n'est pas
-- un geste confirmé — personne ne peut dire s'il l'a été. Elles sont marquées
-- « abandonne », le seul état qui ne promette rien de faux, et leur motif le
-- dit. Les lignes jamais ouvertes restent « en_attente » et hériteront de la
-- durée de vie de trois jours à leur prochaine lecture.
UPDATE gestes_intentions
   SET etat = 'abandonne',
       motif_refus = 'Lien à usage unique d''US-196, remplacé par la file (US-224)'
 WHERE traite_le IS NOT NULL
   AND etat = 'en_attente';

-- Le niveau 1 de la présentation liste la file d'un compte, tous potagers
-- confondus (CA5, CA13) ; la purge balaye par échéance (CA3).
CREATE INDEX IF NOT EXISTS ix_gestes_intentions_user_etat
    ON gestes_intentions (user_id, etat);

COMMENT ON COLUMN gestes_intentions.etat IS
    'US-224/CA3, CA8 — en_attente | confirme | abandonne | perime. Un geste n''est retiré '
    'de la file qu''à la CONFIRMATION ou à l''ABANDON EXPLICITE : « Plus tard », un délai '
    'de confirmation dépassé, une conversation refermée ou une relance ignorée le laissent '
    'en attente. C''est la différence de fond avec le `consomme_le` d''US-196, qui brûlait '
    'le geste dès l''ouverture du lien.';

COMMENT ON COLUMN gestes_intentions.traite_le IS
    'US-224/CA8 — Instant de SORTIE de la file (confirmation, abandon, refus, péremption), '
    'et non instant d''ouverture du lien. Une ligne sortie reste quelques heures pour que '
    'l''application puisse dire ce qu''elle est devenue (CA18), puis part à la purge.';

COMMENT ON COLUMN gestes_intentions.motif_refus IS
    'US-224/CA12 — Pourquoi ce geste n''a pas pu être joué : parcelle supprimée, lot '
    'inconnu, potager archivé ou quitté, rôle devenu lecteur. Jamais d''écriture '
    'silencieuse, jamais un geste fantôme qui échoue à chaque reprise.';

COMMENT ON COLUMN gestes_intentions.avertissement_le IS
    'US-224/CA17 — Instant de l''avertissement « ce geste sera vidé dans 4 heures », '
    'envoyé UNE FOIS par geste. Par geste, et non par pile : deux gestes déposés à deux '
    'jours d''écart ont deux échéances distinctes.';

COMMENT ON COLUMN gestes_intentions.expire_le IS
    'US-224/CA3 — Trois jours à compter du dépôt de CE geste. La péremption se compte par '
    'geste, jamais par pile : confirmer un geste ne prolonge jamais les autres, et un '
    'geste déposé le troisième jour n''est pas emporté par la purge de ceux du premier.';

-- ── [CA14, CA15, CA19, CA20] La relance, par compte ─────────────────────────
CREATE TABLE IF NOT EXISTS files_gestes_reglages (
    user_id                INTEGER   PRIMARY KEY REFERENCES users(id),
    relances_actives       BOOLEAN   NOT NULL DEFAULT TRUE,
    derniere_activite_le   TIMESTAMP,
    derniere_invitation_le TIMESTAMP,
    derniere_relance_le    TIMESTAMP,
    message_relance_id     INTEGER
);

COMMENT ON TABLE files_gestes_reglages IS
    'US-224/CA14, CA15, CA19, CA20 — Ce qui relève de la relance d''une file et n''appartient '
    'à aucun geste en particulier. Une ligne par compte, créée à la demande. Pas de RLS : '
    'aucune donnée de potager ici, même traitement que `liaisons_telegram` (US-045).';

COMMENT ON COLUMN files_gestes_reglages.relances_actives IS
    'US-224/CA20 — Couper les relances ne vide PAS la file : les gestes restent, les '
    'invitations cessent, l''avertissement du CA17 et la notification du CA18 aussi. '
    'Le réglage se dit et se défait depuis le compagnon ; c''est la soupape de l''US, '
    'elle ne doit jamais être difficile à trouver.';

COMMENT ON COLUMN files_gestes_reglages.derniere_activite_le IS
    'US-224/CA19 — Toute activité sur la file (confirmation, abandon, simple consultation) '
    'remet le compteur de relance à zéro. Elle ne rallonge JAMAIS la vie d''un geste : '
    'la péremption du CA3 court depuis le dépôt, et rien ne la repousse.';

COMMENT ON COLUMN files_gestes_reglages.derniere_invitation_le IS
    'US-224/CA14 — Une invitation part au premier dépôt sur une file vide, et une seule : '
    'les gestes déposés à la suite, pendant la même session de préparation, n''en '
    'déclenchent aucune autre.';

COMMENT ON COLUMN files_gestes_reglages.message_relance_id IS
    'US-224/CA20 — Le message de relance à REMPLACER, plutôt que d''empiler des bulles '
    'identiques dans la conversation. Remis à NULL dès qu''une édition échoue (message '
    'supprimé par le jardinier) : la relance suivante repart d''un envoi neuf.';

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type
  FROM information_schema.columns
 WHERE table_name = 'gestes_intentions'
   AND column_name IN ('etat', 'motif_refus', 'avertissement_le', 'traite_le')
 ORDER BY column_name;

SELECT etat, count(*) FROM gestes_intentions GROUP BY etat ORDER BY etat;

SELECT relname, relrowsecurity FROM pg_class
 WHERE relname IN ('gestes_intentions', 'files_gestes_reglages');
