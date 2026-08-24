-- =============================================================================
-- migration_v30.sql — Identité fédérée Google (OpenID Connect) (US-090)
-- =============================================================================
-- Ajoute sur `users` une unique colonne :
--   * google_sub : claim `sub` de l'id_token Google — identifiant opaque et
--                  stable du compte Google, UNIQUE (CA14). Jamais l'e-mail :
--                  celui-ci peut changer côté Google, `sub` non.
--
-- Aucune autre colonne n'est nécessaire : `users.mot_de_passe_hash` est déjà
-- nullable (US-044) et `users.email` déjà nullable + unique (US-040) — un
-- compte créé via Google, sans mot de passe, tient dans le schéma existant.
--
-- Volontairement PAS de colonne `auth_provider` (CA15) : un compte peut cumuler
-- plusieurs méthodes de connexion (mot de passe + Google + Telegram) et le
-- fournisseur utilisé est une propriété de l'événement de connexion, journalisé,
-- pas une propriété de l'utilisateur.
--
-- Purement additive : aucun compte existant n'est modifié, google_sub reste NULL
-- partout tant qu'aucune fédération n'a eu lieu.
--
-- Idempotent : IF NOT EXISTS sur la colonne et sur l'index unique.
-- Rollback : migrations/rollback_v30.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- [CA11, CA12] Identifiant Google du compte — NULL pour tout compte non fédéré.
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255) NULL;

-- [CA14] Unicité : un compte Google ne peut être rattaché qu'à un seul
-- utilisateur. Index unique plutôt que contrainte UNIQUE pour rester idempotent
-- via IF NOT EXISTS ; PostgreSQL n'indexe pas les NULL entre eux, les comptes
-- non fédérés ne se gênent donc pas.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users (google_sub);

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'google_sub';

SELECT COUNT(*) AS nb_comptes_federes_google FROM users WHERE google_sub IS NOT NULL;
