**ID :** INC-019
**Titre :** « Liste tout ce que j'ai fait aujourd'hui ? » répond « pas de mémoire persistante » au lieu de lire les actions menées (US-261 / CA4)
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-29

**Reproduction (jeu de test réalisé) :**
Recette locale dev de US-261 / CA4 (scénario « actions au-delà des 5 premières »), à faire juste
après le scénario 5 (série de gestes enregistrés dans le potager, dont plus de 5 dans les 24 h).
Dans Telegram, potager 33, `APP_ENV=dev`, le message texte envoyé est :
`liste tout ce que j'ai fais aujourd'hui ?`
*(Nombre exact de gestes enregistrés avant la phrase : à confirmer par le déclarant — non fourni.)*

**Résultat obtenu :**
Le bot répond : « Je ne peux pas accéder aux actions que tu as réalisées aujourd'hui dans ton
potager, car je n'ai pas de mémoire persistante entre les échanges. Si tu veux, tu peux me
rappeler ce que tu as fait pour q… »

Journal du bot (extraits utiles, ordre chronologique) :
- `🎛️ INTERPRETEUR : phrase interrogative → cascade des questions`
- `❓ QUESTION AGENT : nature=None → _ask_question`
- `🧭 ROUTEUR : origine=modele │ nature=QUESTION_DATA` (modèle `mistral/ministral-8b-latest`)
- `🚫 AGENT SQL : geste 'null' absent de la question : ni classement ni historique de geste`
- `↪️ ROUTEUR REMONTÉE : donnée non exploitable → raisonnement (1 saut)`
- réponse produite par `ministral-8b-latest` (appel `question`), sans aucune trace d'un appel
  d'outil `lire` ni d'un tour de l'agent interpréteur.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Le bot retrouve les actions menées du jour, y compris celles au-delà des 5 références du
contexte (A6, A7…), via `lire(quoi="actions")` (US-261 / CA4). Il ne doit ni dire qu'il ne se
souvient pas, ni inventer une action absente de la table `actions_menees`.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram / aiguillage des phrases interrogatives (couche
  interpréteur et cascade des questions).
- Nature probable : régression logique d'aiguillage — la phrase interrogative semble partir dans
  la cascade des questions (routeur + AGENT SQL) sans passer par l'agent qui dispose de l'outil
  `lire`. À investiguer.
- Fichiers probablement concernés : `app/services/interpreteur_commandes.py` (log « phrase
  interrogative → cascade des questions », ~l.2861), `app/bot/messages.py` (`_ask_question`,
  ~l.327 et ~l.789), `app/services/agent/lecture.py` (outil `lire`, `quoi="actions"`).
- Corpus de connaissance concerné : à déterminer — `data/connaissance/doc_app/compagnon-reponses-et-memoire.md`
  si le chemin attendu des questions « actions menées » change.

**Labels :** incident, bot-telegram, agent-interpreteur, us-261
