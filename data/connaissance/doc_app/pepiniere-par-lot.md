---
titre: La pépinière, lot de semis par lot de semis
famille: doc_app
source: Guide de l'Assistant Potager
niveau_confiance: verifie
domaines_aide: semis ; godet ; lot
type: semis
index_terms:
  - "lot de semis"
  - "état de germination"
  - "graines en germination"
---

# La pépinière, lot de semis par lot de semis

## Ce qu'est un lot de semis

**Intention :** comprendre
**On parle aussi de :** lot ; barquette ; série ; semis du jour ; regroupement par date

Chaque semis fait à couvert forme un lot à lui seul, identifié par sa date. Deux semis de la même culture faits à deux jours d'écart restent donc deux lots distincts, jamais fondus en une seule ligne : c'est ce qui permet de voir lequel a levé et lequel se fait attendre. La pépinière se lit ainsi lot par lot, avec pour chacun sa date, sa culture, sa variété, le nombre de graines de départ et ce qu'il en reste.

## Savoir combien de graines d'un lot n'ont pas encore levé

**Intention :** diagnostic
**On parle aussi de :** graines restantes ; en germination ; pas encore levé ; reste à repiquer ; lot en cours

La différence entre les graines semées et celles déjà repiquées donne ce qui est encore en train de lever. Trois états sont possibles pour un lot : en cours, quand des graines restent à lever et que les repiquages ont été déclarés complètement ; clos, quand tout a été soldé, ou quand vous avez déclaré la levée terminée ; indéterminé, quand un repiquage n'a pas dit de combien de graines il venait. L'état indéterminé n'est jamais présenté comme un lot en cours : une information manquante ne se transforme pas en attente prometteuse.

## Un lot qui affiche plus de plants que de graines

**Intention :** diagnostic
**On parle aussi de :** taux de germination impossible ; plus de cent pour cent ; incohérence ; erreur de saisie

Obtenir plus de plants qu'il n'a été semé de graines est impossible au jardin : quand cela s'affiche, c'est une saisie qui se contredit, et l'assistant le signale au lieu de rogner discrètement les chiffres. Les valeurs sont montrées telles qu'elles ont été saisies, accompagnées de la mention d'incohérence, pour que le geste fautif puisse être retrouvé et corrigé dans le journal.

## Des godets qui ne sont rattachés à aucun semis

**Intention :** diagnostic
**On parle aussi de :** godets orphelins ; plants achetés ; sans semis d'origine ; lot à part

Des plants mis en godet sans qu'aucun semis de la pépinière ne leur soit rattaché — parce qu'ils ont été achetés, donnés, ou repiqués sans qu'on précise leur origine — sont regroupés dans un lot à part, par culture et par variété. Ce lot se comporte comme les autres pour la plantation, mais n'affiche ni date de semis ni taux de réussite, faute d'un point de départ connu.

## Retrouver un lot par son numéro, l'écrire sur l'étiquette

**Intention :** procédure
**On parle aussi de :** numéro de lot ; liste des lots ; mes lots ; numéro oublié ; lot 128 ; étiquette de la barquette ; écrire au crayon ; aller au lot ; retrouver un lot

Chaque semis en pépinière reçoit un numéro court à l'enregistrement : le premier lot de votre potager porte le numéro 1, le suivant le 2, et ainsi de suite, sans jamais reprendre un numéro déjà donné, même si vous supprimez un semis. Vous pouvez l'écrire au crayon sur l'étiquette de la barquette, puis dire « levée du lot 128 : 40 » plutôt que de chercher parmi vos semis de choux. Le numéro est propre à votre potager : le lot 5 d'un autre potager n'est pas le vôtre, et il ne se retrouve jamais depuis le vôtre.

