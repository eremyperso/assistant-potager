**ID :** INC-022
**Titre :** « Quel est le lieu de mon potager ? » : l'agent répond « Lyon » alors que le potager est enregistré à Cormeilles-en-Parisis
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager de recette (id 33), bot Telegram, mode agent d'abord (branche `agent-mode-prioritaire`),
le 05/11/2026, dans une même conversation de 10 échanges :
1. 16:27 « quel météo sur Lyon ? » → réponse correcte pour Lyon (géocodage Open-Meteo, coordonnées 45.75, 4.85).
2. 16:28 « et la météo sur mon potager ? » → réponse correcte (coordonnées du potager 48.97, 2.20).
3. 16:36 « quel était la météo à cormeilles en parisis le 2 novembre dernier » → réponse correcte.
4. 16:38 « quel est le llieu de mon potager ? » (faute de frappe d'origine conservée).
5. 16:55, test de recette B6 : « il fait quoi aujourd'hui ? » (attendu au plan de test : « Météo du jour du potager (préchargement) »),
   dans la même conversation de 10 échanges où « Lyon » a été citée plus tôt.

**Résultat obtenu :**
Réponse : « Ton potager est à Lyon, Emmanuel ! ».
Le journal montre `texte seul → aucune proposition`, `LLM agent … out=10` : le modèle n'a appelé aucun outil
et n'a lu aucune donnée du potager. Il a répondu à partir de la conversation, dans laquelle
« Lyon » avait été nommée quelques minutes plus tôt à propos d'une autre ville que celle du potager.
Aucun garde-fou de la couche agent n'est intervenu : ils portent sur les relevés des outils, et il n'y en avait pas.

**Test B6 — « il fait quoi aujourd'hui ? » (même cause, rattrapé par un garde-fou) :**
Le journal montre que le modèle a appelé l'outil `meteo` sans lieu (`meteo ton potager aujourdhui 3 jour(s)`, coordonnées
du potager 48.97, 2.20), puis a rédigé une phrase qui attribuait les chiffres à **Lyon** :
`chiffres attribués à ['Lyon'], absent des relevés → texte du code`. Le garde-fou sur les lieux a écarté la phrase
du modèle et renvoyé celle du code : « Pour ton potager : aujourd'hui, Couvert, de 4.6 à 10.7 °C, 0.0 mm de pluie prévu ».
Le texte final reçu par le jardinier est donc correct, mais le test est en échec sur le comportement du modèle :
- il a pris « Lyon » pour le lieu du potager alors que la météo lue est celle de Cormeilles-en-Parisis ;
- la météo du jour ne vient pas du préchargement du contexte : le modèle a dû appeler l'outil (un tour de plus,
  7 756 ms et 17 903 jetons), le préchargement étant lancé avant le modèle sans que la réponse s'y appuie.
Le résultat n'est correct que parce que le garde-fou a rattrapé l'erreur : sans lui, la réponse aurait annoncé la météo de Lyon
comme celle du potager. La cause est la même que ci-dessus : le modèle ne connaît pas la ville du potager et reprend
le seul lieu nommé dans la conversation.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
La réponse doit donner la ville enregistrée en base pour le potager 33, soit **Cormeilles-en-Parisis**
(la ville est bien enregistrée : les coordonnées 48.97, 2.20 utilisées pour la météo du potager sont celles
de cette commune). Plus généralement, l'agent ne doit jamais affirmer une caractéristique du potager
(ville, localisation, exposition, superficie, altitude…) sans l'avoir lue dans les données du potager,
et il ne doit jamais prendre pour le potager un lieu cité dans la conversation (par exemple la ville d'une
question météo posée un instant avant).
Pour B6, « il fait quoi aujourd'hui ? » doit donner la météo du jour du potager, sans que le modèle y associe un autre lieu
(le texte final est correct aujourd'hui, mais par rattrapage du code, pas par comportement du modèle).
Il s'agit d'une donnée métier du potager, pas d'un détail de conversation : une réponse fausse est ici
une erreur sur le référentiel de l'utilisateur, affirmée avec aplomb.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend (couche agent `app/services/agent/`).
- Nature probable : lacune de conception du contexte ou des outils de l'agent. La ville du potager existe
  en base (colonne `ville` du modèle `Potager`, US-074, avec latitude, longitude et altitude), mais elle n'est
  probablement exposée au modèle ni dans son contexte préchargé ni par un outil de lecture dédié.
  Le seul outil qui touche la localisation est `meteo`, qui étiquette son résultat « ton potager » sans nom de ville.
  À investiguer : ce que contient exactement le contexte préchargé sur le potager.
- Fichiers probablement concernés : `app/services/agent/catalogue_outils.py` (catalogue : outil de lecture des
  caractéristiques du potager), `app/services/agent/savoir.py` (résultat de l'outil météo, garde-fous sur les lieux),
  `app/services/agent/interpreteur_agent.py` (consigne et contexte envoyés au modèle),
  `database/models.py` (`Potager.ville`).
- Pistes à instruire par le Developer, sans préjuger : exposer la ville du potager au modèle (contexte ou outil),
  obliger un outil pour toute question sur une caractéristique du potager, et étendre aux noms de lieux sans
  relevé le garde-fou qui écarte aujourd'hui les chiffres absents des lectures.
- Même famille que INC-021 (fausse information présentée comme celle du potager, sans relevé derrière)
  et que le garde-fou « chiffre absent des lectures » qui existe déjà pour la météo.
- Corpus de connaissance concerné : à vérifier à la correction. Si une fiche de `data/connaissance/doc_app/`
  décrit ce que le compagnon sait du potager, elle devra être relue (voir CLAUDE.md, section « Corpus de connaissance »).

**Labels :** incident, agent, potager, donnees-metier
