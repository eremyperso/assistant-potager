**Titre :** Restructurer /help en 4 domaines fonctionnels

**Story :**
En tant que jardinier
Je veux que la commande /help organise les actions en 4 domaines métier (Pépinière, Culture en place, Récolte, Sorties)
Afin de comprendre immédiatement dans quel domaine s'inscrit mon action et quelle commande utiliser

**Critères d'acceptance :**
- [ ] CA1 : Le message /help présente les actions regroupées en 4 sections : 🌱 Pépinière · 🌿 Culture en place · 🧺 Récolte · ❌ Sorties, plus 📋 Observations (transversale)
- [ ] CA2 : Chaque section liste les types d'action associés avec 1 exemple vocal pour les plus importantes
- [ ] CA3 : Le message reste ≤ 4096 chars et lisible sur écran mobile (listes à puces, pas de tableaux)
- [ ] CA4 : Le message est en français, la commande reste `/help` (anglais)
- [ ] CA5 : La restructuration intègre les nouveaux types issus des US de modélisation (mise_en_godet, eclaircissage, recolte_finale, arrachage, recolte_graines) dès qu'ils sont disponibles

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (bot.py, cmd_help)
- Migration BDD requise : non
- Dépendances : US_Enregistrer_mise_en_godet, US_Enregistrer_eclaircissage_pleine_terre, US_Enregistrer_recolte_finale_cloture, US_Enregistrer_arrachage_fin_culture — à livrer **après** ces US
- Message 100% statique, zéro token Groq

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Feature: /help structuré en domaines fonctionnels

  Scenario: Affichage de l'aide restructurée
    Given le bot est démarré
    When le jardinier envoie "/help"
    Then le message contient les 4 sections : Pépinière, Culture en place, Récolte, Sorties
    And chaque section liste ses types d'action
    And le message est ≤ 4096 caractères
    And aucun tableau ni colonne alignée n'est utilisé

  Scenario: Intégration des nouveaux types d'action
    Given les US de modélisation sont livrées
    When le jardinier consulte /help
    Then les nouveaux types (mise_en_godet, recolte_finale, arrachage...) apparaissent dans leur domaine
```

**Labels GitHub :** `us`, `priorite-basse`, `bot`, `ux`, `help`
