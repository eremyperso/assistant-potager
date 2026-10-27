**ID :** US-276
**Titre :** Alléger le catalogue de l'agent et le projeter selon la phrase
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon ne me propose jamais d'écrire ou de supprimer quand je pose une question
Afin de pouvoir lui demander « est-ce que je peux supprimer la planche sud ? » sans recevoir une suppression à confirmer

**Contexte fonctionnel :**
Lot 1 du cadrage `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`. Le §4.5 décrit le « catalogue projeté selon l'état », mais aucune US ne le portait. La mesure US-256 du 27/10/2026 montre que le catalogue livré (environ 3 200 jetons) surcharge la tâche, quel que soit le modèle : 29 % de bon outil sur Ministral 3B, 60 % sur le 8B et 49 % sur Small. Les erreurs observées viennent d'outils qui se recouvrent, pas d'un manque de capacité :

- `parcelle(action="supprimer")`, une action inventée, à côté de `parcelle_supprimer` ;
- `calendrier`, outil d'écriture, appelé dès qu'une date apparaît (« corrige le semis, c'était le 3 mai », « règle un rappel demain à 8 heures ») à la place d'une lecture ;
- une question transformée en écriture : « est-ce que je peux supprimer la planche sud sans perdre mon historique ? » donne `parcelle_supprimer("Planche Sud")`, une proposition valide qui arrive au jardinier avec un bouton de confirmation ; « comment me débarrasser des limaces ? » donne `bioagresseur(action="rattacher")`.

Le code sait déjà reconnaître une destruction (la règle `parcelle_supprimer` de `interpreteur_commandes.py`) et une demande de savoir (`_est_demande_de_savoir`). Il décide donc, avant l'appel, quels outils le modèle voit. Le modèle ne fait plus que choisir dans un catalogue réduit. C'est le premier allègement du §4.5, à livrer avant US-257.

**Critères d'acceptance :**
- [ ] CA1 : Chaque intention a un seul outil. Une écriture et une lecture sur le même sujet portent des noms et des descriptions qui commencent par leur verbe (« renseigner… », « afficher… »). Les recouvrements relevés par US-256 (`parcelle` et `parcelle_supprimer`, `calendrier` et `consulter`) sont levés.
- [ ] CA2 : Le code projette le catalogue avant l'appel au modèle. Une phrase interrogative (point d'interrogation, « est-ce que », « comment », « quand », « peux-tu ») n'expose aucun outil d'écriture : seulement la lecture et les outils de réponse.
- [ ] CA3 : Un outil destructeur n'est exposé que si la phrase contient un verbe de destruction, reconnu par la même liste que la règle `parcelle_supprimer`, jamais par une seconde liste. Il ne l'est jamais pour une phrase interrogative.
- [ ] CA4 : Un catalogue projeté est un sous-ensemble du catalogue complet : `controler_parite_outils` tient, et chaque outil garde son schéma (C5). Le nombre de projections est borné (complet, sans écriture, sans destruction), et chacune garde un ordre stable pour que son préfixe reste en cache.
- [ ] CA5 : Les descriptions des outils sont raccourcies. Le rapport US-256 donne les jetons d'entrée par message avant et après.
- [ ] CA6 : Rejoué par US-256 sur Ministral 3B (cascade et couperets au jardinier, US-256 / CA9) : aucun couperet n'arrive au jardinier sur QUE-3, REG-1, DOU-1, DOU-2 et REG-2. Le taux de bon outil de l'agent ne baisse dans aucune catégorie.
- [ ] CA7 : Les tests existants de l'agent (US-235 à US-238) restent verts ; une projection se teste sans modèle.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (agent interpréteur)
- Migration BDD requise : non
- Dépendances : US-256 (CA9). À livrer **avant** US-257, qui retire `poser_question`, `demander_precision` et `hors_perimetre` : US-257 reprendra la projection telle quelle.
- Production conseillée : **Opus 5.5, effort `high`**. C'est un garde-fou sur le chemin d'écriture, et un choix de projection qui touche au cache de prompt. Les tests de projection sont délégables à Sonnet 5.5.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le compagnon en AGENT_MODE=actif
When le jardinier écrit "est-ce que je peux supprimer la planche sud sans perdre mon historique ?"
Then le modèle ne voit aucun outil d'écriture
And aucune proposition n'est présentée à confirmer

When le jardinier écrit "renomme la planche sud en planche des courges"
Then le modèle ne voit pas l'outil de suppression
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `securite`
