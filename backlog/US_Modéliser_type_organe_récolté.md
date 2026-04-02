US-001 : Modéliser le type d'organe récolté en base de données
Titre : Ajouter la classification agronomique des cultures (végétatif vs reproducteur)

Story :
En tant que jardinier
Je veux que l'application connaisse le type d'organe récolté pour chaque culture
Afin que les calculs de rendement et de stock soient scientifiquement corrects

Critères d'acceptance :

 CA1 : La table evenements possède une colonne type_organe_recolte avec valeurs vegétatif | reproducteur | null
 CA2 : Une table culture_config catégorise les cultures classiques (salade→végétatif, tomate→reproducteur, etc.)
 CA3 : Migration SQL v5 crée la structure et pré-popule 15+ cultures avec classification correcte
 CA4 : L'API expose GET /cultures retournant liste des cultures avec leur type et description agronomique
Notes techniques :

Composants impactés : models.py, migrations/migration_v5.sql
Migration BDD requise : oui
Dépendances : aucune
Estimation : 2 points

Scénario Gherkin :

```gherkin
Feature: Classification agronomique des cultures

  Scenario: Consulter le type d'organe d'une culture connue
    Given la table culture_config est peuplée avec les 15+ cultures classiques
    When l'API reçoit GET /cultures
    Then la réponse JSON contient "salade" avec type_organe_recolte = "végétatif"
    And la réponse JSON contient "tomate" avec type_organe_recolte = "reproducteur"

  Scenario: Culture sans classification connue
    Given une culture "persil" sans entrée dans culture_config
    When l'API reçoit GET /cultures
    Then "persil" apparaît avec type_organe_recolte = null

  Scenario: Migration v5 appliquée sur une base existante en v4
    Given une base de données en version v4
    When la migration migration_v5.sql est exécutée
    Then la colonne type_organe_recolte existe dans la table evenements
    And la table culture_config contient au moins 15 lignes
    And aucune donnée existante n'est perdue
```

Labels GitHub : us, database, domain-model