# À corriger — relevé pendant la relecture G2

- B13 : aucun type « fin de culture » dans proposer_geste (capacité manquante) ; le cas est joué sur le potager neuf, sans haricot en place (jeu).
- B04-F7 : le compagnon retire la liste des parcelles de sa question ; l'afficher (amélioration).
- B05-F2 : l'attendu cite « sous abri en février », absent de ce que voir_calendrier a rendu : calendrier ou attendu à vérifier.
- B05-F6 : attendu du radis appliqué au cerfeuil tubéreux (jeu) ; le compagnon dit pouvoir « compléter la fiche » sans en avoir le moyen.
- B05-F6, ARBITRAGE : le porteur attend une réponse issue d'une recherche web (géolocalisation, période, région) et la procédure pour compléter la fiche. Aucune capacité de recherche web n'existe ; à concilier avec « les sources d'abord, jamais d'invention ».
- B08-F4 : la consigne « demande au jardinier quand il a arrosé » rendue par voir_meteo est ignorée ; « tomates pas en culture active » affirmé sans lecture, non relevé par le code (contrôle faux).
- B12 (porteur) : aucun cas « même culture sur plusieurs parcelles » dans le jeu ; seule la plantation demande la parcelle. Règle proposée à confirmer : une → d'office ; plusieurs → demander avec la liste ; aucune → le signaler.
- IMPORTANT (porteur, 27/11) : Telegram propose les parcelles où la culture est en place (règle dans app/bot/saisie.py, US-021) ; la PWA et le compagnon ne le font pas. Une seule parcelle → d'office ; plusieurs → boutons ; aucune → toutes. Règle à descendre dans les services, avec le contrôle de cohérence « aucune trace de X sur Y ».
- Relevé en lisant le code (B15-F7), non testé : toute nouvelle proposition remplace celle qui attend (gestes_conversation.proposer). Quand le compagnon prépare deux cartes au même tour (B07 : levée du haricot et du radis), seule la dernière resterait confirmable.

## Ajouts après les premiers cas (27 et 28/11)

- Compagnon : un résultat d'outil est coupé à 6 000 caractères (`app/services/compagnon/fil.py`) ; la pépinière en fait 16 304.
- Juge : il ne lit que 1 500 caractères d'un résultat (`tools/jeu_evaluation/juge.py`) ; les traces en gardent 4 000.
- B16-F2 : `voir_stock` se dit « stock de graines et de plants » ; des graines semées sont présentées comme restantes.
- B17-F5 : période par défaut du carnet ramenée à 6 mois (fait, non commité).
- B23-F4 : « Je te montre la carte ? » répété, aucune carte préparée.
- Pépinière : lot clôturé ou sans graines encore annoncé « repiquage en retard » (lots 2 et 7).
- Garde-fou : le semis sans quantité n'est pas refusé par le contrôle central (`valider_evenement`).
- Cultures non localisées : `parcelles_avec_culture` les ignore (lu dans le code, non testé).
