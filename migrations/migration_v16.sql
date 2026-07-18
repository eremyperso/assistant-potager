-- =============================================================================
-- migration_v16.sql — Socle multi-tenant (users / potagers / potager_membres)
-- =============================================================================
-- [US-040] Crée le socle de données du tenant "potager" et rattache toutes les
-- données existantes au potager #1, sans changer le comportement actuel du
-- bot ni de la PWA. potager_id reste NULLABLE sur les tables métier à ce
-- stade — le passage NOT NULL est réservé à une US ultérieure de scoping
-- applicatif (isolation inter-potagers).
--
-- Tables métier concernées (inventaire via information_schema.tables,
-- schema 'public', hors tables système/techniques) :
--   - evenements      → potager_id ajouté (backfill = 1)
--   - parcelles       → potager_id ajouté (backfill = 1)
--   - culture_config  → potager_id ajouté, NULLABLE en permanence
--                       (NULL = fiche référentiel globale partagée entre
--                       potagers ; non NULL = fiche personnalisée à un
--                       potager). Le backfill NE force PAS potager_id=1 ici :
--                       les fiches existantes restent des fiches globales.
--
-- Idempotent : IF NOT EXISTS / WHERE potager_id IS NULL, safe à rejouer.
--
-- Exécution — TOUJOURS passer les 3 variables -v explicitement (évite toute
-- ambiguïté liée aux variables psql non définies) :
--
--   psql -U potager_user -d potager_dev -h localhost \
--        -v chat_id_actuel=123456789 \
--        -v lat_actuelle=48.96082453509178 \
--        -v lon_actuelle=2.2038296967715305 \
--        -f migrations/migration_v16.sql
--
-- Si tu ne connais pas encore le chat_id Telegram, passe une chaîne vide
-- (le champ restera NULL, à renseigner plus tard) :
--   -v chat_id_actuel=''
--
-- Rollback : migrations/rollback_v16.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- [1] Table users
CREATE TABLE IF NOT EXISTS users (
    id                SERIAL PRIMARY KEY,
    email             VARCHAR(255) UNIQUE,
    telegram_chat_id  BIGINT UNIQUE,
    nom               VARCHAR(100),
    cree_le           TIMESTAMP DEFAULT now()
);

-- [2] Table potagers
CREATE TABLE IF NOT EXISTS potagers (
    id                SERIAL PRIMARY KEY,
    nom               VARCHAR(100) NOT NULL,
    latitude          FLOAT,
    longitude         FLOAT,
    proprietaire_id   INTEGER NOT NULL REFERENCES users(id),
    plan              VARCHAR(20) DEFAULT 'free',
    cree_le           TIMESTAMP DEFAULT now()
);

-- [3] Table potager_membres
CREATE TABLE IF NOT EXISTS potager_membres (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    potager_id  INTEGER NOT NULL REFERENCES potagers(id),
    role        VARCHAR(10) NOT NULL CHECK (role IN ('owner', 'editor', 'lecteur')),
    PRIMARY KEY (user_id, potager_id)
);

-- [4] Colonne potager_id sur les tables métier — NULLABLE à ce stade
ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS potager_id INTEGER REFERENCES potagers(id);

ALTER TABLE parcelles
    ADD COLUMN IF NOT EXISTS potager_id INTEGER REFERENCES potagers(id);

ALTER TABLE culture_config
    ADD COLUMN IF NOT EXISTS potager_id INTEGER REFERENCES potagers(id);

-- [5] Backfill — user #1, potager #1, lien owner
--     N'insère que si le user #1 n'existe pas déjà (idempotence)
--     NULLIF(...,'')  → une variable -v passée vide (ou absente, psql la
--     substitue alors par une chaîne vide) retombe sur NULL / la valeur
--     par défaut, sans jamais casser la syntaxe SQL.
INSERT INTO users (id, email, telegram_chat_id, nom)
SELECT 1, NULL, NULLIF(:'chat_id_actuel', '')::BIGINT, 'Emmanuel'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 1);

-- Recale la séquence si l'INSERT ci-dessus a forcé l'id=1
SELECT setval(pg_get_serial_sequence('users', 'id'), GREATEST((SELECT MAX(id) FROM users), 1));

INSERT INTO potagers (id, nom, latitude, longitude, proprietaire_id, plan)
SELECT 1, 'Potager principal',
       COALESCE(NULLIF(:'lat_actuelle', '')::FLOAT, 48.96082453509178),
       COALESCE(NULLIF(:'lon_actuelle', '')::FLOAT, 2.2038296967715305),
       1, 'free'
WHERE NOT EXISTS (SELECT 1 FROM potagers WHERE id = 1);

SELECT setval(pg_get_serial_sequence('potagers', 'id'), GREATEST((SELECT MAX(id) FROM potagers), 1));

INSERT INTO potager_membres (user_id, potager_id, role)
SELECT 1, 1, 'owner'
WHERE NOT EXISTS (SELECT 1 FROM potager_membres WHERE user_id = 1 AND potager_id = 1);

-- [6] Backfill des tables métier vers le potager #1
UPDATE evenements SET potager_id = 1 WHERE potager_id IS NULL;
UPDATE parcelles  SET potager_id = 1 WHERE potager_id IS NULL;
-- culture_config reste NULL par défaut (fiche globale partagée) — décision
-- documentée en tête de fichier, pas de backfill forcé ici.

-- [7] Index
CREATE INDEX IF NOT EXISTS idx_evenements_potager_date ON evenements (potager_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_parcelles_potager        ON parcelles (potager_id);
CREATE INDEX IF NOT EXISTS idx_culture_config_potager   ON culture_config (potager_id);

COMMIT;

-- [8] Vérification post-migration
SELECT 'evenements sans potager_id' AS verification, count(*) FROM evenements WHERE potager_id IS NULL
UNION ALL
SELECT 'parcelles sans potager_id', count(*) FROM parcelles WHERE potager_id IS NULL;
