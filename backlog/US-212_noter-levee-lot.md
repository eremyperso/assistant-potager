**ID :** US-212
**Titre :** Noter la levée d'un lot de semis
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux noter combien de graines ont levé dans une barquette, devant la barquette — « levée du lot 128 : 40 »
Afin de connaître mon vrai taux de levée, lot par lot, et de savoir au printemps suivant s'il faut semer plus

**Contexte fonctionnel :**
La v2 en fait « la donnée la plus utile et la moins saisie » : « 48 semés → 40 levés, c'est ce qui permet de dire au printemps suivant « sème 20 % de plus ». Encore faut-il que quelqu'un compte. » L'écran de terrain (§ 3c) porte un bouton « Noter la levée », et la phrase « 83 % — au-dessus de la moyenne du chou (75 %) ».

**Décision du 18/10/2026 — la PWA limite la saisie.** Depuis la PWA, seul le **geste** de la levée est possible : le bouton dépose « levée du lot 128 » dans la file, sans compteur ni case « terminée ». Tous les détails — le nombre de levés, puis « la levée est-elle terminée ? » — sont demandés **par le bot, très précisément**, avec ce que la base sait du lot (même principe que la mise en godet et la perte, US-224).

**Ce geste n'existe pas.** Aujourd'hui, la germination d'un lot se **déduit** des mises en godet : « La différence entre les graines semées et celles déjà repiquées donne ce qui est encore en train de lever » (`pepiniere-par-lot.md`). Tant que rien n'est repiqué, un lot de 48 graines dont 40 ont levé s'affiche comme 48 graines en germination.

Cette US ajoute un geste de **constat** : la levée d'un lot, un nombre de plants levés à une date, éventuellement déclarée **terminée**. Elle enrichit la lecture par lot sans toucher au stock.

**Critères d'acceptance :**

