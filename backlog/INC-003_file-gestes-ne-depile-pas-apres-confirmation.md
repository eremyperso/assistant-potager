**ID :** INC-003
**Titre :** La commande `gestes` ne dépile pas après confirmation d'un geste
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-21

**Reproduction (jeu de test réalisé) :**
Sur implémentation d'US-224 (file de gestes en attente). Depuis le compagnon
Telegram, l'utilisateur relance le traitement de la file avec la commande
`gestes`. La file contient plusieurs gestes en attente. Le premier geste
présenté (id=5, « 1/2 ») est traité (quantité renseignée, puis confirmé —
DB SAVE id=515). L'utilisateur relance ensuite la commande `gestes`.

**Résultat obtenu :**
Après confirmation du premier geste, l'utilisateur n'a pas accès au second
geste de la file. Pire : en relançant la commande `gestes`, il retrouve à
nouveau **tous** les gestes, y compris ceux déjà confirmés/traités. Le journal
montre le même geste id=5 présenté deux fois de suite en « 1/2 » (22:09:31 puis
22:09:50), alors qu'un item (id=516 puis id=517) vient d'être enregistré en
base entre les deux.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Conformément à US-224 CA8 et CA9 : un geste n'est retiré de la file qu'à la
confirmation ou à l'abandon explicite (donc un geste confirmé doit disparaître
de la file au prochain appel de `gestes`), et après confirmation d'un geste,
le compagnon doit annoncer ce qu'il reste et proposer le suivant — pas
représenter le même geste ni la totalité de la file depuis le début.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (`app/bot/file_gestes.py`) et couche
  métier associée (`app/services/file_gestes.py`)
- Nature probable : régression logique — la sortie de file à la confirmation
  (marquage de l'état, cf. `_requete_en_attente`, `ETAT_EN_ATTENTE` et la
  fonction qui marque un geste « sorti » dans `app/services/file_gestes.py`)
  ne semble pas prise en compte par l'enchaînement/la présentation du geste
  suivant côté bot (`[US-224 / CA6] Geste de la file présenté à la
  confirmation`, `app/bot/file_gestes.py`)
- Fichiers probablement concernés : `app/bot/file_gestes.py`,
  `app/services/file_gestes.py`
- Corpus de connaissance concerné : non (pas de mise à jour de fiche de
  `data/connaissance/` a priori — sujet backend/bot en cours d'implémentation
  d'US-224, non encore documenté comme acquis)

**Labels :** incident, bot, backend
