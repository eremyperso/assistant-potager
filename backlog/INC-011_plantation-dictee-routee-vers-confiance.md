**ID :** INC-011
**Titre :** Une plantation dictée est interprétée comme « /confiance » : quantité, variété et date perdues
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-07

**Reproduction (jeu de test réalisé) :**
Bot Telegram, potager 26. Saisie texte « plantation 9 plants de tomate le 15/05 »,
puis une seconde fois « plantation 9 plants de tomate en date du 15/05 ».
Depuis la réponse obtenue, appui sur « Enregistrer », choix de la parcelle
« planche_centrale », confirmation.

**Résultat obtenu :**
- La phrase n'est pas traitée comme un geste : l'interpréteur de commandes la
  classe par le modèle en commande `/confiance` (journal : `nature=COMMANDE │
  origine=modele │ /confiance │ confiance=0.96`), exécutée comme
  `/confiance tomate plantation 15/05`.
- « 15/05 » est pris pour un nom de parcelle (« Parcelle '15/05' inconnue →
  évaluation au potager ») et la confiance est calculée pour le jour même
  (07/10), pas pour le 15/05.
- L'enregistrement depuis la fiche confiance crée l'événement #555 :
  plantation de tomate **datée du 07/10/2026, sans quantité, sans variété**
  (journal : `qte=None | parcelle=61 | date=2026-10-07`). La variété n'a pas
  été demandée.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Une phrase qui annonce un geste (« plantation 9 plants de tomate le 15/05 ») est
enregistrée comme un geste : plantation de 9 plants de tomate datée du
15/05/2026, avec demande de la parcelle et de la variété si elle n'est pas
dite. Elle ne doit jamais déclencher une évaluation de confiance, ni produire
un événement daté du jour sans quantité.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (aiguillage des messages texte),
  interpréteur de commandes (repli modèle), enregistrement depuis la fiche
  confiance.
- Nature probable : régression logique — le repli « commande » par le modèle
  (priorité 3e de `app/bot/messages.py`) est tenté avant la reconnaissance des
  gestes par le routeur (priorité 4). Le chemin « Enregistrer » depuis la
  confiance (US-179 / CA6) ne reprend ni la date évaluée ni la quantité.
- Fichiers probablement concernés : `app/bot/messages.py`,
  `app/services/interpreteur_commandes.py` (`interpreter`), `llm/routeur.py`
  (`_regle_par_geste`), le flux US-179 / CA6 d'enregistrement depuis la confiance.
- Corpus de connaissance concerné : non.
- Note : un correctif de l'aiguillage est présent dans l'arbre de travail non
  commité de la branche `epic-9-12-refonte-plan-cultures-pepiniere` (le repli
  modèle n'est plus tenté sur une phrase qui s'ouvre sur un geste). Le chemin
  « Enregistrer » depuis la confiance et la question de variété restent à traiter.

**Labels :** incident, bot