Pour retrouver un numéro oublié, tapez `/lot` sans rien ajouter (ou dites « mes lots ») : l'assistant liste vos lots, les plus récents d'abord, 15 au plus, avec pour chacun son numéro, sa culture, sa date de semis, son emplacement et ce qui reste. Un lot épuisé est marqué ⚪ et les autres 🟢. `/lot tomate` ne garde que les lots de tomate, ce qui permet de remonter plus loin quand vous en avez beaucoup. Les godets sans semis rattaché n'ont pas de numéro et n'y figurent pas.

Pour retrouver un lot : tapez `/lot 128` (ou demandez « où en est le lot 128 ? ») et l'assistant répond tout de suite, sans réfléchir longuement : culture, variété, date de semis, emplacement, graines semées, plants obtenus et plants restants. Dans l'application, la carte de chaque lot affiche son numéro (« #128 »), et le champ « Aller au lot n° » de la Pépinière ouvre sa fiche. Un numéro qui n'existe pas dans votre potager est dit tel quel : « Aucun lot n° 128 dans ce potager ». Les godets sans semis rattaché n'ont pas de numéro, faute de semis.

Un semis corrigé de la pépinière vers la pleine terre garde son numéro mais quitte la liste des lots ; corrigé dans l'autre sens, il reçoit un numéro s'il n'en avait pas.

## Savoir où se trouve un lot

**Intention :** diagnostic
**On parle aussi de :** emplacement d'un lot ; dans quelle pépinière ; où sont mes godets ; lot réparti entre deux pépinières ; emplacement non renseigné

Chaque lot affiche son emplacement du moment : la pépinière et son type (chaude ou froide). L'assistant le lit dans cet ordre, et s'arrête au premier trouvé : le dernier déplacement que vous avez dit (« passé le lot 119 au châssis froid »), sinon la dernière mise en godet dont vous avez dit la pépinière, sinon la pépinière où le semis a été fait, sinon « emplacement non renseigné ». Un semis fait sans pépinière dite n'est donc jamais rattaché d'office à « la » pépinière, même s'il n'y en a qu'une. Le lot des godets sans semis rattaché prend l'emplacement de sa dernière mise en godet localisée, sinon il reste non renseigné. Avec une date de référence antérieure à une mise en godet ou à un déplacement, le lot est lu à l'emplacement qu'il avait alors. Le cycle de vie d'un lot, dans l'application, affiche chaque déplacement à sa date, avec la pépinière d'origine et celle de destination.

Un lot n'a qu'un seul emplacement. Si vous avez posé une partie de vos godets sous le châssis froid et l'autre dans la serre, le lot se lit à la dernière pépinière que vous avez dite ; l'application ne tient pas la répartition d'un lot entre deux pépinières, et un déplacement porte toujours sur le lot entier. Ce détail par emplacement ne change aucun total : vos plants restent comptés par culture et par variété.

## Savoir ce qu'il y a à faire aujourd'hui dans la pépinière

**Intention :** procédure
**On parle aussi de :** que faire aujourd'hui ; onglet Aujourd'hui ; à repiquer ; à endurcir ; prêts pour le plan ; à semer ; lots du plus urgent au plus calme ; échéance d'un lot ; action suggérée ; onglet Lots

Pour chaque lot, l'assistant calcule ce qu'il y a à faire et dans quel ordre. Il répond à quatre questions : quels lots sont **à repiquer**, lesquels sont **à endurcir**, quels plants sont **prêts pour le plan**, et quels légumes sont **à semer** (la fenêtre de votre zone est ouverte et aucun lot de ce légume n'est en cours). Chaque lot porte aussi une action suggérée, une seule : Repiquer, Noter la levée, Mettre en terre ou Clôturer. Les lots sont rangés du plus urgent au plus calme : d'abord les retards, du plus grand au plus petit, puis les échéances à venir, de la plus proche à la plus lointaine, puis les lots sans échéance, et tout en dernier les lots dormants. Le calcul est le même partout.

Dans l'application, la Pépinière s'ouvre sur son onglet **Aujourd'hui**, le poste de travail. En haut, quatre cartes répondent aux quatre questions ; une carte à zéro dit « rien » au lieu de disparaître, et « À repiquer » passe en teinte d'alerte dès qu'un lot est en retard. Appuyer sur « À repiquer », « À endurcir » ou « Prêts pour le plan » ne garde que ces lots ; un second appui, ou la croix de la pastille, retire le filtre. Dans « À semer », le nom d'un légume ouvre sa fiche culture. Dessous, les lots en cours sont listés du plus urgent au plus calme : numéro, culture, variété, jour du semis, emplacement, graines semées ou godets disponibles, l'échéance en clair (« Repiquage +6 j », « Endurcissement J+3 sur 7 », « En pépinière froide », « Délai non renseigné »…) et le bouton de l'action suggérée. Une ligne en retard est mise en évidence ; les lots dormants sont en fin de liste, atténués. La recherche porte sur la culture, la variété et le numéro ; venu du plan en appuyant sur une pépinière, l'onglet s'ouvre filtré sur elle. Appuyer sur une ligne ouvre la fiche du lot. Avec une seule pépinière, sa superficie et son type sont rappelés en haut. L'onglet **Lots** garde l'écran d'avant : les cartes par lot, groupées par famille, avec leur numéro. Les onglets Calendrier et Emplacements arriveront plus tard.

## Ce que veulent dire à repiquer, en retard, à endurcir et prêt pour le plan

**Intention :** comprendre
**On parle aussi de :** repiquage attendu ; en retard de repiquage ; endurcissement ; J+3 sur 7 ; pépinière froide ; mise en terre prévue ; fourchette de dates

Un lot est **à repiquer** tant qu'aucun de ses plants n'est repiqué : l'échéance est la date où vous avez semé, augmentée du temps que met ce légume avant son repiquage. C'est une fourchette, jamais une date unique : « repiquage attendu entre le 11 et le 13 septembre ». Avant la fourchette, le lot est « à venir » ; dedans, il est « à repiquer » ; après, il est « en retard », et le retard se compte depuis la fin de la fourchette.

Un lot repiqué a une **mise en terre prévue**, elle aussi en fourchette. L'**endurcissement** est le compte à rebours de 7 jours qui précède le début de cette fourchette : « J+3 sur 7 » veut dire trois jours déjà écoulés, et le compteur ne dépasse jamais 7. En pépinière froide, le lot s'endurcit sur place : l'assistant écrit « en pépinière froide » et ne compte rien. Un lot que vous déplacez vers une pépinière froide commence son endurcissement au jour du déplacement ; une fois les 7 jours passés, il n'y a plus rien à compter et le lot reste « en pépinière froide ». Une pépinière dont le type n'est pas renseigné est traitée comme une pépinière chaude.

Des plants sont **prêts pour le plan** quand leur mise en terre prévue est atteinte, ou quand elle n'est pas connue : l'assistant compte alors des plants et, lorsque le plan les connaît, les rangs libres de chaque parcelle. Il ne dit rien de la place en mètres carrés.

## Un lot dormant : oublié depuis des semaines

**Intention :** diagnostic
**On parle aussi de :** lot dormant ; lot oublié ; plus de geste depuis longtemps ; clôturer un lot ; 60 jours sans geste ; plants oubliés

Un lot est **dormant** quand il reste des graines à lever ou des plants en pot, qu'aucun geste ne lui a été imputé depuis 60 jours, et que sa mise en terre prévue est dépassée ou inconnue. L'action suggérée est alors « Clôturer », et le lot passe en fin de liste. Un lot dont les plants attendent une mise en terre prévue qui n'est pas encore arrivée n'est jamais dormant, même si vous n'y avez pas touché depuis des mois : il attend, il n'est pas oublié. Un lot épuisé n'est pas dormant non plus. Pour le solder, voir « Clôturer un lot ».

## Ouvrir la fiche d'un lot et y faire ses gestes

**Intention :** guide
**On parle aussi de :** fiche du lot ; ouvrir un lot ; lot sélectionné ; écran de terrain ; faire un geste depuis le lot ; repiquer depuis la fiche ; mettre en terre depuis la fiche

Appuyez sur un lot de la liste, tapez son numéro dans « Aller au lot n° », ou ouvrez l'adresse `/?vue=pepiniere&lot=128` (celle de l'étiquette) : la **fiche du lot** s'ouvre. Sur un grand écran elle se pose à côté de la liste ; sur un téléphone elle prend tout l'écran. C'est le même écran dans les deux cas, et l'ouvrir ne modifie rien.

Elle montre, du haut vers le bas : le numéro, la culture et la variété, le jour du semis et le nombre de jours écoulés, l'emplacement et son type ; l'**échéance** en clair et datée (« En retard de 6 jours — repiquage attendu entre le 11 et le 13 septembre »), avec la raison quand elle ne peut pas être calculée ; les **gestes** ; puis la **traçabilité** du lot : graines semées, levés, taux de levée, plants repiqués en godet, pertes, ventes, plants mis en terre, godets restants, graines encore en germination. Un tiret veut dire « aucun geste de ce type », jamais zéro. « Détail du lot » ouvre le cycle de vie complet, levées, déplacements et clôture compris ; un lot terminé y finit par « Lot terminé ».

Les gestes proposés suivent l'état du lot, **le geste suggéré en premier** : *Repiquer en godet* s'il reste des graines en germination, *Noter la levée* tant que la levée n'est pas terminée, *Mettre en terre* s'il reste des godets, *Déclarer une perte* s'il reste quelque chose, *Déplacer* si votre potager compte au moins deux pépinières, *Clôturer le lot* s'il est dormant. Un lot de godets sans semis rattaché n'a ni repiquage ni levée. Un lot terminé ou clôturé s'ouvre sans aucun geste et garde sa traçabilité.

**Un bouton ne fait que préparer.** Il remplit le geste avec le lot, la culture, la variété et les quantités connues, et le dépose dans la file d'attente, sans quitter l'application ni ouvrir Telegram ; une notification le confirme, un doublon est signalé, un échec propose « Réessayer ». Votre compagnon vous le relit ensuite, et rien ne compte avant votre « Confirmer ». Les boutons de la liste du jour font de même. À côté du bouton, la phrase équivalente à dire au compagnon est proposée (« mise en godet 30 plants du lot 128 », « levée du lot 128 »). Un membre en lecture seule voit la fiche entière, sans bouton.

## Comment clôturer un lot définitivement

**Intention :** guide
**On parle aussi de :** clôturer un lot ; solder un lot ; fermer un lot ; abandonner un lot ; lot dormant à clôturer ; clôture du lot

**Clôturer** un lot le solde **définitivement** : tous ses godets restants et toutes ses graines, levées ou non. Il n'a plus rien à faire, n'apparaît plus dans les échéances et sort du stock. Le bouton est proposé sur un lot dormant ; il dit, avant que vous appuyiez, ce qu'il solde (« 40 godets et 20 graines non levées »). Comme tout geste de la fiche, il passe par le compagnon : « clôture du lot 128 — 40 godets et 20 graines soldés. C'est correct ? ». Les nombres sont relus au moment où vous confirmez. Un lot déjà clôturé ou déjà épuisé est refusé : rien n'est enregistré. L'historique du lot — semis, plants obtenus, mises en terre — n'est jamais réécrit.

Vous pouvez aussi le dire directement : « clôture du lot 128 ». Un geste préparé depuis l'application attend dans votre fil de gestes en attente, où le compagnon vous le rappelle.

## Pourquoi un lot n'a pas d'échéance

**Intention :** diagnostic
**On parle aussi de :** échéance manquante ; valeur non renseignée ; pas de repiquage attendu ; pas de mise en terre prévue ; pourquoi aucune date

L'assistant n'invente jamais une date. Sans la donnée nécessaire, le lot n'a tout simplement pas d'échéance, et la raison est dite : « non renseigné » quand le calendrier ne porte pas la durée voulue, « date inconnue » pour des plants arrivés sans semis rattaché. Une durée n'est jamais déduite d'une autre : ni de la levée, ni du temps avant la mise en terre. Un lot sans échéance n'est donc ni en retard ni à endurcir ; pour qu'il en ait une, renseignez la durée manquante avec `/calendrier duree`, pour votre potager.

## Savoir où mettre en terre les plants d'un lot

**Intention :** guide
**On parle aussi de :** où les mettre ; où planter mes godets ; quelle planche pour mes plants ; mettre en terre ici ; rangs libres pour la pépinière ; exposition de la parcelle ; ensoleillement de la parcelle ; plein soleil mi-ombre ombre

Quand un lot a des godets, sa fiche montre la section **« Où les mettre »** : les parcelles du plan où il reste au moins un rang libre à la date affichée. Les pépinières n'y figurent jamais, ni les parcelles pleines. Chaque parcelle dit ce qui lui reste — en **places** de la culture du lot quand la longueur de la parcelle et l'espacement de la culture sont connus (« 20 places de chou »), en **rangs libres** sinon — et compare l'**ensoleillement** de la parcelle (plein soleil : 6 h et plus de soleil direct ; mi-ombre : 3 à 6 h ; ombre : moins de 3 h) à l'exposition que la culture demande, écrite en mots : « plein soleil, comme la culture le demande », « mi-ombre, pour une culture de plein soleil », « déconseillé : ombre, pour une culture de plein soleil » quand l'écart est de deux crans (la parcelle reste proposée : la suggestion conseille, elle n'interdit pas), ou « ensoleillement de la parcelle non renseigné » quand la parcelle n'a pas déclaré le sien — la fiche dit alors la phrase à dire au compagnon (« ensoleillement planche racines plein soleil »). L'orientation de la parcelle (« Nord », « Sud ») n'entre pas dans la comparaison : elle ne dit pas l'ensoleillement, une planche plein sud peut être à l'ombre d'un mur. Rien n'est supposé.

