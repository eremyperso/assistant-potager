US-005 : Déploiement automatisé sur serveur Scaleway
Titre : Déployer l'application sur Scaleway via script ou GitHub Actions

Story :
En tant que développeur
Je veux pouvoir déployer le code sur mon serveur Scaleway en une commande
Afin de mettre en production rapidement et de façon reproductible

Critères d'acceptance :
- [ ] CA1 : Un script `deploy.sh` (ou workflow GitHub Actions) transfère et redémarre l'application sur Scaleway via SSH
- [ ] CA2 : Le déploiement installe les dépendances (`pip install -r requirements.txt`) et applique les migrations SQL en attente
- [ ] CA3 : L'application est gérée par `systemd` pour redémarrer automatiquement en cas de crash
- [ ] CA4 : Les variables sensibles (TOKEN_PROD, DATABASE_URL) sont injectées côté serveur via `.env.prod` — non transmises par le script
- [ ] CA5 : Un test de smoke post-déploiement vérifie que le bot répond sur Telegram dans les 30 secondes

Notes techniques :
- Composants impactés : (nouveau) deploy.sh ou .github/workflows/deploy.yml
- Migration BDD requise : non (le script exécute les migrations existantes)
- Dépendances : #US-004 (gestion des environnements dev/prod doit être en place)
- Infrastructure : serveur Scaleway sous Ubuntu 22.04

Estimation : 5 points

Scénario Gherkin :
```gherkin
Scenario: Déploiement réussi
  Given le code est à jour sur la branche main
  When le développeur exécute le script de déploiement
  Then le code est transféré sur le serveur Scaleway
  And les dépendances Python sont installées
  And les migrations SQL en attente sont appliquées
  And le service systemd est redémarré
  And le bot @AssistantPotagerBot répond dans les 30 secondes
```

Labels GitHub : `us`, `sprint-2`, `infra`, `devops`
