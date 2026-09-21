---
titre: Le compagnon de terrain sur Telegram
famille: doc_app
source: Guide de l'Assistant Potager
niveau_confiance: verifie
index_terms:
  - "activation"
  - "liaison"
  - "synthèse vocale"
  - "geste lancé depuis l'application"
---

# Le compagnon de terrain sur Telegram

## Activer le compagnon de terrain depuis son compte

**Intention :** procédure
**On parle aussi de :** relier ; connecter le bot ; activation ; premier lancement ; code de liaison

L'application web propose d'activer le compagnon de terrain en un seul geste : le bouton ouvre la conversation, et il suffit alors d'appuyer sur Démarrer pour que le lien avec le compte soit établi. Un code de liaison, valable dix minutes et utilisable une seule fois, peut aussi être saisi à la main dans la conversation si le bouton ne fonctionne pas. Une même conversation ne peut être reliée qu'à un seul compte.

## Pourquoi il faut appuyer sur Démarrer

**Intention :** comprendre
**On parle aussi de :** pas de notification ; rappels qui n'arrivent pas ; bouton démarrer ; autoriser les messages

Un assistant sur messagerie ne peut jamais engager la conversation le premier : tant que le bouton Démarrer n'a pas été pressé, aucun message ne peut être envoyé, pas même un rappel d'arrosage ou une alerte de gel. C'est pour cela que l'activation passe par l'ouverture de la conversation plutôt que par un simple formulaire, et pourquoi un compte relié qui ne reçoit rien a presque toujours sauté cette étape.

## Se faire répondre à la voix plutôt qu'au texte

**Intention :** procédure
**On parle aussi de :** synthèse vocale ; réponse audio ; écouter ; mains occupées ; couper le son

Les réponses peuvent être lues à voix haute plutôt qu'écrites, ce qui rend service quand on a les mains dans la terre et le téléphone au fond d'une poche. La lecture s'active et se coupe à la demande, et son état se rappelle au démarrage de la conversation. Le texte reste envoyé dans tous les cas : la voix s'ajoute, elle ne remplace rien.

## Détacher la conversation de son compte

**Intention :** procédure
**On parle aussi de :** dissocier ; délier ; changer de téléphone ; se déconnecter ; couper le lien

Le lien entre une conversation et un compte peut être défait à tout moment. La conversation cesse alors d'accéder aux potagers, sans qu'aucune donnée du jardin ne soit perdue : le compte web reste intact, et une nouvelle activation rétablira le lien plus tard, depuis le même appareil ou un autre.

## Lancer un geste depuis l'application et le confirmer ici

**Intention :** procédure
**On parle aussi de :** bouton enregistrer ; depuis le site ; pré-rempli ; confirmer dans la conversation ; enregistrer sans dicter

Les écrans de l'application web proposent, là où ils montrent une culture ou une parcelle, un bouton qui lance le geste correspondant. Ce bouton n'enregistre rien lui-même : il **dépose le geste dans une file d'attente**, avec ce que l'écran savait — la culture, la parcelle, la date. C'est la conversation qui le présente ensuite sur un récapitulatif déjà rempli, qu'il ne reste qu'à confirmer. C'est exactement le parcours d'un geste dicté, sauf qu'on n'a rien eu à dire. À côté du bouton, la phrase équivalente est proposée pour qui préfère la dicter.

Un geste ainsi déposé attend **trois jours**, et il attend vraiment : le lien qui le désigne reste valable tout ce temps, et le rouvrir redonne le même geste. On peut donc en préparer plusieurs devant l'écran, au calme, et les confirmer plus tard, quand on a les mains libres. Un lien ouvert dans une conversation reliée à un autre compte est refusé, et le geste reste chez celui qui l'a préparé.

## Reprendre ses gestes en attente quand on veut

**Intention :** procédure
**On parle aussi de :** mes gestes en attente ; ma file ; gestes à confirmer ; qu'est-ce qui m'attend ; reprendre plus tard