*Le geste*
- [ ] CA1 : Le référentiel d'actions (US-168) gagne le geste **levée** : un lot, un nombre de plants levés, une date, et l'indication facultative que la levée est **terminée**
- [ ] CA2 : Il se dicte, reconnu par la grammaire déterministe sans appel au modèle : « levée du lot 128 : 40 », « 40 choux frisés levés sur 48 », « les tomates cerise ont levé, 12 plants », « levée terminée pour le lot 128 : 40 ». Le lot se désigne par son numéro (US-209), par sa culture quand un seul lot en cours correspond, ou par un choix entre plusieurs lots proposés par boutons avec numéro et date de semis (modèle d'US-019) ; cette résolution est écrite une fois et partagée avec le déplacement (US-211)
- [ ] CA3 : Un « sur 48 » qui ne correspond pas aux graines semées du lot est signalé au récapitulatif, jamais corrigé en silence. Plus de levés que de graines semées est signalé comme incohérence de saisie — les valeurs sont gardées telles quelles, comme pour l'incohérence existante des lots (US-065)
- [ ] CA4 : La levée ne se note que sur un **lot de pépinière** issu d'un semis. Le lot « godets sans semis rattaché » la refuse. Une phrase sur un semis en pleine terre (« les carottes ont levé ») n'est pas une levée de lot : le bot propose de la noter en observation (hors périmètre, plan des épics § 9)
- [ ] CA5 : Le geste est récapitulé et confirmé (US-021) ; il apparaît au Journal, se corrige et se supprime par le parcours existant

*La lecture du lot*
- [ ] CA6 : Un comptage est un **instantané** : le plus récent à la date de référence fait foi, les comptages ne s'additionnent pas. `GET /pepiniere/lots` expose le nombre de levés, la date du dernier comptage, le **taux de levée** (levés ÷ graines semées, seulement si les graines semées sont connues) et l'indication « levée terminée »
- [ ] CA7 : Une levée **terminée** clôt la germination du lot : les graines non levées (semées − levés) sont soldées, l'état de germination passe à « clos » (US-065) et il ne reste plus de graines « en train de lever ». Une levée non terminée laisse l'état de germination tel qu'il est
- [ ] CA8 : La lecture expose aussi la **moyenne de levée de la culture dans ce potager**, calculée sur les autres lots de la même culture dont la levée a été notée, **à partir de deux lots** ; en deçà, aucune moyenne n'est rendue (pas de comparaison sur un seul point)
- [ ] CA9 : Après la levée, un repiquage de plus de plants qu'il n'en a levé est signalé comme incohérence, jamais borné
- [ ] CA14 : Chaque comptage de levée apparaît, à sa date, dans le **cycle de vie du lot** (« Détail du lot », US-061) au même titre qu'une mise en godet, une plantation ou une perte : nombre de levés, « sur N » s'il a été dit, mention « terminée ». Tous les comptages y figurent, pas seulement le dernier ; seuls ceux du lot affiché remontent (`GET /godets/detail` → `levees`) *(Ajouté le 18/10/2026 : retour PO, la levée n'était visible que dans la traçabilité de la fiche.)*
- [ ] CA10 : **Aucun stock ne change** : un plant levé n'est pas un godet. `GET /godets`, `GET /stats`, l'écran Stocks et `/stats` rendent les mêmes valeurs avant et après (test)
- [ ] CA11 : Le geste est ouvert à la PWA par le geste pré-rempli d'US-196, **limité au geste lui-même** : il ne porte que le lot (« levée du lot 128 », gabarit de phrase reconnu par le parseur). Ni compteur, ni nombre de levés, ni « levée terminée » ne se saisissent à l'écran, et le serveur ignore un nombre qu'un client enverrait. Le bot demande ensuite, précisément :
  - **le nombre de levés**, en rappelant le lot (culture, variété, date de semis, graines semées, dernier comptage) ; zéro est un comptage valide. Sur un lot **déjà en partie repiqué**, la question porte sur les graines restantes (« 20 graines semées, dont 15 déjà repiqués — combien ont levé parmi les 5 graines restantes ? ») : un plant repiqué a forcément levé, et le total enregistré est repiqués + réponse (5 → 20 levés sur 20, rien de soldé). Le récapitulatif dit d'où vient le total *(Révisé le 18/10/2026 : retour PO sur le lot 4 — la question sur le lot entier faisait compter 5 sur 20 et solder 15 graines pourtant repiquées.)* ;
  - **si la levée est terminée**, en disant avant de demander ce que « oui » solde (les graines non levées, la germination qui se clôt).

  Une phrase dictée avec son nombre (« levée du lot 128 : 40 ») ne pose aucune de ces deux questions : sans le mot « terminée », la levée est en cours. « Laisser dans ma file » laisse le geste en attente. Le récapitulatif d'une levée ne demande **aucune parcelle** : le geste porte sur un lot *(correctif du 18/10/2026, idem pour la clôture d'US-216)*.

*Définition de terminé*
- [ ] CA12 : Les fiches `pepiniere-par-lot.md` (noter la levée, le taux, la moyenne, la levée terminée), `semis-godet-plantation.md`, `enregistrer-un-geste.md`, `journal-et-corrections.md` et le guide utilisateur (§ 6.3) sont mis à jour (US-099 / CA9)
- [ ] CA13 : Des tests couvrent : chaque forme dictée, « sur N » discordant, plus de levés que de semés, refus hors lot de pépinière, instantané (deux comptages successifs), taux sans graines connues, levée terminée et état clos, moyenne avec zéro, un et deux lots antérieurs, repiquage supérieur aux levés, absence d'effet sur les stocks, isolation entre potagers de la moyenne

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement, analyse (lecture par lot)
- Migration BDD requise : **non** si le type d'action n'est pas contraint en base et que le nombre de levés tient dans la quantité du geste ; à vérifier au démarrage
- Dépendances : **US-209** (numéro de lot) ; US-065 (état de germination, livrée)
- Consommateurs : US-214 (action suggérée « Noter la levée »), US-215, US-216
- Impact tokens : zéro sur le chemin déterministe
- Point de vigilance : **ne pas casser le calcul actuel de germination**. Sans levée notée, un lot se lit exactement comme aujourd'hui ; la levée ajoute une information, elle ne remplace le calcul existant que lorsqu'elle est déclarée terminée
- Point de vigilance : le taux de levée n'est pas le taux de germination affiché aujourd'hui (plants obtenus au repiquage ÷ graines semées). Les deux coexistent et sont nommés différemment à l'écran
- Wireframe : v2 § 3 (colonne « semés → levés »), § 3c « Noter la levée » (le compteur du wireframe n'est pas repris : la saisie du détail est faite par le bot, décision du 18/10/2026), note « Taux de levée »

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Premier comptage
  Given le lot 128 : 48 graines de chou frisé semées le 1er septembre
  When le jardinier dicte "levée du lot 128 : 40"
  Then le récapitulatif propose "levée du lot 128 (chou frisé) : 40 plants"
  When le jardinier confirme
  Then le lot 128 compte 40 levés, taux de levée 83 %
  And son état de germination reste "en cours"

Scénario: Deux comptages successifs
  Given un comptage de 30 levés le 8 septembre sur le lot 128
  When le jardinier note 40 levés le 12 septembre
  Then le lot 128 compte 40 levés, pas 70

Scénario: Levée terminée
  When le jardinier dicte "levée terminée pour le lot 128 : 40"
  Then l'état de germination du lot 128 est "clos"
  And 8 graines sont soldées comme non levées

Scénario: Moyenne de la culture
  Given deux lots de chou antérieurs avec une levée notée de 70 % et 80 %
  When je consulte le lot 128
  Then la moyenne de levée du chou dans ce potager est de 75 %

Scénario: Pas de moyenne sur un seul lot
  Given un seul lot de chou antérieur avec une levée notée
  When je consulte le lot 128
  Then aucune moyenne de levée n'est rendue

Scénario: Depuis la PWA, le geste seul
  Given le lot 128 : 48 graines de chou frisé semées le 1er septembre
  When le jardinier appuie sur "Noter la levée" dans la fiche du lot
  Then le geste "levée du lot 128" est déposé dans sa file, sans nombre ni indication de fin
  When il reprend le geste dans le compagnon
  Then le bot demande "Combien de plants ont levé dans le lot n° 128 ?" en rappelant les 48 graines semées
  When il répond "40"
  Then le bot demande "La levée est-elle terminée ?" en disant que 8 graines non levées seraient soldées
  When il répond "Pas encore"
  Then le récapitulatif propose "levée du lot 128 (chou frisé) : 40 plants"

Scénario: Une phrase dictée avec son nombre
  When le jardinier dicte "levée du lot 128 : 40"
  Then le bot propose directement le récapitulatif, sans poser de question
  And la levée n'est pas terminée

Scénario: Semis en pleine terre
  When le jardinier dicte "les carottes ont levé"
  Then le bot indique que la levée se note sur un lot de pépinière
  And propose de l'enregistrer en observation
```

**Labels GitHub :** `us`, `bot`, `backend`, `enregistrement`, `pepiniere`
