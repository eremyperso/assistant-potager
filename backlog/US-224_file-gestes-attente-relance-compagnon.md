**ID :** US-224
**Titre :** Déposer un geste depuis la PWA dans une file d'attente et le confirmer au compagnon quand on veut
**Épic :** ÉPIC 9 — Socle commun Plan, Cultures, Pépinière *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que les gestes lancés depuis l'application s'accumulent dans une file d'attente, et que mon compagnon me propose de les traiter quand je suis disponible
Afin de préparer mes enregistrements au calme devant l'écran et de les confirmer plus tard, sans perdre ce que j'ai préparé si je ne réponds pas tout de suite

**Contexte fonctionnel :**

US-196 a posé le principe juste — *la PWA prépare, le compagnon confirme, rien n'est écrit avant « Confirmer »* — mais avec un véhicule qui ne tient pas à l'usage : **un lien à usage unique, valable quinze minutes**.

Trois conséquences constatées sur l'implémentation livrée :

1. Le lien est **consommé à l'ouverture**, pas à la confirmation. Appuyer sur « Annuler » dans le récapitulatif brûle le geste : rouvrir le lien répond « déjà utilisé ».
2. Le récapitulatif du bot expire au bout de **60 secondes** (règle d'US-021, reprise telle quelle par US-196 / CA8). Une minute d'hésitation, un appel qui passe, et le geste est perdu de la même façon.
3. Dans les deux cas, **il n'y a rien à rejouer depuis Telegram**. La seule issue est de revenir dans l'application et de rappuyer sur le bouton — exactement le détour que l'US voulait supprimer.

Le modèle sous-jacent est en cause, pas son implémentation : *un laissez-passer de quinze minutes* suppose que le jardinier bascule immédiatement vers Telegram et confirme du premier coup. Or on prépare ses gestes devant l'écran, souvent plusieurs à la suite, et on les confirme quand on a les mains libres.

Cette US remplace le laissez-passer par une **file de gestes en attente** : ce que la PWA dépose y reste jusqu'à confirmation ou abandon explicite, le compagnon **invite** à la traiter, et le jardinier la reprend quand il veut — depuis la notification, depuis un lien, ou de lui-même.

Ce qui ne change pas, et qui reste acquis d'US-196 : la PWA n'écrit rien ; l'écriture reste le flux de confirmation du bot (US-021), avec ses avertissements de rotation (US-167) et ses questions de parcelle ou de quantité ; le geste part pré-parsé, donc à zéro jeton ; les rôles (US-047) et le potager d'origine (US-088) gouvernent comme avant.

⚖️ **Arbitrage A16 reconduit** : un formulaire de saisie web branché sur le même service reste hors périmètre — il créerait un second chemin d'écriture, que les wireframes excluent. La file n'en est pas un : elle ne fait qu'attendre.

**Ce que cette US remplace dans US-196 :**

| CA d'US-196 | Devenir |
|---|---|
| CA3 (usage unique, 15 minutes) | **Remplacé** — voir CA3 et CA8 ci-dessous |
| CA6 (refus du code : expiré, déjà servi) | **Remplacé** — voir CA12 |
| CA8 (état en attente de 15 minutes) | **Remplacé** — voir CA8 |
| CA10 (activation du compagnon avant toute préparation) | **Inversé** — voir CA21 |
| CA12 (relecture de l'écran au retour) | **Étendu** — voir CA22 |
| CA1, CA2, CA5, CA7, CA9, CA11, CA13, CA15, CA16, CA17 | **Conservés tels quels** |

**Critères d'acceptance :**

*La file*

- [ ] CA1 : Un geste lancé depuis un écran est **déposé** dans une file d'attente propre au compte et au potager consulté, au lieu d'ouvrir un laissez-passer. Le dépôt n'écrit aucun événement : la file n'apparaît ni au Journal, ni dans un stock, ni dans une statistique
- [ ] CA2 : Un geste en attente porte tout ce que l'écran savait — geste, culture, variété, quantité, unité, parcelle, rang, lot, filière de semis, date, écran d'origine — et l'instant de son dépôt
- [ ] CA3 : Un geste en attente vit **3 jours à compter de son propre dépôt**, puis il est purgé. La péremption se compte **par geste**, jamais par pile : un geste déposé le troisième jour n'est pas emporté par la purge de ceux du premier. Tant qu'il n'est ni confirmé, ni abandonné, ni périmé, un geste reste disponible — annuler un récapitulatif ne le retire pas
- [ ] CA4 : Déposer deux fois le même geste (même action, même culture, même parcelle, même jour) est **signalé mais pas interdit** : l'écran dit qu'un geste identique attend déjà. Semer deux fois la même chose le même jour est un cas réel

*Ce que le compagnon présente*

- [ ] CA5 : La présentation a **deux niveaux**, et le premier ne peut rien écrire. Niveau 1, **la file** : le nombre de gestes en attente et le détail des trois premiers (geste, culture, parcelle, date), puis « et N autres » ; deux actions seulement — commencer, ou couper les relances. Aucune action de ce niveau n'enregistre quoi que ce soit.

  Ces deux actions sont des **boutons**, pas des commandes à retaper. ⚠️ L'envoi sortant du compagnon ne sait aujourd'hui poster que du **texte brut**, sans clavier : il doit être étendu, faute de quoi toute invitation dégénère en « envoyez /gestes pour les traiter » et perd l'essentiel de son intérêt. Constaté à l'envoi d'un message de test sur l'environnement de dev, le 21/09/2026
- [ ] CA6 : Niveau 2, **le geste** : le récapitulatif existant d'US-021, inchangé — avertissement de rotation (US-167), parcelle ou quantité demandée si elle manque —, précédé de sa position (« geste 1 sur 3 »). Zéro jeton
- [ ] CA7 : Le geste offre **trois issues nommées sans ambiguïté** : *Confirmer* (enregistre et retire de la file), *Plus tard* (repose le geste dans la file, et le dit), *Abandonner ce geste* (le retire définitivement, et le dit). Le libellé « Annuler » d'aujourd'hui disparaît de ce flux : il ne permet pas de distinguer « j'annule la confirmation » de « j'annule le geste »
- [ ] CA8 : Un geste n'est retiré de la file **qu'à la confirmation ou à l'abandon explicite**. « Plus tard », un délai de confirmation dépassé, une conversation refermée, une relance ignorée : dans tous ces cas le geste est toujours là
- [ ] CA9 : Traiter plusieurs gestes à la suite ne redemande pas le contexte à chaque fois : après confirmation, le compagnon annonce ce qui reste et propose **le suivant**. Le jardinier peut s'arrêter à tout moment, le reste demeure en attente
- [ ] CA10 : Le jardinier reprend sa file quand il veut, **sans dépendre d'une notification** : une commande de consultation du bot ouvre le niveau 1. Elle est déclarée dictable au titre d'US-172 — c'est une consultation, pas un code à coller —, sans quoi le contrôle de parité des commandes échoue
- [ ] CA11 : Un lien reçu depuis l'application ouvre **directement le geste qu'il désigne** (niveau 2), sans passer par la file. Le lien reste valide tant que le geste l'est : il n'est plus à usage unique
- [ ] CA12 : Un geste dont le contexte a disparu entre le dépôt et la confirmation — parcelle supprimée, lot inconnu, potager archivé ou quitté, rôle devenu lecteur — est **refusé en clair, avec son motif**, et retiré de la file. Jamais d'écriture silencieuse, jamais un geste fantôme qui échoue à chaque reprise
- [ ] CA13 : Le geste s'enregistre dans le potager de son dépôt. Si le potager actif du compagnon est un autre, la bascule est nommée et faite (US-088). Quand la file couvre plusieurs potagers, le niveau 1 les groupe par potager

*La relance, et sa fin*

- [ ] CA14 : Le compagnon **invite** à traiter la file — il ne l'exécute jamais de lui-même. Une invitation part **au premier dépôt sur une file vide**, et une seule : les gestes déposés à la suite, pendant la même session de préparation, n'en déclenchent aucune autre
- [ ] CA15 : Tant que la file n'est pas vide, la relance est **semestrielle au sens propre du terme — toutes les demi-journées** —, posée sur deux créneaux quotidiens plausibles (matin, fin d'après-midi) et jamais à l'heure exacte du dépôt : un geste déposé à 15 h ne réveille personne à 3 h du matin
- [ ] CA16 : Les relances **s'arrêtent au bout de 3 jours**, qu'elles aient été suivies d'effet ou non. Passé ce délai, le compagnon se tait jusqu'à l'avertissement du CA17
- [ ] CA17 : **4 heures avant la purge d'un geste**, un dernier message l'annonce — ton distinct d'une relance ordinaire, puisqu'il annonce une perte : il nomme les gestes concernés et laisse une dernière occasion de les traiter
- [ ] CA18 : À la purge, une notification **dit ce qui a été vidé** et ce que cela décrivait. Rien ne disparaît en silence : un geste préparé et jamais confirmé doit laisser une trace de son sort, sans quoi le jardinier croira l'avoir enregistré.

  ⚠️ L'envoi sortant est **best-effort** : il n'échoue jamais bruyamment, un message perdu l'est sans bruit. Acceptable pour une relance — il y en aura une autre — mais **pas pour cette notification-ci**, qui n'a pas de seconde chance et dont la perte produit exactement le malentendu que le CA18 veut éviter. L'échec d'envoi est donc journalisé, et l'information portée **aussi** par l'application : un geste purgé y reste visible comme tel, le temps d'être vu
- [ ] CA19 : Toute activité sur la file — confirmation, abandon, simple consultation — **remet le compteur de relance à zéro**. Elle ne rallonge en revanche jamais la vie d'un geste : la péremption du CA3 court depuis le dépôt, et rien ne la repousse
- [ ] CA20 : Chaque relance **remplace la précédente** dans la conversation au lieu d'empiler des bulles identiques. Le jardinier peut **couper les relances** sans vider sa file : les gestes restent, les invitations cessent, l'avertissement du CA17 et la notification du CA18 aussi — le réglage se dit et se défait depuis le compagnon

*Dans l'application*

- [ ] CA21 : Sans compagnon activé, le dépôt **reste possible** et la file se remplit ; l'application invite à activer le compagnon pour pouvoir confirmer, sans bloquer le dépôt. C'est l'inverse d'US-196 / CA10, et c'est voulu : on prépare sa journée d'abord, on active une fois
- [ ] CA22 : L'application montre **combien de gestes attendent**, en permanence et sur tous les écrans concernés — une file invisible serait une file oubliée. Au retour sur l'onglet, ce compte et l'écran concerné sont relus **une fois**, sans interrogation périodique
- [ ] CA23 : On peut **consulter la file et en retirer un geste** depuis l'application, sans passer par le compagnon. On ne peut pas l'y confirmer : la confirmation reste au compagnon (arbitrage A16)
- [ ] CA24 : Un membre en lecture seule ne dépose rien et ne voit aucun bouton d'action (inchangé, US-196 / CA11)

*La date du geste*

- [ ] CA25 : Un geste confirmé trois jours après son dépôt porte la date de son **dépôt**, pas celle de sa confirmation : c'est le jour où le jardinier a agi au potager. Le récapitulatif l'affiche en clair et permet de la corriger
- [ ] CA26 : La règle « un geste ne se date jamais dans le futur » (US-196 / CA14) reste entière au moment du dépôt ⚖️ **à trancher — le mot « programmé » du besoin est ambigu** : une file *asynchrone* (je prépare maintenant, je confirme plus tard un geste déjà fait) et une file *programmée* (je planifie un semis pour samedi prochain) sont deux fonctionnalités différentes. La seconde suppose des gestes à venir, donc une notion de « prévu » distincte de « fait », qui touche le stock, le plan et les statistiques. **Proposition : rester sur l'asynchrone dans cette US**, et cadrer la programmation à part si le besoin est bien celui-là

*Définition de terminé*

- [ ] CA27 : Fiches du corpus corrigées dans la même livraison (US-099 / CA9) : `compagnon-telegram.md` (la file, sa reprise, les relances, leur coupure et la purge), `enregistrer-un-geste.md` (un geste préparé attend trois jours, il ne se perd pas en cours de route). Les fiches de domaine concernées décrivent la file, la règle de consommation à la confirmation et la cadence de relance
- [ ] CA28 : Des tests couvrent : dépôt sans écriture, confirmation qui retire de la file, « Plus tard » qui l'y laisse, délai de confirmation dépassé qui l'y laisse, abandon explicite, péremption par geste et non par pile, avertissement 4 h avant, notification de purge, parcelle disparue, potager quitté, rôle devenu lecteur, doublon signalé, enchaînement de plusieurs gestes, invitation unique au premier dépôt, cadence et arrêt à 3 jours, remise à zéro du compteur sur activité, relances coupées sans perte de file, zéro jeton

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement, consultation
- Migration BDD requise : **oui** — la table d'intentions d'US-196 évolue en file : la péremption courte passe à 3 jours, l'état d'un geste (en attente / confirmé / abandonné / périmé) et son motif de refus apparaissent, le réglage de relance, la trace de la dernière invitation et l'identifiant du message de relance à remplacer sont à loger. Migration avec rollback
- Dépendances : US-196 (préparation d'un geste, dont cette US remplace le véhicule), US-045 et US-091 (liaison et lien profond), US-021 (confirmation), US-167 (rotation), US-088 (potager actif), US-047 (rôles), US-172 (parité des commandes, pour la commande de consultation du CA10) — toutes livrées. Les notifications sortantes du compagnon existent déjà (US-085 à US-087), et le bot a déjà un rendez-vous quotidien planifié (job météo) sur lequel adosser les créneaux du CA15
- Consommateurs suivants : inchangés — US-201 (rang libre), US-216 (gestes d'un lot), US-217 (mettre en terre ici), US-218 (semer maintenant)
- Impact tokens : zéro — l'item arrive pré-parsé, invitations et avertissements sont des gabarits texte
- **Vérifié sur l'environnement de dev le 21/09/2026** : l'envoi sortant vers une conversation liée fonctionne déjà et se déclenche depuis n'importe quel processus — l'API, un travail planifié —, sans passer par la boucle d'écoute du bot. Les relances de cette US n'ont donc pas de brique à créer, seulement deux manques à combler (clavier au CA5, fiabilité au CA18). Un message de test a été reçu sur le bot de dev
- Point de vigilance : l'envoi suppose une conversation **déjà ouverte par le jardinier**. Telegram interdit au bot de parler le premier tant que « Démarrer » n'a pas été pressé : un compte lié mais jamais démarré ne recevra aucune relance, sans que rien ne le signale côté serveur (déjà décrit dans la fiche `compagnon-telegram.md`)
- Point de vigilance : **la relance reste le risque principal de cette US.** La règle retenue donne au pire 5 relances, 1 avertissement et 1 notification de purge sur trois jours pour une file jamais traitée — borné, mais à mesurer à l'usage avant d'être figé. Le CA20 (coupure) est la soupape, il ne doit jamais être difficile à trouver
- Point de vigilance : la péremption par geste (CA3) est ce qui empêche une file entretenue en permanence de devenir immortelle. Confirmer un geste ne doit jamais prolonger les autres
- Point de vigilance : une file qui se remplit sans jamais se vider est le symptôme d'un compagnon non activé ou d'un jardinier qui ne veut pas de Telegram. Le CA21 l'accompagne, il ne le masque pas
- Point de vigilance : le lien profond ne transporte toujours **que** le code du geste — aucun nom de culture, aucune donnée du potager dans l'adresse ni dans les journaux du serveur web
- Point de vigilance : l'estimation est au plafond de l'échelle. Un découpage en deux livraisons est possible et recommandé — **(a)** la file, sa présentation à deux niveaux et sa reprise (CA1 à CA13, CA21 à CA26), **(b)** la relance, son arrêt, l'avertissement et la purge (CA14 à CA20). La première a de la valeur seule : elle suffit à ne plus perdre un geste

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Une seule invitation pour une session de préparation
  Given ma file de gestes est vide
  When je dépose quatre gestes depuis l'application en quelques minutes
  Then mon compagnon m'envoie une seule invitation
  And elle annonce les gestes qui m'attendent

Scénario: Un geste reposé reste disponible
  Given mon compagnon me présente le récapitulatif d'un semis d'épinard
  When j'appuie sur "Plus tard"
  Then il me dit que le geste reste en attente
  And je le retrouve en reprenant ma file

Scénario: Traiter plusieurs gestes d'affilée
  Given trois gestes en attente
  When je confirme le premier
  Then mon compagnon m'annonce qu'il en reste deux
  And il me propose le suivant

Scénario: Le délai de confirmation passe
  Given un geste en attente dont le récapitulatif est affiché depuis deux minutes
  When le délai de confirmation est dépassé
  Then le compagnon me dit que la confirmation a expiré
  And le geste est toujours dans ma file

Scénario: Les relances s'arrêtent au bout de trois jours
  Given un geste déposé il y a trois jours et jamais traité
  When le troisième jour s'achève
  Then mon compagnon cesse de me relancer

Scénario: Avertissement avant la purge
  Given un geste qui sera purgé dans quatre heures
  When l'échéance approche
  Then mon compagnon m'annonce que ce geste va être vidé
  And il me laisse une dernière occasion de le traiter

Scénario: Purge annoncée
  Given deux gestes jamais traités arrivés au terme de leurs trois jours
  When ils sont purgés
  Then mon compagnon me dit lesquels ont été vidés
  And rien n'a été enregistré

Scénario: La péremption se compte par geste
  Given un geste déposé lundi et un autre déposé mercredi
  When la purge emporte celui de lundi
  Then celui de mercredi est toujours en attente

Scénario: La date est celle du dépôt
  Given un geste déposé le 19 septembre
  When je le confirme le 21 septembre
  Then l'événement enregistré porte la date du 19 septembre
  And le récapitulatif me l'a montrée avant que je confirme

Scénario: Couper les relances sans perdre sa file
  Given quatre gestes en attente
  When je demande à mon compagnon de ne plus me relancer
  Then il cesse de m'inviter
  And mes quatre gestes sont toujours là quand je reviens les chercher

Scénario: Déposer sans compagnon activé
  Given mon compte n'est lié à aucune conversation Telegram
  When je lance un geste depuis l'application
  Then le geste est déposé dans ma file
  And l'application m'invite à activer mon compagnon pour pouvoir le confirmer
```

**Labels GitHub :** `us`, `backend`, `bot`, `frontend`, `pwa`, `notification`