La conversation présente la file en deux temps. D'abord **la file** : combien de gestes attendent, le détail des trois premiers, et deux boutons seulement — commencer, ou couper les rappels. Rien ne s'enregistre à ce niveau-là. Puis **le geste** : le récapitulatif habituel, précédé de sa position (« geste 1 sur 3 »), avec trois issues clairement nommées — *Confirmer*, qui enregistre et retire le geste de la file ; *Plus tard*, qui l'y laisse ; *Abandonner ce geste*, qui le retire sans rien écrire.

Un geste confirmé porte la date de son **dépôt**, pas celle de sa confirmation : c'est le jour où l'on a agi au potager qui compte. Le récapitulatif l'affiche avant qu'on valide.

Il n'est jamais nécessaire d'attendre un rappel : demander ses gestes en attente rouvre la file à tout moment, depuis la conversation, à la voix comme au clavier. Quand plusieurs gestes attendent, ils s'enchaînent — après chaque confirmation, ce qui reste est annoncé et le suivant est proposé. On peut s'arrêter à tout moment : le reste demeure en attente.

Quand la file couvre plusieurs potagers, ils sont présentés groupés, et chaque geste s'enregistre dans le potager où il a été préparé — le potager actif bascule alors, et la conversation le dit.

## À quelle fréquence le compagnon rappelle les gestes en attente, et comment arrêter ses rappels

**Intention :** comprendre
**On parle aussi de :** rappels ; relances ; fréquence des rappels ; trop de messages ; ne plus me relancer ; arrêter les rappels ; couper les notifications ; couper les rappels sur mes gestes en attente

Le compagnon **invite** à traiter la file, il ne la traite jamais de lui-même. Une invitation part au premier geste déposé sur une file vide, et une seule : préparer quatre gestes à la suite n'envoie pas quatre messages. Ensuite, tant que la file n'est pas vide, un rappel par demi-journée, sur deux créneaux — le matin et la fin d'après-midi, jamais à l'heure du dépôt. Chaque rappel remplace le précédent au lieu d'empiler des messages identiques, et les rappels cessent d'eux-mêmes au bout de trois jours.

Toute activité sur la file — confirmer, abandonner, ou simplement la consulter — remet ce compteur à zéro. Elle ne rallonge en revanche jamais la vie d'un geste : les trois jours courent depuis le dépôt, et rien ne les repousse.

Les rappels se coupent d'un bouton, et cela **ne vide pas la file** : les gestes restent, ils sont toujours consultables et confirmables, seules les sollicitations cessent. Le réglage se défait de la même façon.

## Quand un geste préparé est vidé

**Intention :** comprendre
**On parle aussi de :** geste disparu ; jamais confirmé ; trois jours ; purge ; perdu

Quatre heures avant qu'un geste ne soit vidé, un dernier message l'annonce et nomme les gestes concernés — c'est une dernière occasion de les traiter, et le ton diffère d'un simple rappel puisqu'il annonce une perte. À la purge, un message dit ce qui a été vidé et ce que cela décrivait : **rien n'a été enregistré**. L'application le montre également, le temps qu'on en prenne connaissance, parce qu'un geste préparé et jamais confirmé ne doit pas passer pour un geste enregistré.

Chaque geste a sa propre échéance : confirmer un geste ne prolonge pas les autres, et un geste déposé le troisième jour n'est pas emporté avec ceux du premier.

## Enregistrer sans passer par la conversation

**Intention :** comprendre
**On parle aussi de :** sans messagerie ; je n'ai pas Telegram ; uniquement le site

Tout enregistrement passe aujourd'hui par la conversation : c'est elle qui relit le geste et demande la confirmation. Un jardinier qui n'a pas activé son compagnon de terrain peut donc tout consulter depuis l'application web — plan, stocks, pépinière, calendriers — mais rien y inscrire.

Les boutons d'action fonctionnent quand même : le geste est **déposé dans la file**, et l'application invite alors à activer le compagnon pour pouvoir le confirmer. On prépare sa journée d'abord, on active une fois — rien n'est perdu entre les deux. La file se consulte aussi depuis l'application, qui montre en permanence combien de gestes attendent et permet d'en retirer un ; c'est le seul endroit où l'on ne peut pas les confirmer.
