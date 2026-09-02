**ID :** US-171  
**Titre :** Remplacer le clavier de raccourcis permanent par le menu de commandes natif Telegram

**Story :**
En tant que jardinier
Je veux ouvrir le menu « Menu » de Telegram et y trouver la liste de toutes les commandes du bot, chacune avec son icône et sa courte phrase d'aide, plutôt qu'une grille de boutons qui occupe en permanence le bas de mon écran
Afin de garder l'écran de conversation entier pour mes échanges avec le bot, et de découvrir l'ensemble des commandes disponibles au même endroit au lieu d'un sous-ensemble arbitraire

**Critères d'acceptance :**

*Le menu natif devient le point d'entrée des commandes*
- [ ] CA1 : Le bot déclare auprès de Telegram la liste de ses commandes, de sorte que le bouton « Menu » à gauche de la zone de saisie ouvre la liste verticale des commandes, une par ligne, chacune avec son libellé `/commande` et une phrase d'aide courte — le rendu de référence est celui des bots Telegram grand public (capture ChatGPT 5 fournie le 02/09/2026)
- [ ] CA2 : Chaque commande déclarée porte une description d'une ligne, en français, formulée à l'intention du jardinier et non à celle du développeur ; elle tient dans la largeur d'un écran mobile 375 px sans troncature
- [ ] CA3 : Les commandes du quotidien figurent **toutes** dans le menu, pas seulement celles qui avaient un bouton. Aucune commande morte n'y figure. Trois commandes en sont écartées par décision du 02/09/2026 — `/version`, `/delier`, `/tts` — et cette liste d'exclusion est **écrite en un seul endroit du code, à côté de la déclaration du menu**, de sorte qu'une commande nouvellement ajoutée entre par défaut dans le menu et n'en soit exclue que par une décision explicite
- [ ] CA3bis : Les trois commandes exclues restent **pleinement fonctionnelles à la saisie manuelle**. Les retirer du menu ne les retire pas du bot : `/version`, `/delier` et `/tts` répondent exactement comme avant
- [ ] CA3ter : Toute ligne du menu déclenche une action complète **en un seul clic**. Une commande dont le clic ne fait qu'afficher un rappel de deux autres commandes à taper ensuite n'a pas sa place dans le menu : elle y coûte deux gestes là où la ligne voisine en coûte un
- [ ] CA4 : L'ordre des lignes suit une logique métier (les gestes du quotidien d'abord, la consultation ensuite, la configuration en fin de liste) et non l'ordre d'écriture dans le code
- [ ] CA5 : Taper une commande depuis le menu produit exactement le même comportement que la taper à la main : aucune commande ne change de sémantique au passage
- [ ] CA6 : La déclaration du menu est rejouée à chaque démarrage du bot, sans intervention manuelle : ajouter une commande au bot suffit à la voir apparaître dans le menu au redémarrage suivant

*Le clavier de raccourcis permanent disparaît*
- [ ] CA7 : Le clavier permanent affiché sous la zone de saisie (« Nouvelle action vocale », « Interroger », « Historique », « Stats », « Corriger », « Note »…) n'apparaît plus, ni au démarrage, ni après une commande, ni après un enregistrement d'évènement
- [ ] CA8 : Le clavier est retiré **aussi pour les jardiniers qui l'ont déjà affiché** : un clavier permanent Telegram persiste côté client tant que le bot ne demande pas explicitement son retrait. Sans cette demande de retrait, l'ancien clavier resterait visible indéfiniment chez les utilisateurs existants — CA7 n'est pas satisfait par la seule suppression du code qui l'affichait
- [ ] CA9 : Les parcours qui reposaient uniquement sur un de ces boutons restent atteignables : chaque bouton retiré a soit une commande équivalente dans le menu, soit une entrée équivalente conservée dans le parcours concerné. La correspondance bouton retiré → chemin de remplacement est établie et vérifiée bouton par bouton avant livraison
- [ ] CA10 : `/start` et `/help` restent le point d'entrée de la découverte et mentionnent le menu comme moyen d'accès aux commandes, en cohérence avec la restructuration de l'aide déjà spécifiée

