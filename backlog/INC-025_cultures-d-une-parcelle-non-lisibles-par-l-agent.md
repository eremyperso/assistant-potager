**ID :** INC-025
**Titre :** « Donne moi toutes les cultures sur celle-ci » : l'agent ne sait pas lister les cultures d'une parcelle (« Je n'ai pas bien compris »)
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager de recette (id 33), bot Telegram, mode agent d'abord (branche `agent-mode-prioritaire`), le 05/11/2026 :
1. 20:42 « sur quelle parcelle sont les tomates » → « Les tomates sont sur la parcelle **Est**, Emmanuel ! ».
2. 20:43 « donne moi toutes les cultures sur celle-ci » (« celle-ci » = la parcelle Est de la réponse précédente).
3. 20:43 « toutes les cultures sur la parcelle est » (reformulation explicite).
4. 20:43 « oui » (réponse à la proposition de montrer le détail sur le plan).

**Résultat obtenu :**
1. Réponse donnée après `lire parcelle 'tomate' → 0 résultat` puis `lire parcelles '' → 6 résultat(s)`. Les relevés de ces lectures ne
   portent a priori que la fiche des parcelles, pas leurs cultures : la provenance de « Est » n'est pas visible dans le journal.
2. Échec : `lire parcelle 'Est' → 2 résultat(s)` (probablement « Est » et « planche test », dont le nom contient « est »),
   puis `lire culture 'Est' → 0` et `lire culture 'planche test' → 0` (des noms de parcelle sont passés comme noms de culture),
   `chercher_connaissance[carnet] → 0 passage`, `annonce d'action sans proposition → texte du code`. Réponse finale :
   « Je n'ai pas bien compris ce que tu voulais faire. Redis-le-moi autrement, je te… » (4 outils, 50 200 jetons, 4,6 s).
3. En reformulant, l'agent répond sans aucun outil (`texte seul`, 8 272 jetons) : « Les tomates sont sur la **Est**, Emmanuel ! Et y'a aussi
   du haricot, du persil e[t]… » puis propose de montrer le détail sur le plan. Le journal enregistre une **question en attente** qui est un
   fragment de la réponse coupé en plein mot (`'ui traînent par là-bas. Tu veux que je te montre tout ça en détail sur le plan ?'`, choix : Est).
4. Après « oui », `afficher → /plan Est` est proposé puis exécuté : le plan de la parcelle donne la liste détaillée.
Le jardinier a dû demander explicitement le détail (messages 3 et 4) pour obtenir la liste des cultures de la parcelle.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- « Donne moi toutes les cultures sur celle-ci », après une réponse qui vient de nommer la parcelle Est, doit donner directement la liste
  des cultures de la parcelle Est (ou proposer immédiatement `/plan Est` à confirmer), sans « Je n'ai pas bien compris » et sans
  que le jardinier ait à reformuler.
- Le renvoi « celle-ci » doit être résolu d'après l'échange précédent.
- Une liste de cultures annoncée par l'agent doit venir d'une lecture des données du potager, pas d'un texte rédigé sans outil.
- Le premier message (« sur quelle parcelle sont les tomates ») doit s'appuyer sur une lecture qui relie cultures et parcelles.
  Si possible, la réponse à la première question donne déjà ce qu'il faut (parcelle et cultures voisines) ou propose le plan.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend, couche agent (outil de lecture et catalogue d'outils).
- Nature probable : lacune de conception, à investiguer. L'outil `lire` expose `parcelle` (fiche de la parcelle : nom et champs typés),
  `culture` (noms de cultures issus du stock), `lot` et `actions`, mais aucune lecture ne relie une culture à sa parcelle ni ne liste
  les cultures d'une parcelle. Le filtre de `lire parcelle <nom>` est par sous-chaîne sur le nom normalisé, ce qui explique les 2 résultats
  pour « Est » (« planche test » contient « est »). Faute de lecture adaptée, le modèle essaie des outils qui ne répondent pas
  (`culture` avec un nom de parcelle), puis abandonne, ou répond sans outil à partir de ce qu'il a en contexte.
- Fichiers probablement concernés : `app/services/agent/lecture.py` (`_lire`, filtre par sous-chaîne, absence de lecture parcelle→cultures),
  `app/services/agent/catalogue_outils.py` (description de l'outil `lire`, valeurs de `quoi`), `app/services/agent/validation.py`
  (règle « annonce d'action sans proposition → texte du code »), `app/services/agent/interpreteur_agent.py` (contexte court et
  résolution du renvoi « celle-ci »).
- Corpus de connaissance concerné : à vérifier à la correction. Si l'outil de lecture ou la façon d'interroger le potager change,
  relire les fiches de `data/connaissance/doc_app/` sur le compagnon et le plan (voir CLAUDE.md, section « Corpus de connaissance »).
- Famille voisine : INC-022 (réponse de l'agent sans relevé derrière), INC-023 (fragment de réponse enregistré comme question en attente,
  même symptôme ici : à traiter ensemble), INC-019 (question non routée vers l'agent).

**Labels :** incident, agent, parcelles, lecture
