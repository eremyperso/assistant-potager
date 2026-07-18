# US-100 : Modèle multi-tenant (users / potagers / membres)

**Titre :** Créer le socle de données multi-tenant avec backfill des données existantes vers le potager #1

**Story :**
En tant qu'administrateur de la plateforme
Je veux que chaque donnée métier soit rattachée à un potager (le tenant) via un modèle users / potagers / potager_membres
Afin de préparer l'isolation des données entre jardins sans casser l'installation actuelle

---

**Critères d'acceptance :**

- [ ] CA1 : Une table `users` existe avec les colonnes `id SERIAL PK`, `email VARCHAR(255) UNIQUE NULL`, `telegram_chat_id BIGINT UNIQUE NULL`, `nom VARCHAR(100)`, `cree_le TIMESTAMP DEFAULT now()`
- [ ] CA2 : Une table `potagers` existe avec `id SERIAL PK`, `nom VARCHAR(100) NOT NULL`, `latitude FLOAT`, `longitude FLOAT`, `proprietaire_id INTEGER NOT NULL REFERENCES users(id)`, `plan VARCHAR(20) DEFAULT 'free'`, `cree_le TIMESTAMP DEFAULT now()`
- [ ] CA3 : Une table `potager_membres` existe avec `user_id INTEGER REFERENCES users(id)`, `potager_id INTEGER REFERENCES potagers(id)`, `role VARCHAR(10) NOT NULL CHECK (role IN ('owner','editor','lecteur'))`, `PRIMARY KEY (user_id, potager_id)`
- [ ] CA4 : Toutes les tables métier (`evenements`, `culture_config`, et toute autre table métier détectée via `information_schema.tables`) portent une colonne `potager_id INTEGER NULL REFERENCES potagers(id)` — **nullable à ce stade** (le passage NOT NULL est réservé à US-102)
- [ ] CA5 : Le backfill crée le user #1 (nom "Emmanuel", `telegram_chat_id` = valeur du chat_id actuel lue depuis une variable de migration), le potager #1 (nom "Potager principal", latitude/longitude actuelles du job météo), le lien membre (user #1, potager #1, 'owner'), puis met à jour **100 % des lignes** de toutes les tables métier avec `potager_id = 1`
- [ ] CA6 : Un index composite `(potager_id, date DESC)` existe sur `evenements` ; un index `(potager_id)` existe sur chaque autre table métier
- [ ] CA7 : Les modèles SQLAlchemy (`database/models.py`) sont mis à jour : classes `User`, `Potager`, `PotagerMembre` + attribut `potager_id` sur `Evenement` (et autres modèles) — **sans modifier aucune requête existante** dans `bot.py` / `main.py`
- [ ] CA8 : La migration est idempotente (`IF NOT EXISTS` / `WHERE potager_id IS NULL`) : la rejouer deux fois ne produit ni erreur ni doublon
- [ ] CA9 : Un script de rollback `migrations/rollback_v6.sql` supprime colonnes, index et tables dans l'ordre inverse des dépendances FK
- [ ] CA10 : Après migration, le bot et la PWA fonctionnent **strictement à l'identique** : les 12 actions canoniques, les flux `corr_*`, le mode `ask`, `/stats`, `/plan` passent les tests de non-régression sans modification de comportement

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : base de données + modèles (aucun changement d'interaction Telegram ni PWA)
- Migration BDD requise : **oui** — `migrations/migration_v6.sql` ⚠️ vérifier la dernière version existante dans `migrations/` avant création (v5 = culture_config / US-001)
- Dépendances : aucune (première US de l'épic multi-tenant ; US-101, US-102, US-103 en dépendent)
- Zéro token Groq : aucune modification des appels LLM
- Invariants projet : SQLAlchemy 2.0 (`db.get()`), migration en fichier séparé exécutable via `psql`, pas d'`ALTER TABLE` inline dans le code Python, `PATCH_NOTES.md` à mettre à jour

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `migrations/migration_v6.sql` (nouveau), `migrations/rollback_v6.sql` (nouveau), `database/models.py`
- Le `telegram_chat_id` et les coordonnées du potager #1 sont fournis en tête de migration sous forme de variables psql (`\set chat_id ...`) ou d'un bloc `DO $$` documenté — pas de valeur en dur non commentée
- Inventaire des tables métier : lister via `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` et documenter dans la migration la liste exacte des tables modifiées (commentaire SQL) pour audit ultérieur par US-102
- Ne PAS ajouter `potager_id` aux tables système/référentiel pur si non pertinent — décision à documenter table par table (ex. `culture_config` : si le référentiel devient personnalisable par potager, il prend `potager_id` nullable où NULL = fiche globale partagée ; c'est l'option retenue)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Socle de données multi-tenant

  Scenario: Migration v6 appliquée sur la base de production existante
    Given une base de données en version v5 contenant des événements existants
    When la migration migration_v6.sql est exécutée via psql
    Then les tables users, potagers et potager_membres existent
    And la colonne potager_id existe sur evenements et culture_config
    And aucune donnée existante n'est perdue

  Scenario: Backfill complet vers le potager #1
    Given la migration v6 est appliquée
    When le bloc de backfill s'exécute
    Then le user #1 existe avec le telegram_chat_id actuel
    And le potager #1 existe avec les coordonnées météo actuelles
    And potager_membres contient (user #1, potager #1, 'owner')
    And SELECT count(*) FROM evenements WHERE potager_id IS NULL retourne 0

  Scenario: Idempotence de la migration
    Given la migration v6 a déjà été appliquée avec succès
    When migration_v6.sql est rejouée
    Then aucune erreur n'est levée
    And aucun user, potager ou membre en doublon n'est créé

  Scenario: Non-régression du bot après migration
    Given la migration v6 est appliquée et le bot redémarré
    When le jardinier dicte "j'ai récolté 2 kg de tomates"
    Then l'événement est enregistré comme avant la migration
    And les commandes /stats, /plan et le mode ask répondent à l'identique

  Scenario: Rollback
    Given la migration v6 est appliquée
    When rollback_v6.sql est exécuté
    Then les colonnes potager_id, les index et les tables users, potagers, potager_membres sont supprimés
    And la base est fonctionnellement identique à la version v5
```

**Labels GitHub :** `us`, `sprint-1`, `database`, `multi-tenant`, `fondation`