*Ce qui ne change pas — périmètre explicitement exclu*
- [ ] CA11 : Les claviers **contextuels** affichés en réponse à une action — confirmation d'un évènement enregistré, choix d'une parcelle, correction, désambiguïsation d'une culture, saisie guidée — sont **inchangés** : même déclenchement, mêmes libellés, même comportement. Cette US ne touche qu'au clavier permanent, jamais aux boutons de validation d'un échange en cours
- [ ] CA12 : Un clavier contextuel qui s'affiche puis se referme après réponse ne fait pas réapparaître le clavier permanent supprimé
- [ ] CA13 : Les tests existants qui couvrent les claviers de validation passent sans modification de leurs attendus. Toute modification d'un attendu de ces tests est le signe que le périmètre a débordé

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : interaction Telegram (ergonomie d'entrée des commandes)
- Migration BDD requise : **non** — aucune donnée persistée n'est concernée
- Dépendances :
  - S'articule avec `US_Restructurer_help_4_domaines` et `US_Commande_help_aide_mobile` : les descriptions d'une ligne du menu doivent reprendre le vocabulaire des 4 domaines métier, pas en inventer un septième
  - Touche les parcours de saisie guidée (`US-033` et suivantes) uniquement par CA9 (le bouton d'entrée disparaît, le parcours reste)
- Portée du menu : le menu est déclaré pour l'ensemble des jardiniers. **Vérification faite le 02/09/2026 : il n'existe aucune commande réservée à un rôle** — les 24 commandes enregistrées sont toutes destinées au jardinier, le seul contrôle de rôle en place portant sur l'enregistrement et la correction d'évènements, pas sur l'accès à une commande. Le menu n'a donc pas à distinguer de périmètre d'administration
- Hors périmètre, explicitement : le remplacement du bouton « Menu » par l'ouverture du dashboard PWA (mini-application web Telegram). Écarté par décision du 02/09/2026 — à traiter dans une US dédiée si le besoin se confirme

*Les trois commandes écartées du menu — décisions du 02/09/2026*

Aucune n'est une commande d'administration ; les trois restent tapables à la main (CA3bis).

`/version` — diagnostic sans usage quotidien pour le jardinier, qui peut consulter la version
en ligne. Hors menu.

`/delier` — action rare et destructive. La mettre en évidence dans un menu permanent invite au
geste qu'on cherche justement à rendre délibéré. Hors menu.

`/tts` — écartée pour la raison inverse de celle envisagée d'abord. `/tts` **ne règle rien** :
il affiche l'état de la synthèse vocale et renvoie vers `/tts_on` ou `/tts_off`, qu'il faut
ensuite saisir. Le clic depuis le menu coûte donc deux gestes au lieu d'un, ce qu'une entrée de
menu ne devrait jamais faire (CA3ter). **Ce sont `/tts_on` et `/tts_off` qui entrent au menu**,
chacune agissant en un clic — l'état courant reste lisible, il figure déjà dans leur réponse.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: le menu natif liste toutes les commandes avec leur aide
  Given un jardinier qui ouvre la conversation avec le bot potager
  When il appuie sur le bouton "Menu" à gauche de la zone de saisie
  Then la liste verticale des commandes du bot s'affiche
  And chaque ligne porte le libellé de la commande et une phrase d'aide en français
  And toutes les commandes destinées au jardinier y figurent

Scénario: le clavier permanent ne s'affiche plus pour un nouveau jardinier
  Given un jardinier qui n'a jamais utilisé le bot
  When il envoie /start
  Then aucun clavier de raccourcis n'apparaît sous la zone de saisie
  And la réponse d'accueil l'oriente vers le menu et vers /help

Scénario: le clavier permanent est retiré chez un jardinier existant
  Given un jardinier dont le client Telegram affiche encore l'ancien clavier de raccourcis
  When il envoie son premier message après la mise à jour du bot
  Then le clavier de raccourcis est retiré de son écran
  And il ne réapparaît à aucun message suivant

Scénario: les boutons de validation d'une action sont préservés
  Given un jardinier qui dicte "j'ai récolté 300 g de haricots sur la parcelle 3"
  When le bot lui présente l'évènement interprété pour confirmation
  Then les boutons de confirmation s'affichent comme avant la modification
  And ils disparaissent après son choix
  And aucun clavier de raccourcis permanent ne prend leur place

Scénario: le réglage de la voix se fait en un seul clic depuis le menu
  Given un jardinier dont la synthèse vocale est désactivée
  When il ouvre le menu de commandes
  Then il y trouve /tts_on et /tts_off, chacune sur sa ligne
  And il n'y trouve pas /tts, qui n'aurait fait que lui rappeler ces deux commandes
  When il choisit /tts_on
  Then la synthèse vocale est activée sans autre saisie de sa part

Scénario: une commande écartée du menu reste utilisable à la main
  Given un jardinier qui saisit /version à la main
  When le bot traite la commande
  Then il répond comme avant la mise en place du menu
  And le fait que /version soit absente du menu ne change rien à ce comportement

Scénario: un parcours qui n'avait qu'un bouton reste atteignable
  Given un jardinier qui utilisait le bouton "Corriger" du clavier permanent
  When il ouvre le menu de commandes
  Then il y trouve la commande équivalente avec sa phrase d'aide
  And le parcours de correction se déroule à l'identique
```

**Labels GitHub :** `us`, `interaction-telegram`, `ergonomie`
