# Noter un geste : écarts entre Telegram et la PWA

Inventaire du 27/11/2026, par lecture du code (rien n'a été rejoué à l'écran). Référence : ce que fait Telegram
(`app/bot/saisie.py`, `_parse_and_save`, et `app/bot/enregistrement.py`).

## Pourquoi les deux diffèrent

Les trois voies sans Telegram (PWA actuelle, boucle du compagnon, assistants connectés) passent par le même contrôle
commun, `gestes_conversation.controler`. Tout ce que Telegram demande **par boutons** est resté écrit dans le bot et
n'est jamais passé dans ce contrôle.

## Ce qui est déjà commun

Lot cité par son numéro, emplacement des godets, culture et variété ramenées à leur nom, culture hallucinée retirée,
quantité obligatoire (récolte, semis, plantation), culture inconnue au semis (la PWA renvoie vers Telegram), validation
centrale avant proposition, avertissements de rotation et d'association.

## Les écarts

« Absent » : aucun appel trouvé hors du bot.

| # | Geste | Ce que fait Telegram | PWA et compagnon | Gravité |
|---|---|---|---|---|
| 1 | Tout geste au jardin sans parcelle | culture sur une parcelle : remplie d'office ; sur plusieurs : boutons ; sur aucune : toutes les parcelles ; « Sans parcelle » toujours possible | absent. Le compagnon ne demande que pour une plantation | **forte** : geste non rattaché au plan |
| 2 | Culture ou variété jamais vue sur la parcelle citée | « Aucune trace de X sur Y (trouvé sur : …) », parcelle redemandée | la validation refuse avec son message, sans proposer les bonnes parcelles | **forte** |
| 3 | Récolte sans variété | plusieurs variétés : boutons ; une seule : remplie d'office | absent | **forte** : stock et statistiques par variété faussés |
| 4 | Perte | « au potager ou en pépinière ? », puis la variété | absent : le compagnon n'a que « perte », pas la perte de godets | **forte** : mauvais stock diminué |
| 5 | Vente | variété demandée | la boucle ne propose pas la vente | moyenne |
| 6 | Mise en godet | variété, lot ambigu, « sur combien de graines ? », aucun semis en pépinière | boucle : type proposable, aucune de ces questions | **forte** |
| 7 | Quantité en pépinière | question dédiée | absent | moyenne |
| 8 | Récolte pesée d'une culture végétative | « combien de pieds ? » | absent | **forte** : pieds restants faux |
| 9 | Plantation, vente, perte de godets | choix du lot d'origine | absent | moyenne |
| 10 | Semis | contexte pépinière ou pleine terre proposé et corrigeable | non proposé sur la carte | moyenne |
| 11 | Déplacement, levée, clôture de lot | questions et choix du lot | la boucle ne propose pas ces gestes | moyenne |
| 12 | Fin de culture | geste de l'application | la boucle ne l'a pas (cas B13) | **forte** |
| 13 | Parcelle citée inexistante | « Créer et enregistrer ? » | refus avec les noms proches | faible |
| 14 | Culture non dite (semis, plantation de la file) | question de culture | refus | faible |

## Ce que je propose

1. **Une seule règle, écrite une fois.** Chaque contrôle sort du bot et devient une fonction de service qui rend soit
   le geste complété, soit **une question avec ses choix**. Telegram les affiche en boutons, la PWA en puces, le
   compagnon et les assistants les lisent dans le résultat de l'outil. Le comportement de Telegram ne change pas.
2. **Ordre proposé**, par lots livrables et testables :
   - lot A : parcelle (1, 2) ;
   - lot B : variété et pieds (3, 4, 8) ;
   - lot C : fin de culture (12) ;
   - lot D : pépinière (6, 7, 9, 10) ;
   - plus tard : 5, 11, 13, 14.
3. **Le jeu d'évaluation** : les attendus de B25 et B26 doivent admettre « Sans parcelle », et chaque lot ajoute ses
   cas avec les données qui les déclenchent (plusieurs parcelles, plusieurs variétés, godets).

## Limites

- La levée, le déplacement et la vente n'ont été lus que par leurs points d'entrée, pas en détail.
- La PWA a d'autres portes (boutons « Noter », fiche d'un lot, plan) qui ne sont pas couvertes ici.
- Corrections de gestes et commandes ne sont pas dans le périmètre.
