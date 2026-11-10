**ID :** US-310
**Titre :** Exposer les agrégats de pilotage à l'administrateur
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux interroger la consommation par période, modèle, type d'appel, canal et potager
Afin que le tableau de bord, les alertes et le bilan lisent tous les mêmes chiffres

**Contexte fonctionnel :**
Décisions D7, D9 et D11. `app/services/metriques_routage.py` agrège déjà `routage_logs` pour trois routes `/admin/...`. Cette US ajoute un service `app/services/pilotage/agregats.py` sur `conso_tokens`, source unique des vues US-312 à US-315, des seuils US-316 et du bilan US-317.

**Critères d'acceptance :**
- [ ] CA1 : `GET /admin/pilotage/synthese` renvoie pour une période : appels, jetons d'entrée, de sortie, en cache, taux de cache, secondes d'audio, caractères, coût, répartition des issues, latence P50 et P95, et les mêmes valeurs pour la période précédente de même durée.
- [ ] CA2 : `GET /admin/pilotage/series` renvoie une série par jour (ou par heure sur une journée) d'une mesure choisie, ventilée par une dimension choisie parmi modèle, type d'appel, canal, provenance, issue, version.
- [ ] CA3 : `GET /admin/pilotage/ventilation` renvoie le classement d'une dimension (dont potager et utilisateur) pour une mesure, avec limite.
- [ ] CA4 : `GET /admin/pilotage/echanges` renvoie la distribution du coût, des jetons et du nombre d'appels par échange (médiane, P95, maximum).
- [ ] CA5 : Toutes les routes acceptent les filtres période, provenance, canal, modèle, type d'appel, potager ; sans filtre de provenance, seuls `usage` et `fond` sont comptés.
- [ ] CA6 : Les jetons ne sont sommés que sur les lignes d'unité `jeton` ; secondes et caractères sont des mesures distinctes.
- [ ] CA7 : Les routes sont en lecture seule et protégées par `require_admin_user` ; un compte non administrateur reçoit 403, une requête sans jeton 401.
- [ ] CA8 : Le service lit toutes les lignes de tous les potagers ; cette lecture hors périmètre de potager est faite par un chemin explicite et testé (US-043), jamais par contournement silencieux de `tenant_scope`.
- [ ] CA9 : Aucune route n'appelle un modèle ; les percentiles sont calculés en Python (méthode de `_p95`), identiques sous SQLite et PostgreSQL.
- [ ] CA10 : Une période de 90 jours sur 100 000 lignes répond en moins d'une seconde sur la base de test ; les index nécessaires sont ajoutés par migration.
- [ ] CA11 : Aucun `db.query` hors `app/services/` (test US-041) ; `docs/openapi.json` est régénéré.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (services, API d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : à l'analyse (index sur `cree_le`, `provenance`, `echange_ref`)
- Dépendances : US-306, US-307 ; US-309 pour les mesures de coût (renvoyées nulles sinon)
- Décisions liées : D7, D9, D11
- Une fiche `docs/domaines/pilotage-llm.md` est créée et entre dans la table de `docs/domaines/README.md` dans le même commit.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la base contient 100 lignes "usage" et 400 lignes "mesure" sur la semaine
When l'administrateur appelle GET /admin/pilotage/synthese sur la semaine
Then le nombre d'appels vaut 100
When il ajoute le filtre provenance=mesure
Then le nombre d'appels vaut 400
When un jardinier non administrateur appelle la même route
Then il reçoit 403
```

**Labels GitHub :** `us`, `llm`, `observabilite`, `api`
