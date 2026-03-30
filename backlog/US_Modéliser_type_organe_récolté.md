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

Labels GitHub : us, database, domain-model