US-002 : Adapter le calcul du stock réel selon le type d'organe
Titre : Adapter le calcul du stock selon que la récolte soit destructive ou continue

Story :
En tant que jardinier
Je veux que le stock des plants soit calculé différemment selon qu'il s'agisse de cultures récolte-destructive ou récolte-continue
Afin d'avoir un suivi précis : nombre de plants vivants vs rendement cumulé

Critères d'acceptance :

 CA1 : Pour les organes vegétatif : récolte réduit le stock de plants (récolte 1 plant = -1 du stock)
 CA2 : Pour les organes reproducteur : récolte n'affecte pas le stock de plants (toujours vivant)
 CA3 : Dans cmd_stats(), affichage différencié : "salade : 3 plants récoltés" vs "tomate : 5 plants actuels, 12 kg cumulés"
 CA4 : /stats JSON API retourne champs distincts : stock_plants + rendement_total_kg selon le type
Notes techniques :

Composants impactés : bot.py (cmd_stats), ia_orchestrator.py (build_question_context)
Migration BDD requise : non
Dépendances : #US-001
Estimation : 3 points

Scénario Gherkin :

Labels GitHub : us, bot, scoring