La meilleure parcelle vient d'abord : celles dont l'ensoleillement concorde, puis celles à un cran d'écart, puis à deux crans (déconseillées), puis celles dont l'ensoleillement ou l'exposition de la culture n'est pas renseigné. À rang égal, celle qui a le plus de places libres (sinon le plus de rangs libres), puis l'ordre de vos parcelles. Une parcelle dont le nombre de rangs n'est pas déclaré vient après, marquée « rangs libres inconnus » : elle n'est ni exclue ni comptée comme libre. Trois parcelles s'affichent, « Voir toutes les parcelles » donne les autres. Sans longueur ni espacement, la section précise que le nombre de plants qui tiendront n'est pas calculé.

**Mettre en terre ici** prépare la plantation du lot dans cette parcelle, les godets restants proposés comme quantité (« plantation 40 plants du lot 128 parcelle planche-nord ») ; le compagnon la relit et vérifie la rotation avant votre « Confirmer ». Le rang n'est pas pré-rempli : le plan numérote les rangs dans l'ordre d'installation, pas selon leur position réelle. Si aucune parcelle n'a de rang libre, la section le dit et garde « Mettre en terre » : le compagnon vous demandera la parcelle. Ces suggestions ne réservent rien. Le champ « Plants à mettre en terre » envoie une partie du lot sur une parcelle, le reste sur une autre ; un lot ne donne jamais plus de plants qu'il n'en contient, et le bouton se grise quand tout le lot attend déjà. Les autres gestes du lot suivent la même règle : une perte, un repiquage, un déplacement ou une clôture déjà en attente grise le bouton jusqu'à sa confirmation. Un membre en lecture seule les voit, sans bouton. La carte « Prêts pour le plan » de l'onglet Aujourd'hui lit les mêmes rangs libres.

