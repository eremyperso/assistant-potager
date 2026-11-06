**ID :** INC-026
**Titre :** « je veux cloturer le lot 2 » : l'agent invente un lot (« tomate jaune ») et une parcelle (« principal ») sans lire le lot demandé
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager de recette (id 33), bot Telegram, mode agent d'abord (branche `agent-mode-prioritaire`), le 05/11/2026 à 21:59,
conversation de 2 échanges :
1. Message libre « je veux cloturer le lot 2 ».

**Résultat obtenu :**
Réponse : « Tu veux cloturer le lot de tomate jaune sur la parcelle **principal** ? ».
Le journal montre `texte seul → aucune proposition`, `LLM agent … out=18` : le modèle n'a appelé aucun outil, ni `lire` sur les lots ni
aucune autre lecture. La culture (« tomate jaune ») et la parcelle (« principal ») qu'il énonce n'ont donc aucune source dans les données lues.
Le jardinier indique que le lot 2 n'a jamais été repiqué ni planté sur la parcelle « principal » : la question de confirmation
repose sur une donnée inventée, sans rapport avec le lot 2.
Le bot enregistre ensuite cette phrase comme **question en attente** (`question en attente — 'Tu veux cloturer le lot de tomate jaune sur
la parcelle **principal** ?' (choix : principal)`) : une réponse « oui » du jardinier se rattacherait à cette question inventée.
Le journal montre aussi, avant l'appel du modèle, une lecture de la météo (`MÉTÉO HISTORIQUE` puis `MÉTÉO APPEL`, 369 ms) qui n'a
aucun rapport avec une demande de clôture de lot.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- Pour « je veux cloturer le lot 2 », l'agent lit d'abord le lot 2 (outil `lire` sur les lots), puis propose la clôture de CE lot,
  avec ses données réelles (culture, nombre de godets et de graines soldés), à confirmer, comme le fait le geste de clôture
  (voir INC-023).
- L'agent ne doit jamais énoncer une culture, un numéro de lot ou une parcelle qui ne viennent pas d'une lecture des données du potager.
  S'il ne peut pas lire le lot demandé, il le dit au lieu de poser une question qui contient des valeurs inventées.
- Une question de confirmation ne doit pas être enregistrée en attente quand elle contient des valeurs qu'aucun outil n'a rendues.
- La météo n'est pas consultée pour une demande de clôture de lot.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend, couche agent (consigne de l'agent, garde-fous de réponse, contexte préchargé).
- Nature probable : lacune de conception, à investiguer. Même mécanisme que INC-022 : une réponse `texte seul` sans outil n'est
  contrôlée par aucun garde-fou, car ceux-ci portent sur les relevés des outils (chiffres, lieux) et il n'y en a pas.
  Le prompt de l'agent demande de consulter l'outil avant de répondre à une question, mais pas pour un énoncé de ce type (une demande
  d'action déguisée en question). L'absence d'une commande de clôture dictable (INC-023) laisse en plus l'agent sans proposition à faire.
- Fichiers probablement concernés : `app/services/agent/interpreteur_agent.py` (consigne, contexte préchargé dont la météo,
  enregistrement de la question en attente), `app/services/agent/validation.py` et `app/services/agent/savoir.py` (garde-fous sur
  les valeurs énoncées sans relevé), `app/services/agent/catalogue_outils.py` (outil `lire` sur les lots).
- Corpus de connaissance concerné : à vérifier à la correction (voir CLAUDE.md, section « Corpus de connaissance »).
- Famille voisine : INC-022 (réponse sans relevé, ville inventée), INC-023 (clôture de lot non dictable, fragment de question
  en attente), INC-025 (l'agent ne sait pas relier cultures et parcelles). À traiter de préférence avec INC-023.

**Labels :** incident, agent, pepiniere, lots
