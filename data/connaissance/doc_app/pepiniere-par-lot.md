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

Chaque lot affiche son emplacement du moment : la pépinière et son type (chaude ou froide). L'assistant le lit dans cet ordre, et s'arrête au premier trouvé : la dernière mise en godet dont vous avez dit la pépinière, sinon la pépinière où le semis a été fait, sinon « emplacement non renseigné ». Un semis fait sans pépinière dite n'est donc jamais rattaché d'office à « la » pépinière, même s'il n'y en a qu'une. Le lot des godets sans semis rattaché prend l'emplacement de sa dernière mise en godet localisée, sinon il reste non renseigné. Avec une date de référence antérieure à une mise en godet, le lot est lu à l'emplacement qu'il avait alors.

Un lot n'a qu'un seul emplacement. Si vous avez posé une partie de vos godets sous le châssis froid et l'autre dans la serre, le lot se lit à la dernière pépinière que vous avez dite ; l'application ne tient pas la répartition d'un lot entre deux pépinières. Ce détail par emplacement ne change aucun total : vos plants restent comptés par culture et par variété.
