**ID :** INC-027
**Titre :** « quels sont mes semis en pépinière froide ? » : l'agent répond « Aucun lot » sans avoir consulté le potager, alors que des semis existent
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-06

**Reproduction (jeu de test réalisé) :**
Sur la dernière version (branche `agent-mode-prioritaire`, modèle `mistral/mistral-small-2603`), dans le bot Telegram, potager 33 :
1. Message texte : « quels sont mes semis en pépinière froide ? ».
2. Message texte suivant : « affiches moi mes lots ».
Même comportement constaté dans le compagnon de la PWA (`/compagnon/messages`).
Vérification : dans la PWA (vue Pépinière), des semis de courgettes jaunes sont bien en cours.

Extrait du journal du bot (11:46:46 → 11:48:10) :
- `AGENT : conversation — 5 échange(s)` puis UN SEUL appel `LLM agent` (`in=8806 out=27`).
- `AGENT : texte seul → aucune proposition │ "Aucun lot en pépinière froide pour l'instant, Emmanuel ! Tu veux en créer un ou "`.
- `AGENT : question en attente — « …ère froide pour l'instant… » (choix : aucun nommé)`.
- Au message suivant : deux appels `LLM agent`, `afficher → /lot`, commande `/lot` confirmée et exécutée (`[US-209] /lot — liste (toutes cultures)`).

**Résultat obtenu :**
- Pour la question sur la pépinière froide, l'agent répond directement, en texte, « Aucun lot en pépinière froide pour l'instant, Emmanuel ! Tu veux en créer
  un ou vérifier ailleurs ? ». Le journal ne montre aucun appel de l'outil de lecture (`lire`) : une seule requête au modèle, sans outil, avant la réponse.
- La réponse est fausse : des semis de courgettes jaunes sont en cours (visibles dans la vue Pépinière de la PWA et par la commande `/lot`).
- L'agent invite en outre le jardinier à créer un lot, et la réponse est enregistrée comme « question en attente » : la suite de l'échange repose sur une
  donnée inventée.
- Le jardinier ne retrouve ses lots qu'en contournant l'agent, avec la commande `/lot` (« affiches moi mes lots »).

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- Une question sur le contenu du potager (« mes semis », « mes lots », « ma pépinière ») est précédée d'une lecture du potager (outil `lire`), comme le demande
  la consigne 2 du prompt de l'agent (« Consulte d'abord l'outil qui sait… N'invente jamais une donnée »).
- L'agent n'affirme jamais l'absence de lots, de cultures ou de semis sans avoir lu le potager dans le même tour.
- Si les lectures ne permettent pas de répondre, il le dit (« je ne vois pas… ») ou propose `/lot`, sans inviter à créer ce qui existe déjà.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend, couche agent (prompt de l'agent, garde-fous de réponse après le modèle). Se manifeste à l'identique dans le bot
  Telegram et dans le compagnon de la PWA (`/compagnon/messages`), qui passent par le même orchestrateur.
- Nature probable : lacune de conception, à investiguer. Même mécanisme que INC-022 et INC-026 : une réponse `texte seul` sans appel d'outil n'est
  contrôlée par aucun garde-fou (ceux d'US-281 portent sur les relevés des outils). Ici, c'est une affirmation négative (« aucun lot ») sur les données du
  potager, émise sans aucune lecture.
- Fichiers probablement concernés : `app/services/agent/interpreteur_agent.py` (prompt et boucle d'appels), `app/services/agent/validation.py` (garde-fous
  après le modèle), `app/services/compagnon/orchestrateur.py`.
- Piste connexe, hors périmètre de cette fiche : même avec une lecture, `lire lot` (`app/services/agent/lecture.py`) ne renvoie ni l'emplacement courant ni le
  type de pépinière (chaude/froide) du lot, donc une question « en pépinière froide » ne pourrait pas être filtrée correctement. À traiter dans une fiche
  séparée si on le décide.
- Voir aussi : INC-022 (réponse inventée sans outil), INC-025 (lecture insuffisante pour l'agent), INC-026 (lot et parcelle inventés sans lecture).
- Corpus de connaissance concerné : non, sauf si la correction change le comportement décrit dans la fiche `doc_app/compagnon-reponses-et-memoire.md` (à relire
  alors, règle US-099 / CA9).

**Labels :** incident, backend, agent
