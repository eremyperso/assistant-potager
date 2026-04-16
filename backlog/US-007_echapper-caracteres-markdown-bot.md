**ID :** US-007
**Titre :** Échapper automatiquement les caractères Markdown dans les messages du bot Telegram

**Story :**
En tant que jardinier
Je veux pouvoir nommer mes parcelles, cultures et variétés avec n'importe quel caractère (dont `_`, `*`, `` ` ``, `[`)
Afin d'éviter des erreurs d'affichage Telegram "Can't parse entities" qui rendent les réponses du bot illisibles

**Critères d'acceptance :**
- [ ] CA1 : Une fonction utilitaire `escape_markdown(text: str) -> str` est disponible et échappe les caractères spéciaux Markdown v1 (`_`, `*`, `` ` ``, `[`)
- [ ] CA2 : Tous les messages du bot qui insèrent des données utilisateur (noms de parcelles, cultures, variétés, types d'action) dans une f-string avec `parse_mode="Markdown"` utilisent cette fonction
- [ ] CA3 : Un nom de parcelle contenant `_` (ex : `carré_1`) s'affiche correctement dans `/plan`, `/historique`, `/stats`, et les réponses de confirmation d'action
- [ ] CA4 : Un nom de culture contenant `*` ou `` ` `` s'affiche correctement dans tous les messages Markdown du bot
- [ ] CA5 : Le comportement du bot est inchangé pour les noms sans caractères spéciaux
- [ ] CA6 : Aucun message Telegram ne lève l'exception `BadRequest: Can't parse entities` sur des données saisies légitimement

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (`bot.py`) — tous les appels `send_message`, `reply_text`, `edit_message_text` avec `parse_mode="Markdown"`
- Migration BDD requise : non
- Les caractères à échapper en Markdown v1 Telegram : `_`, `*`, `` ` ``, `[`
- La fonction utilitaire peut être placée dans `utils/telegram_utils.py` (à créer) ou dans `bot.py`
- Alternative à évaluer : basculer vers `parse_mode="MarkdownV2"` (Telegram recommande MarkdownV2 depuis 2020) — nécessite d'adapter les séquences de formatage existantes
- Dépendances : aucune

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Feature: Échappement des caractères Markdown dans les messages Telegram

  Scenario: Affichage d'une parcelle avec underscore dans le nom
    Given une parcelle nommée "carré_1" existe dans la base de données
    When le jardinier envoie la commande /plan
    Then le bot répond sans erreur "Can't parse entities"
    And le message affiché contient le nom "carré_1" lisible et correctement formaté

  Scenario: Confirmation d'une action sur une culture avec caractère spécial
    Given le jardinier enregistre une récolte de "tomate*cerise" dans la parcelle "serre_1"
    When le bot construit le message de confirmation en Markdown
    Then le message est envoyé avec succès
    And les caractères spéciaux sont affichés tels quels dans le message Telegram

  Scenario: Pas de régression sur les noms sans caractères spéciaux
    Given une parcelle nommée "potager" existe dans la base de données
    When le jardinier envoie la commande /historique
    Then le bot répond normalement avec le nom "potager" affiché sans altération
```

**Labels GitHub :** `us`, `sprint-4`, `bot-telegram`
