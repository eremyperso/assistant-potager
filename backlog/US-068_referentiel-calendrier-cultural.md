**ID :** US-068
**Titre :** Constituer le référentiel de calendrier cultural et de durées des cultures

**Story :**
En tant que jardinier
Je veux que l'application connaisse, pour chaque culture, ses périodes conseillées de semis et de récolte ainsi que les délais de germination et de récolte attendus
Afin de savoir quand semer, dans combien de temps ma culture lèvera et quand je pourrai récolter, sans ressortir mon affiche de calendrier des semis

**Contexte fonctionnel :**
L'application ne sait rien du calendrier des cultures. `culture_config` ne porte aujourd'hui que le type d'organe de récolte, une description agronomique, l'espacement et la surface au sol par plant. La maquette 2026 affiche pourtant sur chaque tuile de culture une frise des douze mois (semis / plantation / récolte) et une durée de culture — toutes deux codées en dur dans ses données de démonstration.

Le modèle retenu n'est pas celui de la maquette mais celui des calendriers de semis du commerce, plus juste agronomiquement. Trois différences structurantes :

1. **La distinction n'est pas semis / plantation, mais semis à l'intérieur / semis à l'extérieur.** Une culture se sème soit en pépinière (godet, hors sol), soit directement en place — deux fenêtres différentes pour la même culture. Le repiquage n'est pas une fenêtre autonome : il découle du semis en pépinière.
2. **Les fenêtres ne suffisent pas, il faut des durées.** Un calendrier de semis donne, pour chaque culture, le nombre de jours entre le semis et la germination, et entre le semis et la récolte. Ce sont ces durées, et non les fenêtres, qui permettront à **US-070** de recaler le calendrier sur la date réelle de semis du jardinier.
3. **Une culture porte plusieurs itinéraires culturaux.** « Chou-fleur culture précoce / d'été / d'automne / d'hiver », « Carotte d'été / Carotte d'hiver » ne sont pas des variétés mais des conduites de culture, chacune avec sa fenêtre et ses durées propres.

**Arbitrage produit — granularité :** le référentiel s'attache au couple **culture + itinéraire cultural**, jamais à la variété. Aucune source horticole réutilisable ne descend au niveau du cultivar ; y descendre reviendrait à tout saisir à la main. Une variété hérite de l'itinéraire sous lequel elle est conduite.

**Arbitrage produit — climat :** le référentiel est **décliné par zone climatique**. Les fenêtres décalent de plusieurs semaines entre une côte océanique et un climat méditerranéen ; un référentiel unique serait faux pour la majorité des jardiniers. Les **durées**, elles, ne sont pas déclinées : le délai entre semis et récolte relève de la physiologie de la plante, pas de la latitude.

Cette US ne crée aucun écran et ne modifie aucun calcul existant : elle constitue une donnée de référence et la rend corrigeable. Ses consommatrices sont **US-070** (recalage sur les événements réels), l'écran Plan (US-060) et la vue « Cultures » du Lot E.

**Critères d'acceptance :**

