**Titre :** Afficher une aide en ligne synthétique via /help

**Story :**
En tant que jardinier
Je veux accéder à une aide concise depuis Telegram via `/help`
Afin de prendre en main rapidement le bot sans documentation externe

**Critères d'acceptance :**
- [ ] CA1 : La commande `/help` renvoie un message en français, lisible sur écran mobile (pas de tableaux larges, pas de lignes > 35 caractères de contenu)
- [ ] CA2 : Le message de bienvenue `/start` mentionne `/help` pour accéder à l'aide
- [ ] CA3 : L'aide couvre en une seule réponse (≤ 4096 chars) : les commandes système, les types d'actions avec 1 exemple chacune, les mots-clés de navigation et 3 exemples de questions analytiques
- [ ] CA4 : Le formatage utilise uniquement le Markdown Telegram compatible mobile (gras `*...*`, italique `_..._`, pas de tableaux)
- [ ] CA5 : La commande est en anglais (`/help`) mais tout le contenu affiché est rédigé en français

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : non
- Dépendances : aucune — message 100% statique, zéro token Groq
- Contrainte affichage : éviter les colonnes alignées avec des espaces (rendu imprévisible sur mobile), préférer les listes à puces
- La commande `/aide` existante (si présente) peut être conservée ou fusionnée selon décision du développeur

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Feature: Aide en ligne mobile-friendly

  Scenario: Accès à l'aide via /help
    Given le bot est démarré et l'utilisateur est sur mobile
    When l'utilisateur envoie "/help"
    Then le bot répond en français avec un message unique <= 4096 caractères
    And le message liste les commandes système
    And le message liste les types d'actions avec un exemple par action
    And le message liste les mots-clés de navigation
    And le message contient au moins 3 exemples de questions analytiques
    And aucun tableau ni colonne alignée n'est utilisé

  Scenario: /start invite à consulter /help
    Given le bot est démarré
    When l'utilisateur envoie "/start"
    Then le message de bienvenue contient une référence à "/help"
```

**Labels GitHub :** `us`, `sprint-current`, `bot`