## Noter la levée d'un lot

**Intention :** procédure
**On parle aussi de :** noter la levée ; levée du lot ; combien de graines ont levé ; combien ont levé ; plants levés ; compter les levés ; taux de levée ; moyenne de levée ; levée terminée ; les graines n'ont pas toutes levé ; ont levé

Devant la barquette, dites ce que vous comptez : « levée du lot 128 : 40 », « 40 choux frisés levés sur 48 », « les tomates cerise ont levé, 12 plants » ou « levée terminée pour le lot 128 : 40 ». Le lot se désigne par son numéro, ou par sa culture quand un seul lot en cours correspond ; s'il y en a plusieurs, l'assistant les propose en boutons, avec leur numéro et leur date de semis. Il récapitule en une phrase (« levée du lot 128 (chou) : 40 plants »), puis attend votre « Confirmer ». La levée figure au journal, se corrige et se supprime comme les autres gestes.

Depuis l'application, le bouton « Noter la levée » de la fiche du lot ne fait que **déposer le geste** avec son lot : l'écran ne demande ni le nombre de levés ni « terminée ». C'est le compagnon qui les demande, précisément, quand vous reprenez le geste : d'abord « Combien de plants ont levé dans le lot n° 128 ? », avec le lot, ses graines semées et son dernier comptage rappelés (tapez un nombre, 0 si rien n'a encore levé ; si une partie du lot est déjà repiquée, il ne demande que ce qui a levé parmi les graines restantes et compte les repiqués comme levés), puis « La levée est-elle terminée ? », qui dit ce que « oui » solde avant de vous le demander. Une phrase dictée avec son nombre (« levée du lot 128 : 40 ») ne pose aucune de ces deux questions : sans le mot « terminée », la levée est en cours.

Une levée est un **constat**, pas un mouvement de stock : un plant levé n'est pas un godet. Rien ne change dans les godets, la page Stocks ni les statistiques. Le comptage le plus récent fait foi et les comptages ne s'additionnent pas : 30 levés le 8 septembre, puis 40 le 12, font un lot qui compte 40 levés, pas 70.

Le **taux de levée** est le nombre de levés divisé par le nombre de graines semées (40 sur 48 : 83 %). Il n'existe que si les graines semées sont connues. Il ne se confond pas avec le taux de germination, qui compte les plants obtenus au repiquage. Dès que deux autres lots de la même culture ont une levée notée dans votre potager, l'assistant ajoute la **moyenne de levée** de cette culture et situe le lot : « 83 % — au-dessus de la moyenne des lots de chou ici (75 %) ». Avec un seul autre lot, aucune moyenne n'est donnée : une comparaison à un seul point n'en est pas une.

« **Levée terminée** » dit que plus rien ne lèvera : les graines qui n'ont pas levé sont soldées (8 pour 40 levés sur 48), l'état de germination du lot passe à « clos », et il ne reste plus de graines en train de lever. Les plants levés, eux, restent à repiquer. Sans « terminée », l'état de germination ne change pas. Une fois déclarée terminée, la levée le reste : un comptage ultérieur met le nombre à jour sans rouvrir la germination.

L'assistant signale sans jamais corriger : un « sur 48 » qui ne correspond pas aux graines semées du lot, plus de levés que de graines semées, un repiquage de plus de plants qu'il n'en a levé. Les chiffres que vous avez dits sont gardés tels quels, accompagnés d'une mention à vérifier. La levée ne se note que sur un lot de pépinière issu d'un semis : un lot de godets sans semis rattaché, ou un lot clôturé, la refuse. Une phrase sur un semis en pleine terre (« les carottes ont levé ») n'est pas une levée de lot : l'assistant le dit et propose de la noter en observation.
