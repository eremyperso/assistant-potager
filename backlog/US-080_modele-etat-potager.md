**ID :** US-080
**Titre :** Modéliser le cycle de vie d'un potager (actif / archivé / supprimé)
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant qu'administrateur de la plateforme
Je veux qu'un potager porte un état explicite (`actif`, `archivé`, `supprimé`) avec ses horodatages
Afin que l'archivage et la suppression d'un jardin deviennent possibles sans jamais perdre de données ni polluer les sélecteurs de potager

**Contexte fonctionnel :**
Première US de l'épic « Cycle de vie du potager » (`docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §5.1,
§6.1, §7.2 — proposée sous le numéro provisoire US-150 dans ce document, rédigée ici sous la
numérotation réelle du backlog).

Aujourd'hui un potager naît et ne meurt jamais : la table `potagers` (`database/models.py`, socle
US-040) n'a que `nom`, `ville`, `latitude`, `longitude`, `proprietaire_id`, `plan`, `cree_le`.
Aucune colonne ne permet de distinguer un jardin réellement cultivé d'un jardin abandonné, d'un
doublon créé par erreur ou d'un potager quitté après un déménagement. Conséquence : impossible de
livrer l'archivage (US-083), la suppression (US-084) ni le filtrage du sélecteur.

**Décision produit rappelée** (§2.3 du document de conception) : *un potager = un LIEU physique
persistant*. La saison n'est **pas** un tenant : elle reste un attribut temporel interne au potager
(cf. `docs/EPIC_CALENDRIER_CULTURAL.md`). L'état introduit ici décrit donc le cycle de vie du **lieu**,
jamais celui d'une campagne culturale.

Cette US est **purement structurelle** : aucun écran, aucune commande bot ne change. Elle pose le
socle consommé par US-081 à US-088.

**Critères d'acceptance :**
- [ ] CA1 : La table `potagers` porte trois nouvelles colonnes : `etat VARCHAR(20) NOT NULL DEFAULT 'actif'`
      avec contrainte `CHECK (etat IN ('actif','archive','supprime'))`, `archive_le TIMESTAMP NULL`,
      `supprime_le TIMESTAMP NULL` — valeurs d'état **sans accent** en base (les libellés accentués
      « archivé » / « supprimé » restent côté affichage uniquement)
- [ ] CA2 : Le backfill met **100 %** des potagers existants à `etat = 'actif'`, `archive_le` et
      `supprime_le` à `NULL` — aucun potager existant ne change de comportement
- [ ] CA3 : La migration est idempotente (`IF NOT EXISTS` / `WHERE etat IS NULL`) et un rollback
      `rollback_vXX.sql` supprime les trois colonnes et la contrainte
- [ ] CA4 : `lister_potagers_utilisateur()` (`app/services/potager_actif.py`) accepte un paramètre
      d'état dont la valeur par défaut est `'actif'` : sans demande explicite, un potager archivé ou
      supprimé **n'est jamais retourné**
- [ ] CA5 : `GET /potagers` accepte un paramètre de requête `etat=actif|archive|tous` (défaut `actif`)
      et expose l'état de chaque potager dans sa réponse, aux côtés du rôle et des compteurs existants (US-054)
- [ ] CA6 : `resoudre_tenant_context()` et `definir_potager_actif()` refusent un potager dont l'état
      n'est pas `actif` : un potager archivé ne peut pas devenir (ni rester) le potager actif — une
      exception dédiée est levée, distincte de `PotagerNonMembreError`
- [ ] CA7 : Un potager d'état `supprime` est traité comme inexistant par **toutes** les lectures, y
      compris avec `etat=tous` — il n'apparaît que pour le job de purge (US-084)
- [ ] CA8 : Non-régression complète : un utilisateur ayant un seul potager (cas ~85 %) ne perçoit
      strictement aucun changement — bot, PWA, `/potager`, sélecteur, saisies et statistiques identiques

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : base de données + couche services (aucun changement d'interaction Telegram ni PWA)
- Migration BDD requise : **oui** — nouveau `migrations/migration_vXX.sql` ⚠️ vérifier le dernier numéro réellement présent dans `migrations/` avant création (v28 au moment de la rédaction) + `rollback_vXX.sql`
- Dépendances : US-040 (socle `potagers`), US-046 (`potager_actif`), US-054 (`GET /potagers` et ses compteurs)
- Prépare : US-081 à US-088 — **chemin critique de l'épic**
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `migrations/`, `database/models.py`, `app/services/potager_actif.py`, `main.py` (`GET /potagers`)
- Le filtrage par état doit vivre **dans la couche services**, jamais dupliqué dans `bot.py`/`main.py` (invariant US-041)
- Ne pas transformer `plan` (freemium, colonne existante) en état : ce sont deux axes indépendants — un potager `free` peut être archivé, un potager payant aussi
- Prévoir dès maintenant le test d'isolation : un potager archivé ne doit remonter dans aucune requête scopée par `TenantContext` (cf. tests d'isolation US-042/US-043)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Migration sur une base existante
  Given une base contenant 3 potagers actifs et leurs événements
  When la migration d'état est appliquée
  Then les 3 potagers ont etat = "actif", archive_le et supprime_le à NULL
  And aucune donnée métier n'est modifiée

Scénario: Un potager archivé disparaît des listes par défaut
  Given un utilisateur membre de 2 potagers dont 1 avec etat = "archive"
  When il appelle GET /potagers sans paramètre
  Then un seul potager est retourné
  When il appelle GET /potagers?etat=tous
  Then les 2 potagers sont retournés, chacun avec son état

Scénario: Un potager archivé ne peut pas devenir le potager actif
  Given un potager d'état "archive" dont l'utilisateur est membre
  When il tente de l'activer
  Then l'opération est refusée avec un message explicite
  And son potager actif reste inchangé

Scénario: Idempotence
  Given la migration déjà appliquée
  When elle est rejouée
  Then aucune erreur n'est levée et aucune colonne n'est dupliquée
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `backend`, `bdd`
