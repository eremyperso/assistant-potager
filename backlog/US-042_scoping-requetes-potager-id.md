**ID :** US-042
**Titre :** Scoper systématiquement les requêtes par `potager_id` (et refondre `_ask_question`)
**Épic :** ÉPIC 1 — Socle multi-tenant

**Story :**
En tant qu'administrateur de la plateforme
Je veux que toute lecture et écriture de données métier soit filtrée par le `potager_id` du contexte courant
Afin qu'aucune donnée d'un potager ne puisse jamais apparaître dans les réponses adressées à un membre d'un autre potager

**Contexte fonctionnel :**
`_ask_question()` charge aujourd'hui tout l'historique d'événements sans filtre (~5 000 tokens par appel) : c'est à la fois une fuite potentielle inter-potagers dès qu'il y aura plusieurs jardins, et une source de surcoût Groq. Limiter le nombre de lignes envoyées ne suffit pas : il faut filtrer par potager *avant* de limiter. Cette US s'appuie sur la couche `app/services/` livrée par US-041 : chaque fonction de service y ajoute un filtre `potager_id = ctx.potager_id` sur ses requêtes, et la colonne `potager_id` passe de nullable à `NOT NULL` sur les tables métier une fois le backfill de US-040 confirmé complet.

**Critères d'acceptance :**
- [ ] CA1 : Toutes les fonctions de `app/services/evenements.py` (lecture, écriture, correction, suppression) filtrent par `ctx.potager_id`
- [ ] CA2 : Toutes les fonctions de `app/services/stats.py`, `app/services/stock.py`, `app/services/plan.py` filtrent par `ctx.potager_id`
- [ ] CA3 : `services/questions.repondre_question()` (ex-`_ask_question`) est refondue : filtre par `ctx.potager_id`, applique une fenêtre temporelle par défaut de 12 mois, limite à 100 événements maximum, et sérialise le contexte envoyé au LLM de façon compacte
- [ ] CA4 : La colonne `potager_id` devient `NOT NULL` sur `evenements`, `culture_config` (et toute autre table métier concernée par US-040) via `migration_v17.sql` — appliquée uniquement après vérification que `SELECT count(*) FROM <table> WHERE potager_id IS NULL` = 0 sur chaque table
- [ ] CA5 : Un test automatisé d'isolation existe : étant donné deux potagers A et B avec des événements distincts, une requête de stats/historique/question effectuée avec le contexte du potager A ne retourne strictement aucune donnée du potager B
- [ ] CA6 : Zéro requête non scopée ne subsiste dans le code applicatif de `app/services/` — audit explicite documenté (recherche de tout `db.query()`/`select()` sur une table métier sans clause `potager_id`)
- [ ] CA7 : Le nombre de tokens consommés par un appel à `repondre_question()` est mesuré avant/après et loggé ; la cible est un passage de ~5 000 à moins de 1 500 tokens/appel
- [ ] CA8 : Les requêtes SQL brutes éventuelles (ex. dans `utils/stats.py` ou équivalent si elles existent hors ORM) sont auditées une par une et scopées si elles touchent une table métier

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement | analyse | consultation
- Migration BDD requise : **oui** — `migration_v17.sql` (⚠️ vérifier au moment de l'implémentation le numéro de la dernière migration existante, susceptible d'avoir avancé)
- Dépendances : US-040 (socle tenant), US-041 (couche services)
- Impact tokens : cible chiffrée dans CA7 — à mesurer et loguer explicitement, pas seulement estimer
- Invariants projet : `db.get()` jamais `db.query().get()` ; prompts Groq en `.replace()` jamais `.format()` ; ordre critique des flux (`corr_*` > `ask` > NAV > question > action) préservé

**Notes techniques (pour Persona Developer) :**
- Composants impactés : tous les modules de `app/services/` (ajout du filtre `potager_id`), `migrations/migration_v17.sql` (nouveau, passage `NOT NULL`), script de rollback associé, `tests/test_isolation_potager.py` (nouveau, test d'isolation obligatoire)
- Le passage `NOT NULL` est bloquant : la migration doit échouer explicitement (et documenter comment) si une ligne `potager_id IS NULL` subsiste, plutôt que de silencieusement ignorer le cas
- La refonte de `_ask_question` doit conserver le comportement fonctionnel perçu par l'utilisateur (mêmes types de questions répondues correctement) — seul le contexte envoyé au LLM change de volume et de scoping
- Prévoir un jeu de tests de non-régression sur un corpus de questions réelles pour vérifier que la réduction de contexte ne dégrade pas la qualité des réponses

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Isolation des statistiques entre deux potagers
  Given deux potagers A et B possédant chacun des événements distincts
  When un membre du potager A demande ses statistiques
  Then seuls les événements du potager A apparaissent dans le résultat
  And aucun événement du potager B n'apparaît

Scénario: Isolation du mode ask entre deux potagers
  Given deux potagers A et B possédant chacun des événements distincts
  When un membre du potager A pose une question analytique via /ask
  Then la réponse ne contient aucune donnée issue du potager B

Scénario: Fenêtre temporelle et limite du mode ask
  Given un potager avec plus de 100 événements sur les 24 derniers mois
  When repondre_question(ctx, question) est appelée
  Then au maximum 100 événements des 12 derniers mois sont utilisés comme contexte
  And le nombre de tokens consommés est inférieur à 1500

Scénario: Colonne potager_id NOT NULL après backfill vérifié
  Given le backfill de US-040 est confirmé complet (aucune ligne potager_id NULL)
  When migration_v17.sql est exécutée
  Then la colonne potager_id devient NOT NULL sur evenements et culture_config
  And aucune donnée existante n'est perdue

Scénario: Rollback du passage NOT NULL
  Given migration_v17.sql est appliquée
  When le script de rollback est exécuté
  Then la colonne potager_id redevient nullable sur les tables concernées
  And la base est fonctionnellement identique à la version précédente
```

**Labels GitHub :** `us`, `sprint-multi-tenant`, `database`, `security`, `multi-tenant`, `fondation`
