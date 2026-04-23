**ID :** US-015  
**Titre :** Déployer un environnement dev isolé sur le serveur Scaleway

**Story :**  
En tant qu'administrateur  
Je veux que chaque push sur la branche `dev` déclenche un déploiement automatique vers un environnement dev isolé sur le serveur Scaleway  
Afin de tester les évolutions sans risquer d'écraser les données de production ni perturber les utilisateurs du bot actif

---

**Critères d'acceptance :**

- [ ] CA1 : Un push sur `dev` déclenche le workflow `deploy-dev.yml` (et non `deploy.yml`)
- [ ] CA2 : Le code est déployé dans `/opt/potager-dev`, isolé de `/opt/potager` (prod)
- [ ] CA3 : Les migrations SQL sont appliquées sur la base `potager_dev` uniquement (jamais sur `potager`)
- [ ] CA4 : Le service systemd `potager-dev.service` est redémarré après chaque déploiement
- [ ] CA5 : Un fichier `/opt/potager-dev/.deploy_history` est mis à jour à chaque déploiement avec : date ISO, branche, commit SHA court, statut (success/failure)
- [ ] CA6 : Le smoke test vérifie que `potager-dev.service` est actif après redémarrage
- [ ] CA7 : Un push sur `main` ne déclenche pas `deploy-dev.yml` (isolation stricte des workflows)
- [ ] CA8 : Les variables d'environnement sont lues depuis `/opt/potager-dev/.env.dev-server` (jamais depuis `.env.prod`)

---

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : infrastructure / CI-CD
- Migration BDD requise : oui — les migrations existantes doivent être appliquées sur `potager_dev` à la première exécution
- Dépendances : aucune US existante

**Pré-requis serveur (opérateur humain, avant implémentation) :**

| # | Action | Commande indicative |
|---|--------|---------------------|
| 1 | Créer la base PostgreSQL dev | `createdb potager_dev` |
| 2 | Cloner le repo dans `/opt/potager-dev` | `git clone <repo> /opt/potager-dev` |
| 3 | Checkout de la branche dev | `cd /opt/potager-dev && git checkout dev` |
| 4 | Créer `/opt/potager-dev/.env.dev-server` | Copier `.env.prod`, adapter `DATABASE_URL` → `potager_dev`, `APP_ENV=dev` |
| 5 | Créer le service `potager-dev.service` | Copier `potager.service`, adapter `WorkingDirectory` et `EnvironmentFile` |
| 6 | Activer le service | `systemctl enable potager-dev.service` |

**Pré-requis GitHub (opérateur humain) :**

| # | Action |
|---|--------|
| 7 | Créer la branche `dev` depuis `main` |
| 8 | (Recommandé) Branch protection sur `main` : bloquer push direct, exiger PR |
| 9 | Aucun nouveau secret requis — `SCALEWAY_SSH_PRIVATE_KEY`, `SCALEWAY_HOST`, `SCALEWAY_USER` sont réutilisés |

**Décision ouverte :** utiliser un token Telegram dédié pour le bot dev (recommandé) ou le même token prod avec risque de conflit de session.

---

**Estimation :** 5 points

---

**Scénario Gherkin :**

```gherkin
Feature: Déploiement continu sur environnement dev isolé

  Scenario: Push sur dev déclenche le déploiement dev
    Given la branche dev existe sur GitHub
    And le service potager-dev.service est configuré sur le serveur
    When un développeur pousse un commit sur la branche dev
    Then le workflow deploy-dev.yml se déclenche automatiquement
    And le code est synchronisé dans /opt/potager-dev
    And les migrations sont appliquées sur potager_dev uniquement
    And le service potager-dev.service redémarre
    And le fichier .deploy_history est mis à jour avec la date, le commit SHA et le statut success

  Scenario: Échec de déploiement tracé dans l'historique
    Given un commit invalide est poussé sur dev
    When le workflow deploy-dev.yml échoue (smoke test négatif)
    Then le fichier .deploy_history enregistre le statut failure avec le commit SHA
    And une notification d'échec est visible dans GitHub Actions

  Scenario: Push sur main n'affecte pas l'environnement dev
    Given l'environnement dev est actif dans /opt/potager-dev
    When un commit est poussé sur main
    Then seul deploy.yml se déclenche
    And /opt/potager-dev reste inchangé
    And potager_dev reste inchangé
```

---

**Livrables attendus :**

| Fichier | Action | Description |
|---------|--------|-------------|
| `.github/workflows/deploy-dev.yml` | CRÉER | Workflow déclenché sur push `dev`, déploie sur `/opt/potager-dev`, met à jour `.deploy_history` |
| `.github/workflows/deploy.yml` | MODIFIER | S'assurer que le déclencheur est strictement `branches: [main]` (vérification) |
| `docs/INFRA_DEV_SETUP.md` | CRÉER | Documentation des étapes manuelles serveur + secrets GitHub pour onboarding futur |

---

**Labels GitHub :** `us`, `sprint-6`, `infra`, `ci-cd`
