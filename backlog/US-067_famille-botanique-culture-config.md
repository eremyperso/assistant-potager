**ID :** US-067
**Titre :** Externaliser la famille botanique des cultures et rendre la rotation calculable

**Story :**
En tant que jardinier
Je veux que la famille botanique de chaque culture soit enregistrée avec la culture et corrigeable sans nouvelle version de l'application
Afin que les écrans qui regroupent mes cultures par famille restent justes quand j'ajoute une culture, sans attendre une livraison

> **⚠️ US amendée le 25/08/2026** — voir `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §1.1.
> Deux décisions ajoutées, tranchées avant implémentation pour éviter une migration rejouée :
> la famille botanique devient une **table de référence** (et non une colonne texte sur
> `culture_config`), et elle porte un **délai de retour recommandé en années** qui rend la rotation
> *calculable* et non seulement *affichable*. CA1 est reformulé, CA12 et CA13 sont ajoutés,
> l'estimation passe de 5 à 6 points. Cette US devient de ce fait le socle de l'`ÉPIC 6 —
> Référentiel de connaissance des cultures` : elle **absorbe l'US-160** initialement prévue par
> `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §8, et US-163 n'a plus à rouvrir la
> migration de `culture_config`.

**Contexte fonctionnel :**
US-061 a livré le regroupement par famille botanique de l'écran Pépinière, tel que le prévoit la maquette 2026. Faute de donnée côté serveur, la famille a été portée depuis la table figée `FAM_OF` de la maquette vers un fichier d'interface : une quarantaine d'entrées en dur, un appariement **exact** sur le nom de culture normalisé, et un repli « Autres » pour tout le reste.

Le défaut est mesuré sur les données réelles du potager : `pâtisson`, `petit pois`, `pois gourmand` et `haricot grimpant` tombent dans « Autres » — le premier par simple oubli, les trois autres parce qu'un nom composé ne trouve pas son genre. Surtout, **toute culture nouvellement dictée au bot y tombera aussi**, jusqu'à ce que quelqu'un pense à modifier le fichier et à livrer une version.

La famille botanique est une donnée horticole attachée à la culture, au même titre que son type d'organe de récolte — pas une constante d'interface. Sa place est dans `culture_config`, où elle devient consultable, corrigeable et durable.

Cette US ne crée pas d'écran : elle déplace une donnée et branche dessus le regroupement déjà livré. Elle prépare également le **Lot E** (vue « Cultures » transverse, §5.3 de `docs/ANALYSE_REFONTE_UI_WEB_2026.md`), qui a besoin de la famille pour ses filtres et son classement — mais ne l'attend pas.

**Périmètre volontairement resserré :** le calendrier cultural (fenêtres conseillées de semis et de récolte, durées germination/récolte, itinéraires, zones climatiques) a d'abord été envisagé ici, puis sorti de cette US — il constitue un référentiel à part entière, porté par **US-068**. Cette US ne traite que la famille botanique.

