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

La différence entre les graines semées et celles déjà repiquées donne ce qui est encore en train de lever. Trois états sont possibles pour un lot : en cours, quand des graines restent à lever et que les repiquages ont été déclarés complètement ; clos, quand tout a été soldé ; indéterminé, quand un repiquage n'a pas dit de combien de graines il venait. L'état indéterminé n'est jamais présenté comme un lot en cours : une information manquante ne se transforme pas en attente prometteuse.

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
**On parle aussi de :** que faire aujourd'hui ; à repiquer ; à endurcir ; prêts pour le plan ; à semer ; lots du plus urgent au plus calme ; échéance d'un lot ; action suggérée

Pour chaque lot, l'assistant calcule ce qu'il y a à faire et dans quel ordre. Il répond à quatre questions : quels lots sont **à repiquer**, lesquels sont **à endurcir**, quels plants sont **prêts pour le plan**, et quels légumes sont **à semer** (la fenêtre de votre zone est ouverte et aucun lot de ce légume n'est en cours). Chaque lot porte aussi une action suggérée, une seule : Repiquer, Noter la levée, Mettre en terre ou Clôturer. Les lots sont rangés du plus urgent au plus calme : d'abord les retards, du plus grand au plus petit, puis les échéances à venir, de la plus proche à la plus lointaine, puis les lots sans échéance, et tout en dernier les lots dormants. Ces indications arrivent dans la Pépinière de l'application par étapes ; le calcul, lui, est le même partout.

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

Elle montre, du haut vers le bas : le numéro, la culture et la variété, le jour du semis et le nombre de jours écoulés, l'emplacement et son type ; l'**échéance** en clair et datée (« En retard de 6 jours — repiquage attendu entre le 11 et le 13 septembre »), avec la raison quand elle ne peut pas être calculée ; les **gestes** ; puis la **traçabilité** du lot : graines semées, levés, taux de levée, plants repiqués en godet, pertes, ventes, plants mis en terre, godets restants, graines encore en germination. Un tiret veut dire « aucun geste de ce type », jamais zéro. « Détail du lot » ouvre le cycle de vie complet, déplacements compris.

Les gestes proposés suivent l'état du lot, **le geste suggéré en premier** : *Repiquer en godet* s'il reste des graines en germination, *Mettre en terre* s'il reste des godets, *Déclarer une perte* s'il reste quelque chose, *Déplacer* si votre potager compte au moins deux pépinières, *Clôturer le lot* s'il est dormant. Un lot de godets sans semis rattaché n'a ni repiquage ni levée. Un lot terminé ou clôturé s'ouvre sans aucun geste et garde sa traçabilité.

**Un bouton ne fait que préparer.** Il remplit le geste avec le lot, la culture, la variété et les quantités connues, puis ouvre votre compagnon Telegram, qui vous le relit : le geste ne compte qu'après votre « Confirmer ». À côté du bouton, la phrase équivalente à dire au compagnon est proposée (« mise en godet 30 plants du lot 128 »). Un membre en lecture seule voit la fiche entière, sans bouton.

## Comment clôturer un lot définitivement

**Intention :** guide
**On parle aussi de :** clôturer un lot ; solder un lot ; fermer un lot ; abandonner un lot ; lot dormant à clôturer ; clôture du lot

**Clôturer** un lot le solde **définitivement** : tous ses godets restants et toutes ses graines, levées ou non. Il n'a plus rien à faire, n'apparaît plus dans les échéances et sort du stock. Le bouton est proposé sur un lot dormant ; il dit, avant que vous appuyiez, ce qu'il solde (« 40 godets et 20 graines non levées »). Comme tout geste de la fiche, il passe par le compagnon : « clôture du lot 128 — 40 godets et 20 graines soldés. C'est correct ? ». Les nombres sont relus au moment où vous confirmez. Un lot déjà clôturé ou déjà épuisé est refusé : rien n'est enregistré. L'historique du lot — semis, plants obtenus, mises en terre — n'est jamais réécrit.

Vous pouvez aussi le dire directement : « clôture du lot 128 ». Un geste préparé depuis l'application attend dans votre fil de gestes en attente, où le compagnon vous le rappelle.

## Pourquoi un lot n'a pas d'échéance

**Intention :** diagnostic
**On parle aussi de :** échéance manquante ; valeur non renseignée ; pas de repiquage attendu ; pas de mise en terre prévue ; pourquoi aucune date

L'assistant n'invente jamais une date. Sans la donnée nécessaire, le lot n'a tout simplement pas d'échéance, et la raison est dite : « non renseigné » quand le calendrier ne porte pas la durée voulue, « date inconnue » pour des plants arrivés sans semis rattaché. Une durée n'est jamais déduite d'une autre : ni de la levée, ni du temps avant la mise en terre. Un lot sans échéance n'est donc ni en retard ni à endurcir ; pour qu'il en ait une, renseignez la durée manquante avec `/calendrier duree`, pour votre potager.