*Structure du référentiel*
- [ ] CA1 : Une culture peut porter **un ou plusieurs itinéraires culturaux** nommés (ex. « standard », « culture précoce », « culture d'été », « culture d'automne », « culture d'hiver »). Une culture sans itinéraire nommé en possède un par défaut, implicite, qui n'oblige le jardinier à aucune saisie
- [ ] CA2 : Chaque itinéraire porte trois **fenêtres conseillées** indépendantes, chacune pouvant être vide : semis en pépinière (hors sol), semis en pleine terre, et récolte. Une culture qui ne se sème jamais en godet n'a pas de fenêtre pépinière ; une vivace peut n'avoir qu'une fenêtre de récolte
- [ ] CA3 : Chaque itinéraire porte deux **durées conseillées** : le délai entre le semis et la levée, et le délai entre le semis et la première récolte. Une troisième durée, le délai entre le semis et le repiquage, n'est renseignée que pour un itinéraire passant par la pépinière
- [ ] CA4 : Les durées sont exprimées en jours et peuvent être une fourchette (ex. « 70 à 90 jours ») ; les cultures qui n'en relèvent pas admettent une mention libre (ex. « vivace »). L'affichage ne doit jamais présenter une fourchette comme une date certaine
- [ ] CA5 : L'écartement entre plants **n'est pas ajouté** : `culture_config` porte déjà `espacement` et `surface_m2`, qui font foi. Le référentiel ne duplique pas cette donnée

*Déclinaison par zone climatique*
- [ ] CA6 : Les fenêtres du CA2 sont déclinées par **zone climatique** (a minima : océanique, continental, méditerranéen, montagnard). Les durées du CA3 ne le sont pas — elles sont communes à toutes les zones
- [ ] CA7 : Un potager porte **sa zone climatique**. Elle est pré-positionnée à partir de sa localisation lorsque celle-ci est connue, et reste **modifiable par le jardinier** — c'est lui qui connaît son microclimat, un fond de vallée n'a pas le calendrier du plateau voisin
- [ ] CA8 : Un potager sans zone renseignée reste pleinement fonctionnel : il lit les fenêtres d'une zone par défaut, sans erreur ni écran bloqué

*Alimentation et correction*
- [ ] CA9 : Le référentiel est **pré-rempli à la livraison** pour les cultures réellement présentes dans les données du potager, à partir d'une source de calendrier de semis identifiée. Le pré-remplissage n'écrase jamais une valeur déjà saisie par le jardinier
- [ ] CA10 : Le jardinier peut **consulter et corriger depuis le bot** les fenêtres et les durées d'une culture ; la commande confirme l'ancienne et la nouvelle valeur
- [ ] CA11 : Une correction saisie par un jardinier **ne modifie jamais** ce que lit un autre potager — contrairement à la famille botanique (US-067 / CA7), un calendrier est une préférence légitime, pas un fait botanique. La correction s'appuie sur le mécanisme de fiche personnalisée déjà présent sur `culture_config`
- [ ] CA12 : Le référentiel est retrouvé quelle que soit la casse et l'accentuation du nom de culture, cohérent avec la normalisation appliquée ailleurs aux noms de culture

*Robustesse et non-régression*
- [ ] CA13 : Une culture sans référentiel reste utilisable partout : les écrans affichent une frise neutre et des durées en tiret. **L'application n'invente jamais une période ni un délai**, ni côté serveur ni côté interface
- [ ] CA14 : La création d'une configuration de culture à la volée (déclenchée au premier événement sur une culture inconnue) **n'exige** ni fenêtre ni durée : le référentiel reste facultatif, sous peine de bloquer une saisie vocale sur une question horticole
- [ ] CA15 : Aucune régression sur les lectures existantes de `culture_config` — type d'organe de récolte, calcul de stock végétatif/reproducteur, écran Stocks, écran Statistiques et statistiques du bot conservent exactement leur comportement, vérifié par les tests existants passant sans modification
- [ ] CA16 : Des tests couvrent le pré-remplissage, une culture à plusieurs itinéraires, une culture sans fenêtre pépinière, la déclinaison par zone, un potager sans zone, la correction depuis le bot, son isolement par potager (CA11) et la non-régression du CA15

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et enregistrement (métadonnées de culture)
- Migration BDD requise : **oui** — référentiel de calendrier rattaché à `culture_config` (itinéraires, fenêtres déclinées par zone, durées), et zone climatique sur le potager, avec leur pré-remplissage
- Dépendances : aucune bloquante. **US-069** (distinction pépinière / pleine terre à la saisie) est nécessaire pour que la bonne fenêtre soit appliquée à un semis donné, mais le référentiel peut être constitué avant. **US-070** en est la consommatrice principale
- Voisinage : **US-067** enrichit la même table avec la famille botanique — US indépendante, mais même fichier de migration, à séquencer si les deux sont menées en parallèle
- Point de vigilance : `culture_config` n'est créée qu'à la demande, jamais pré-semée pour un catalogue — le pré-remplissage du CA9 ne doit pas créer de configuration pour des cultures que le jardinier n'a jamais utilisées
- Point de vigilance : la source du pré-remplissage doit être identifiée et sa réutilisation vérifiée avant développement (licence, format, couverture des cultures réellement suivies). C'est le principal risque de chiffrage de cette US
- Point laissé ouvert : l'édition du référentiel depuis l'interface web n'est **pas** traitée ici — elle relève de la vue « Cultures » du Lot E. Le bot suffit à satisfaire l'exigence « corrigeable sans livraison »

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Deux itinéraires pour une même culture
  Given une culture "chou-fleur" portant les itinéraires "culture précoce" et "culture d'hiver"
  When le jardinier consulte le calendrier du chou-fleur
  Then les deux itinéraires sont proposés avec leurs fenêtres et leurs durées propres

Scénario: Culture semée uniquement en pleine terre
  Given une culture "carotte" dont la fenêtre de semis en pépinière n'est pas renseignée
  When le jardinier consulte son calendrier
  Then seules les fenêtres de semis en pleine terre et de récolte sont affichées
  And aucune fenêtre de pépinière n'apparaît

Scénario: Fenêtres décalées selon la zone climatique
  Given une culture "courgette" dont le semis en pleine terre est conseillé en mai en zone continentale et en avril en zone méditerranéenne
  When un potager situé en zone méditerranéenne consulte ce calendrier
  Then la fenêtre de semis en pleine terre démarre en avril

Scénario: Durée identique quelle que soit la zone
  Given une culture "courgette" dont le délai semis → récolte conseillé est de 95 jours
  When deux potagers de zones climatiques différentes consultent ce calendrier
  Then les deux lisent le même délai de 95 jours

Scénario: Potager sans zone climatique renseignée
  Given un potager dont la zone climatique n'est pas renseignée
  When le jardinier consulte le calendrier d'une culture
  Then les fenêtres de la zone par défaut s'affichent
  And aucun écran n'est bloqué

Scénario: Correction propre à un potager
  Given deux potagers utilisant la culture "tomate"
  When le jardinier du premier avance sa fenêtre de semis en pépinière de mars à février
  Then son calendrier de la tomate démarre en février
  And celui du second potager reste inchangé

Scénario: Culture sans référentiel
  Given une culture "topinambour" sans aucune fenêtre ni durée renseignée
  When le jardinier enregistre un semis de topinambour
  Then l'événement est enregistré normalement, sans question sur le calendrier
  And les écrans affichent une frise neutre et des durées en tiret
```

**Labels GitHub :** `us`, `backend`, `cultures`, `referentiel`