**Critères d'acceptance :**
- [ ] CA1 : La famille botanique est une propriété de la culture, rattachée à `culture_config` par une **table de référence des familles** côté serveur, et non plus une table figée dans le code de l'interface. Le libellé de la famille n'est écrit **qu'une seule fois**, dans cette table — le corriger le corrige partout où il est affiché
- [ ] CA2 : Les cultures déjà connues de l'application sont **pré-remplies** à la livraison — au minimum celles de la table portée par US-061 et celles réellement présentes dans les données du potager, `pâtisson`, `petit pois`, `pois gourmand` et `haricot grimpant` compris. Le pré-remplissage ne doit jamais écraser une famille déjà saisie par le jardinier
- [ ] CA3 : Une culture dont la famille n'est pas renseignée reste utilisable partout : elle est simplement regroupée sous « Autres ». L'absence de famille n'empêche jamais d'enregistrer un événement, de créer une culture, ni d'afficher un écran
- [ ] CA4 : Le jardinier peut **corriger ou renseigner la famille d'une culture depuis le bot**, sans livraison ni intervention en base ; la commande confirme l'ancienne et la nouvelle valeur
- [ ] CA5 : Une famille corrigée est reflétée **immédiatement** sur l'écran Pépinière au rechargement — le regroupement lit la donnée, il n'en garde pas de copie
- [ ] CA6 : Le regroupement retrouve la famille quelle que soit la casse et l'accentuation du nom de culture saisi (« Céleri », « celeri », « CÉLERI » désignent la même culture), cohérent avec la normalisation déjà appliquée ailleurs aux noms de culture
- [ ] CA7 : La famille d'une culture donnée est **identique quel que soit le potager** : c'est un fait botanique, pas une préférence de jardinier — deux potagers ne peuvent pas classer la tomate dans deux familles différentes
- [ ] CA8 : Le fichier de familles en dur de l'interface (`frontend/src/lib/familles.js`) est **supprimé**, et plus aucune famille botanique ne subsiste en dur côté frontend
- [ ] CA9 : Aucune régression sur les lectures existantes de `culture_config` — le type d'organe de récolte, le calcul de stock végétatif/reproducteur, l'écran Stocks, l'écran Statistiques et les statistiques du bot conservent exactement leur comportement, ce qui est vérifié par les tests existants passant sans modification
- [ ] CA10 : La création d'une configuration de culture à la volée (aujourd'hui déclenchée au premier événement sur une culture inconnue) **n'exige pas** de renseigner la famille : celle-ci reste facultative, sous peine de bloquer une saisie vocale sur une question horticole
- [ ] CA11 : Des tests couvrent le pré-remplissage, la correction depuis le bot, une culture sans famille, une culture au nom composé (`petit pois`), la normalisation casse/accents du CA6, et la non-régression du CA9
- [ ] CA12 : La famille botanique porte un **délai de retour recommandé, exprimé en années** — la durée minimale avant de replanter la même famille sur une parcelle. Il est pré-rempli pour les familles connues, **nullable**, et corrigeable depuis le bot au même titre que la famille elle-même. Étant un attribut *de la famille* et non *de la culture*, il n'est saisi qu'une fois et vaut pour toutes les cultures qui s'y rattachent
- [ ] CA13 : Une famille dont le délai de retour n'est pas renseigné **n'empêche aucun affichage** : elle rend simplement l'avertissement de rotation indisponible pour les cultures de cette famille. L'application dit alors qu'elle ne sait pas, elle ne conclut jamais à l'absence de conflit
- [ ] CA14 : Des tests couvrent le pré-remplissage du délai de retour, sa correction depuis le bot, une famille sans délai, et le fait qu'une correction de délai vaut immédiatement pour **toutes** les cultures de la famille sans avoir à les reprendre une à une

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et enregistrement (métadonnée de culture)
- Migration BDD requise : **oui** — table de référence des familles botaniques (libellé + délai de retour) et rattachement depuis `culture_config`, avec leur pré-remplissage
- Dépendances : **US-061** (consommatrice du regroupement, livrée avec la table provisoire à retirer) ; prépare le **Lot E** (§5.3) sans en dépendre
- Voisinage : **US-068** enrichit la même table avec le référentiel de calendrier cultural. Les deux US sont indépendantes et peuvent être jouées dans n'importe quel ordre, mais elles touchent le même fichier de migration — à séquencer si elles sont menées en parallèle
- Prérequis de : **US-163** (associations et rotation calculable) et **US-140** (corpus agronomique) de l'`ÉPIC 6`. C'est le CA12 qui les débloque : sans délai de retour, US-163 devait rouvrir la migration de `culture_config`
- **Arbitrage tranché — table de référence, pas colonne texte :** un délai de retour est un attribut *de la famille*, pas *de la culture*. Porté en colonne sur `culture_config`, il se duplique sur chaque culture de la famille et devient incohérent à la première correction — le jardinier corrige « Solanacées : 4 ans » sur la tomate et la pomme de terre reste à 3. La table de référence rend la correction unique par construction, et elle est la seule forme cohérente avec le CA7
- Point de vigilance : `culture_config` n'est créée qu'à la demande, jamais pré-semée pour un catalogue de cultures — le pré-remplissage du CA2 ne doit donc pas créer de configuration pour des cultures que le jardinier n'a jamais utilisées, sous peine de peupler ses écrans de cultures fantômes. La mesure du 25/08/2026 confirme le risque : **14 des 54 configurations existantes ne portent aucun événement**
- Point laissé ouvert : l'édition de la famille depuis l'interface web n'est **pas** traitée ici — elle relève de la vue « Cultures » du Lot E. Le bot suffit à satisfaire l'exigence « modifiable dynamiquement »

**Estimation :** 6 points *(5 initialement, +1 au titre de l'amendement du 25/08/2026)*

**Scénario Gherkin :**
```gherkin
Scénario: Regroupement lu depuis la donnée et non depuis le code
  Given une culture "tomate" dont la famille enregistrée est "Solanacée"
  When le jardinier consulte l'écran "Pépinière"
  Then ses lots de tomate sont regroupés sous "Solanacée"

Scénario: Culture au nom composé correctement classée
  Given une culture "petit pois" pré-remplie en "Fabacée"
  When le jardinier consulte l'écran "Pépinière"
  Then ses lots de petit pois sont regroupés sous "Fabacée" et non sous "Autres"

Scénario: Correction sans livraison
  Given une culture "pâtisson" classée par erreur dans "Autres"
  When le jardinier corrige sa famille en "Cucurbitacée" depuis le bot
  Then le bot confirme le passage de "Autres" à "Cucurbitacée"
  And l'écran "Pépinière" regroupe ses lots de pâtisson sous "Cucurbitacée" au rechargement suivant

Scénario: Nouvelle culture sans famille connue
  Given une culture "topinambour" dictée au bot pour la première fois, sans famille renseignée
  When le jardinier enregistre un semis de topinambour
  Then l'événement est enregistré normalement, sans question sur la famille
  And l'écran "Pépinière" regroupe ce lot sous "Autres"

Scénario: Casse et accents indifférents
  Given une culture enregistrée sous le nom "céleri", famille "Apiacée"
  When un événement est saisi sur "CELERI"
  Then le lot correspondant est regroupé sous "Apiacée"

Scénario: Le délai de retour est porté par la famille, pas par la culture
  Given la famille "Solanacée" dont le délai de retour est de 3 ans
  And les cultures "tomate", "poivron" et "pomme de terre" rattachées à cette famille
  When le jardinier corrige le délai de retour des Solanacées à 4 ans depuis le bot
  Then le bot confirme le passage de 3 à 4 ans
  And les trois cultures partagent le nouveau délai sans correction supplémentaire

Scénario: Famille sans délai de retour renseigné
  Given une famille "Autres" dont le délai de retour n'est pas renseigné
  When le jardinier consulte une culture rattachée à cette famille
  Then la culture s'affiche normalement, regroupée sous "Autres"
  And aucun avertissement de rotation n'est produit pour cette culture
  And l'application n'affirme pas pour autant l'absence de conflit

Scénario: Aucun impact sur les écrans existants
  Given un potager avec des cultures végétatives et reproductrices
  When l'écran Stocks, l'écran Statistiques et les statistiques du bot sont consultés
  Then ils affichent exactement les mêmes valeurs qu'avant cette évolution
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `backend`, `cultures`
