**ID :** INC-023
**Titre :** Clore un lot de semis : l'agent annonce une clôture mais exécute `/lot 1` (consultation), et la clôture n'existe que comme geste
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager de recette (id 33), bot Telegram, mode agent d'abord (branche `agent-mode-prioritaire`),
le 05/11/2026, trois essais dans la même conversation :
1. 17:07 « Peux tu clore ou fermer le lot 1 ? » puis confirmation de la proposition.
2. 17:08 « Donne moi l'état de mes lots en pépinière ».
3. 17:09 « Comment terminer ou clore un lot de semis ? ».
4. Pour comparaison, 17:22 : la clôture du lot 1 par le geste, depuis la file de gestes (US-224).

**Résultat obtenu :**
1. L'agent répond « Je te propose de clore le lot 1 de pépinière, Emmanuel. Tu confirmes ? ». Le journal montre pourtant
   que la commande rangée est `/lot 1` (`regle=afficher`, proposition id=267). À la confirmation :
   `Exécution de la commande interprétée : /lot 1`, puis `/lot 1 consulté`. Rien n'est clos : le bot a annoncé une
   clôture et exécuté une simple consultation.
2. La liste des lots répond correctement (trois lots en pépinière).
3. L'agent interroge la documentation (`chercher_connaissance[application]`, fiche `pepiniere-par-lot.md`) et répond
   « Dis-moi juste le nu[méro]… ils ont levé, je te guide ! ». Il demande donc le nombre de plants levés, alors que
   la commande `/lot` ne propose aucune action de clôture. Le jardinier ne trouve pas de clôture depuis `/lot`.
   Le journal enregistre ensuite une **question en attente** qui est un fragment de la réponse, coupé en plein mot :
   `'ts ont levé, je te guide ! Source : La pépinière, lot de semis par lot de semis.'` (choix : aucun nommé).
   La ligne de source fait partie du texte retenu.
4. Par le geste, la clôture fonctionne : `Geste cloture_lot rattaché au lot n° 1 (semis 640)`, récapitulatif à confirmer,
   `Clôture du lot 1 (courgette) : 16 godet(s) et 0 graine(s) soldés`, enregistrement id=668 (`action=cloture_lot`,
   16 plants), proposition id=269 confirmée.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- Dire « clos le lot 1 » ou « Peux tu clore ou fermer le lot 1 ? » doit donner le même comportement que le geste :
  un récapitulatif à confirmer qui énonce la clôture (« clôture du lot 1 (courgette) — 16 godets et 0 graine soldés »,
  définitive), puis l'enregistrement `cloture_lot`. Le jardinier ne doit pas avoir à passer par la file de gestes.
- L'agent ne doit jamais annoncer une action (« clore ») qu'il n'exécute pas : la commande proposée doit correspondre
  à la phrase affichée. Aujourd'hui `/lot 1` est proposé sous un libellé de clôture.
- Une question en attente ne doit pas être un fragment de réponse coupé en plein mot ni contenir la ligne de source.
- Piste de correction proposée par le jardinier, à instruire par le Developer sans préjuger : faire de la clôture une
  action de la commande `/lot` (`/lot clore <n>`), déclarée dans le menu des commandes dictables, pour que l'interpréteur
  de commandes puisse renvoyer la bonne commande.
  Points de vigilance de cette piste : appeler le même service que le geste (pas de seconde logique de clôture),
  confirmation obligatoire, action définitive donc non exécutable sur un rapprochement approché de numéro de lot,
  parité menu/CI (`controler_parite`) et documentation de la commande modifiée (aide, menu natif, guide utilisateur,
  fiche `doc_app` et RAG).

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (commande `/lot`, flux d'enregistrement du geste `cloture_lot`) ; API/Backend
  (couche agent et déclaration des commandes dictables).
- Nature probable : lacune de conception. Le grep ne trouve aucune forme de commande de clôture dans la couche agent,
  le menu des commandes dictables ni l'interpréteur de commandes ; `cloture_lot` n'existe que comme action de geste
  (`utils/actions.py`, `app/bot/enregistrement.py`, `app/bot/saisie.py`). Faute d'outil adapté, l'agent s'est rabattu
  sur `afficher`, la forme la plus proche, et son texte annonce autre chose. Le fragment de question en attente est
  un défaut distinct (même symptôme que sur la réponse « mildiou » du 05/11), à investiguer.
- Fichiers probablement concernés : `app/services/menu_commandes.py` (déclaration des formes de commande),
  `app/services/interpreteur_commandes.py`, `app/services/agent/validation.py` et `app/services/agent/catalogue_outils.py`
  (cohérence entre texte annoncé et commande proposée), `app/bot/interpretation.py` (exécution par introspection),
  `app/bot/enregistrement.py` (récapitulatif de clôture), `app/services/lots_pepiniere.py` (service de clôture, US-216),
  `app/services/agent/interpreteur_agent.py` (enregistrement de la question en attente).
- Corpus de connaissance concerné : oui — `data/connaissance/doc_app/` (fiche `pepiniere-par-lot.md` : la clôture
  se dicte, et la commande `/lot` est modifiée), ainsi que l'aide `/help`, le guide utilisateur (deux copies) et `SETUP`
  (voir CLAUDE.md, section « Corpus de connaissance » : la fiche se met à jour dans la même livraison).
- Famille voisine : INC-019 (question non routée vers l'agent) ; INC-021 et INC-022 (réponse de l'agent non ancrée
  dans une donnée réelle du potager).

**Labels :** incident, agent, bot-telegram, pepiniere, commandes
