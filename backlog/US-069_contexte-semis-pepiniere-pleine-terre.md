**ID :** US-069
**Titre :** Distinguer le semis en pépinière du semis en pleine terre sur l'événement

**Story :**
En tant que jardinier
Je veux que l'application sache si un semis a été fait en pépinière ou directement en pleine terre
Afin que mes statistiques distinguent les deux filières et que le calendrier conseillé qui m'est présenté soit celui du bon itinéraire

**Contexte fonctionnel :**
Un semis suit l'un de deux itinéraires : semé en godet hors sol puis repiqué en parcelle (filière `semis → mise en godet → plantation`), ou semé directement en place (`semis → récolte`). L'application enregistre aujourd'hui les deux sous le même `type_action` `semis`, sans les distinguer. La filière n'est reconstituable qu'après coup, et seulement si une mise en godet a effectivement suivi — un semis en pépinière consulté avant son repiquage est indiscernable d'un semis en place.

Ce manque devient bloquant avec **US-068** : le référentiel de calendrier porte deux fenêtres de semis distinctes, l'une pour la pépinière, l'autre pour la pleine terre. Sans savoir de quel itinéraire relève un semis donné, impossible de choisir la fenêtre à lui appliquer, ni de recaler correctement la projection attendue par **US-070**. Le besoin statistique, lui, préexistait : savoir combien de cultures sont issues de chaque filière est une question que le jardinier se pose déjà en fin de saison.

Cette US remplace et numérote l'ancienne US non numérotée `backlog/US_Distinguer_semis_pepiniere_pleine_terre.md`, rédigée avant l'arrivée du suivi par lot (US-065) et du chaînage complet du cycle de vie (US-029) — **ce fichier est à supprimer à la reprise de cette US.**

**Critères d'acceptance :**
- [ ] CA1 : Un événement de semis porte son **contexte** : pépinière (hors sol, en godet) ou pleine terre (semis direct en parcelle). Le contexte n'a de sens que pour un semis — aucun autre type d'action n'en porte
- [ ] CA2 : Le contexte est reconnu à la saisie vocale ou textuelle quand le jardinier le dit — « semé 50 graines de tomate cerise **en pépinière** » et « semé des carottes rang 3 **en pleine terre** » sont enregistrés dans deux contextes distincts
- [ ] CA3 : Quand le jardinier ne le précise pas, l'application **propose** le contexte le plus probable au regard de la culture et de son référentiel (US-068) plutôt que d'en choisir un silencieusement, et le jardinier confirme ou corrige en un geste. Un semis dont le contexte reste indéterminé est enregistré sans contexte plutôt que d'être classé arbitrairement
- [ ] CA4 : Le contexte est **corrigeable après coup** via le flux de correction existant, sans intervention en base
- [ ] CA5 : Les semis déjà enregistrés sont **repris** à la livraison : un semis suivi d'une mise en godet chaînée (`origine_graines_id`) est reconnu comme un semis en pépinière ; les autres restent sans contexte plutôt que d'être présumés en pleine terre. Aucune donnée existante n'est réécrite sur une supposition
- [ ] CA6 : Les statistiques restituent **deux totaux séparés** — semis en pépinière et semis en pleine terre — par culture et par saison, les semis sans contexte formant un troisième total explicite et non un silence
- [ ] CA7 : Le contexte détermine **quelle fenêtre conseillée** du référentiel s'applique au semis (US-068 / CA2) et sert de point d'ancrage à la projection (US-070)
- [ ] CA8 : Aucune régression sur le calcul de stock : un semis en pépinière continue de ne pas alimenter le stock de culture en place, un semis en pleine terre continue de l'alimenter, exactement comme aujourd'hui. Le chaînage `semis → godet → plantation` (US-029, US-065, US-066) conserve son comportement
- [ ] CA9 : L'absence de contexte ne bloque jamais rien : ni l'enregistrement d'un événement, ni un écran, ni une statistique
- [ ] CA10 : Des tests couvrent la saisie explicite des deux contextes, la proposition du CA3, la correction après coup, la reprise des semis existants du CA5, la séparation statistique du CA6 et la non-régression du CA8

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot), analyse (statistiques), consultation
- Migration BDD requise : **oui** — contexte de semis sur l'événement, nullable, avec la reprise décrite au CA5
- Dépendances : **US-068** (le référentiel fournit l'itinéraire probable du CA3 et les fenêtres du CA7) ; **US-070** en est la consommatrice. Aucune dépendance bloquante pour la partie statistique (CA6), livrable seule
- Remplace : `backlog/US_Distinguer_semis_pepiniere_pleine_terre.md`, à supprimer
- Point de vigilance : le CA3 ne doit pas transformer une saisie vocale en interrogatoire. Si la proposition ne peut pas être faite en un seul geste de confirmation, mieux vaut enregistrer sans contexte — le CA4 permet de corriger plus tard
- Point de vigilance : ne pas confondre le contexte du semis avec la parcelle de destination. Un semis en pépinière est rattaché à une parcelle comme tout événement (contrainte `parcelle_id`), ce qui ne le rend pas pour autant « en pleine terre »

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Contexte dicté explicitement
  Given le jardinier dicte "semé 50 graines de tomate cerise en pépinière"
  When l'événement est enregistré
  Then il porte le contexte "pépinière"
  And il n'alimente pas le stock de culture en place

Scénario: Contexte proposé puis confirmé
  Given le jardinier dicte "semé des carottes rang 3" sans préciser le contexte
  And le référentiel indique que la carotte se sème en pleine terre
  When le bot demande confirmation
  Then il propose "pleine terre" en un seul geste de confirmation
  And l'événement enregistré porte le contexte confirmé

Scénario: Semis laissé sans contexte
  Given le jardinier dicte un semis d'une culture dont l'itinéraire n'est pas déterminable
  When l'événement est enregistré
  Then il est enregistré sans contexte
  And aucun écran ni aucune statistique n'est en erreur

Scénario: Reprise d'un semis existant chaîné
  Given un semis de tomate déjà enregistré, suivi d'une mise en godet chaînée
  When la reprise des données est appliquée
  Then ce semis porte le contexte "pépinière"

Scénario: Reprise sans supposition
  Given un semis de courgette déjà enregistré, sans mise en godet chaînée
  When la reprise des données est appliquée
  Then ce semis reste sans contexte
  And il n'est pas présumé en pleine terre

Scénario: Statistiques séparées
  Given une saison comportant des semis en pépinière, des semis en pleine terre et des semis sans contexte
  When le jardinier consulte ses statistiques de semis
  Then trois totaux distincts sont restitués par culture
```

**Labels GitHub :** `us`, `backend`, `bot`, `cultures`
