**ID :** US-043
**Titre :** Activer le Row-Level Security PostgreSQL en défense en profondeur
**Épic :** ÉPIC 1 — Socle multi-tenant

**Story :**
En tant qu'administrateur de la plateforme
Je veux que la base de données elle-même interdise toute lecture ou écriture hors du potager courant, indépendamment du code applicatif
Afin qu'un bug dans la couche services (oubli d'un filtre `potager_id`) ne puisse jamais provoquer de fuite de données entre potagers

**Contexte fonctionnel :**
Le scoping applicatif livré par US-042 filtre correctement les requêtes tant que le code est juste — mais un seul oubli de filtre dans une fonction de service future suffirait à exposer les données d'un autre potager. Cette US ajoute une seconde ligne de défense au niveau PostgreSQL via Row-Level Security (RLS), indépendante du code applicatif : même une requête mal écrite ne pourra pas sortir du potager courant. Le rôle propriétaire des tables (superuser/owner) n'étant pas soumis aux policies RLS, un rôle applicatif non-superuser dédié (`app_user`) doit être créé pour que la protection soit effective.

**Critères d'acceptance :**
- [ ] CA1 : Un rôle PostgreSQL non-superuser `app_user` existe, propriétaire des connexions applicatives (bot + API), distinct du rôle admin utilisé pour les migrations/backups
- [ ] CA2 : `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` est appliqué sur `evenements`, `culture_config` et toute autre table métier portant `potager_id` (cf. inventaire documenté dans US-040)
- [ ] CA3 : Une policy RLS `USING (potager_id = current_setting('app.potager_id')::int)` existe sur chaque table métier concernée, appliquée en lecture et en écriture
- [ ] CA4 : `database/db.py` pose `SET LOCAL app.potager_id = :pid` à l'ouverture de chaque session applicative (context manager ou event SQLAlchemy `after_begin`), à partir du `TenantContext` en place depuis US-041/US-042
- [ ] CA5 : Si `app.potager_id` n'est pas défini au moment d'une requête sur une table protégée, l'application échoue de façon explicite (fail-fast avec message clair) plutôt que de renvoyer silencieusement zéro ligne
- [ ] CA6 : Un test automatisé dédié prouve qu'une requête volontairement non scopée (contournant sciemment le filtre applicatif) exécutée avec le rôle `app_user` retourne 0 ligne appartenant à un autre potager que celui du setting courant
- [ ] CA7 : Les opérations de migration et de sauvegarde, exécutées avec le rôle admin (propriétaire des tables), continuent de fonctionner sans policy RLS bloquante
- [ ] CA8 : Le comportement fonctionnel du bot et de la PWA reste strictement identique pour un potager donné (aucune régression perceptible par l'utilisateur)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : base de données + sécurité (aucun changement d'interaction Telegram ni PWA)
- Migration BDD requise : **oui** — `migration_v18.sql` (policies RLS + création du rôle `app_user`) (⚠️ vérifier le numéro de la dernière migration au moment de l'implémentation)
- Dépendances : US-040 (socle tenant), US-041 (couche services), US-042 (scoping applicatif + `potager_id NOT NULL`)
- Zéro impact tokens Groq
- Invariants projet : migration en fichier séparé idempotent avec rollback documenté ; pas d'`ALTER TABLE` inline dans le code Python

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `migrations/migration_v18.sql` (nouveau : création rôle `app_user`, `ENABLE ROW LEVEL SECURITY`, policies), script de rollback associé, `database/db.py` (pose du `SET LOCAL app.potager_id`), configuration de connexion (chaîne de connexion applicative doit utiliser `app_user` et non le rôle admin)
- Les jobs de fond (météo, sauvegardes — hors périmètre de cette US mais à anticiper) devront poser le setting `app.potager_id` pour chaque potager qu'ils traitent, un par un ; documenter ce point dans la migration à l'attention des US de jobs à venir
- Le fail-fast de CA5 est critique : sans lui, un oubli de `SET LOCAL` produirait un échec silencieux (0 ligne partout) difficile à diagnostiquer en production
- Vérifier que les connexions actuelles (bot.py, main.py) utilisent bien un pool de connexions compatible avec `SET LOCAL` (portée transaction, pas connexion) — à documenter si un changement de pattern de session est nécessaire

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Isolation garantie même sans filtre applicatif
  Given RLS est activé sur les tables métier avec le rôle app_user
  And le setting app.potager_id est positionné sur le potager A
  When une requête volontairement non filtrée par potager_id est exécutée
  Then seules les lignes du potager A sont retournées
  And aucune ligne du potager B n'apparaît

Scénario: Fail-fast en l'absence de setting
  Given RLS est activé sur les tables métier
  When une requête est exécutée sans que app.potager_id ait été positionné
  Then l'application lève une erreur explicite
  And aucune requête silencieuse à zéro résultat ne se produit

Scénario: Migrations et sauvegardes non bloquées par RLS
  Given RLS est activé avec le rôle admin propriétaire des tables
  When une migration ou un pg_dump est exécuté avec le rôle admin
  Then l'opération s'exécute normalement sans policy bloquante

Scénario: Non-régression fonctionnelle du bot
  Given RLS est activé et app.potager_id est positionné correctement par la session
  When le jardinier dicte "j'ai récolté 2 kg de tomates"
  Then l'événement est enregistré comme avant l'activation de RLS

Scénario: Rollback
  Given migration_v18.sql est appliquée
  When le script de rollback est exécuté
  Then les policies RLS sont supprimées, RLS est désactivé sur les tables
  And le rôle app_user est supprimé
  And la base est fonctionnellement identique à la version précédente
```

**Labels GitHub :** `us`, `sprint-multi-tenant`, `database`, `security`, `multi-tenant`, `fondation`
