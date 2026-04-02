US-003 : Affichage différencié des stats selon le type de culture
Titre : Afficher les statistiques de façon agronomiquement pertinente

Story :
En tant que jardinier
Je veux que l'interface PWA et les commandes Telegram affichent les stats adaptées au type de chaque culture
Afin de lire facilement mon potentiel de production réel

Critères d'acceptance :

 CA1 : /stats commande Telegram montre pour cultures vegétatif : "5 plants de salade (4 récoltés, 1 actuel)"
 CA2 : /stats montre pour cultures reproducteur : "2 plants de tomate actuels · rendement 8.5 kg"
 CA3 : Interface PWA affiche deux sections distinctes : "Cultures à récolte unique" vs "Cultures productives continues"
 CA4 : /ask supporté les questions adapté type (ex: "quelle salade ai-je le plus produit" vs "quel plant est le plus productif")
Notes techniques :

Composants impactés : bot.py (send_voice_reply), index.html, main.py (endpoints)
Migration BDD requise : non
Dépendances : #US-001, #US-002
Estimation : 3 points

Scénario Gherkin :

```gherkin
Feature: Affichage agronomiquement pertinent des statistiques

  Scenario: Commande /stats pour une culture végétative
    Given 5 plants de salade plantés, 4 récoltés, 1 actuel
    And salade est classifiée type_organe_recolte = "végétatif"
    When l'utilisateur envoie /stats sur Telegram
    Then le message contient "5 plants de salade (4 récoltés, 1 actuel)"

  Scenario: Commande /stats pour une culture reproductive
    Given 2 plants de tomate actuels avec 8.5 kg récoltés au total
    And tomate est classifiée type_organe_recolte = "reproducteur"
    When l'utilisateur envoie /stats sur Telegram
    Then le message contient "2 plants de tomate actuels · rendement 8.5 kg"

  Scenario: Interface PWA affiche deux sections distinctes
    Given des cultures végétatives et reproductrices en base
    When l'utilisateur ouvre l'interface PWA
    Then la section "Cultures à récolte unique" est visible avec les cultures végétatives
    And la section "Cultures productives continues" est visible avec les cultures reproductrices

  Scenario: Question /ask adaptée au type de culture
    Given la question "quelle salade ai-je le plus produit ?"
    When l'utilisateur envoie cette question via /ask
    Then la réponse porte sur le nombre de plants récoltés, pas sur le rendement en kg

  Scenario: Question /ask sur productivité d'un plant reproducteur
    Given la question "quel plant de tomate est le plus productif ?"
    When l'utilisateur envoie cette question via /ask
    Then la réponse porte sur le rendement_total_kg par plant, pas sur le nombre de récoltes
```

Labels GitHub : us, ux, display