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

Labels GitHub : us, ux, display