**ID :** US-311
**Titre :** Ouvrir la PWA d'administration
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux une application d'administration distincte de celle des jardiniers, installable sur mon téléphone
Afin de consulter le pilotage sans extraction et sans mêler l'administration à l'application livrée aux utilisateurs

**Contexte fonctionnel :**
Décisions D1 et D2 (choix du 10/11/2026 : application séparée). Elle accueillera d'abord les vues de pilotage LLM (US-312 à US-315), puis d'autres vues de contrôle. Sa maquette de référence est produite par US-318.

**Critères d'acceptance :**
- [ ] CA1 : Une application Vite + React vit dans `admin/`, avec son `package.json`, son manifeste, son icône et son service worker ; elle partage la configuration Tailwind et les jetons de l'identité visuelle du frontend, sans importer de code métier du jardinier.
- [ ] CA2 : Elle est servie par l'API FastAPI sous `/pilotage/` (périmètre du manifeste et du service worker limité à ce chemin) ; les routes du jardinier et `/admin/...` ne changent pas.
- [ ] CA3 : La connexion utilise le compte et le jeton existants ; un compte qui n'est pas `ADMIN_EMAIL` voit un écran « accès réservé » et aucune donnée n'est chargée.
- [ ] CA4 : La coquille offre une navigation entre vues, un sélecteur de période (aujourd'hui, 7 jours, 30 jours, 90 jours, personnalisée), les filtres provenance, canal et modèle, partagés par toutes les vues et gardés dans l'adresse.
- [ ] CA5 : La vue du jour se rafraîchit toutes les 60 secondes quand l'onglet est visible ; l'heure de dernière mise à jour est affichée ; une panne de l'API affiche les dernières valeurs avec la mention de leur âge.
- [ ] CA6 : L'application est utilisable à 360 px de large ; breakpoints Tailwind pour la page, container queries pour les composants (règle du projet).
- [ ] CA7 : Le service worker ne met en cache aucune réponse de `/admin/...` : hors ligne, l'application s'ouvre et dit qu'elle n'a pas de données.
- [ ] CA8 : Les déploiements dev et prod construisent et publient `admin/` ; `tests/test_us005_deploiement.py` couvre le nouveau paquet ; le runbook de déploiement est mis à jour.
- [ ] CA9 : Le paquet du frontend jardinier ne contient aucun module de l'application d'administration.
- [ ] CA10 : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration, déploiement)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-318 (maquette de référence, validée avant de démarrer) ; US-310 pour afficher des données, la coquille peut être livrée avant
- Décisions liées : D1, D2, D8
- Points ouverts : chemin `/pilotage/` ou sous-domaine dédié ; bibliothèque de graphiques (reprendre celle de `frontend/src/views/Stats.jsx` si elle convient)
- Un `admin/CLAUDE.md` décrit les commandes et les règles de l'application.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given je suis connecté avec le compte ADMIN_EMAIL
When j'ouvre /pilotage/ sur mon téléphone
Then la coquille s'affiche avec le sélecteur de période sur "7 jours"
And je peux l'installer comme application
Given je suis connecté avec un compte de jardinier
When j'ouvre /pilotage/
Then je vois "accès réservé" et aucune requête /admin/pilotage n'aboutit
```

**Labels GitHub :** `us`, `pwa`, `admin`, `deploiement`
