**ID :** US-173  
**Titre :** Répondre en langage naturel à ce qui attaque une culture, sans jeton  
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux demander « qu'est-ce qui attaque mes poireaux ? » avec mes mots, à la voix comme au clavier
Afin d'obtenir la réponse que l'application détient déjà en base, au lieu de la voir soit inventée par un modèle, soit enregistrée comme un événement

**Contexte fonctionnel :**

US-162 a livré les tables — une identité par bioagresseur, une arête vers chaque culture qu'il
attaque — et le service de lecture qui les restitue à coût nul. Elle a livré **un seul lecteur** :
la commande `/bioagresseur lister <culture>`. Le référentiel est donc exact, complet et
inaccessible à qui ne connaît pas la commande.

La mesure faite le 07/09/2026 sur le routeur, en l'état du code, est sans ambiguïté :

| Formulation | Ce qui se passe aujourd'hui |
|---|---|
| `/bioagresseur lister poireau` | répond depuis la table, zéro jeton ✅ |
| « qu'est-ce qui attaque mes poireaux ? » | **aucune règle ne matche** → classée par le modèle, puis répondue par le modèle |
| « quelles maladies sur mes tomates ? » | idem |
| « à quoi dois-je m'attendre sur mes poireaux ? » | idem |
| « qu'est-ce qui attaque mes poireaux » *(sans « ? »)* | **classée ACTION → enregistrée comme un événement d'observation** |

Deux défauts distincts, et le second est le plus grave.

**Le premier est un gaspillage doublé d'un mensonge.** La question part au modèle pour être
classée, puis au modèle pour être répondue — deux appels payants — et la réponse est tirée des
connaissances générales du modèle, **pas des arêtes du potager**. L'application ignore son propre
référentiel au moment précis où il répondrait.

**Le second fait écrire à la place de répondre.** `attaque` est une variante de l'action canonique
`observation` dans le référentiel d'actions ; la règle de geste la reconnaît en tête de phrase et
n'est neutralisée que par un point d'interrogation final. Or le compagnon est **dicté à la voix**,
et la transcription ne restitue pas systématiquement la ponctuation. La question phare de l'US-162,
posée à l'oral, devient une ligne dans le journal. Ce défaut préexiste à US-162 ; celle-ci le rend
seulement voyant, en promettant de répondre à cette question exacte.

La mécanique nécessaire existe déjà et n'attend qu'une famille de plus : `reponses_chiffrees`
(US-096) porte ses gabarits, ses détecteurs et ses agrégateurs, et le routeur traite le catalogue
**comme une règle** — une question que les gabarits savent servir n'atteint jamais le modèle, pas
même pour être classée. Cette US étend ce catalogue, pour la première fois, à une donnée du
**référentiel partagé** et non plus aux seuls événements du potager.

**Frontière avec US-172, à tenir explicitement.** « Montre-moi les bioagresseurs du poireau » est
une **commande** dictée : elle relève de US-172, qui la traduira en `/bioagresseur lister poireau`.
« Qu'est-ce qui attaque mes poireaux ? » est une **question** : elle relève de cette US, servie par
gabarit à l'étage 1. Les deux chemins doivent aboutir au même contenu sans qu'aucun ne réimplémente
l'autre — c'est le même service de lecture qui est appelé.

**Critères d'acceptance :**

*Reconnaître la question, sans jeton*
- [ ] CA1 : Une question portant sur ce qui attaque une culture est reconnue **par règle**, sans aucun appel au modèle — ni pour la classer, ni pour la répondre. Elle entre au catalogue de réponses chiffrées, que le routeur consulte avant le modèle
- [ ] CA2 : Les trois registres sont couverts : le ravageur (« qu'est-ce qui attaque mes poireaux »), la maladie (« quelles maladies sur mes tomates »), et l'anticipation (« à quoi dois-je m'attendre sur mes courgettes »). Le vocabulaire du jardinier et celui de l'agronome — « ravageur », « nuisible », « bêtes », « parasites », « bioagresseur »
- [ ] CA3 : 🔴 **La ponctuation ne décide de rien.** Une question dictée sans point d'interrogation est traitée comme une question. Aucune formulation interrogative portant sur les bioagresseurs ne peut être enregistrée comme un événement — c'est le défaut mesuré ci-dessus, et le corriger est un préalable, pas un effet de bord attendu
- [ ] CA4 : Une **saisie réelle** d'observation reste une saisie : « observé une attaque de mildiou sur les tomates » enregistre un événement, comme aujourd'hui. Les deux formes sont testées en regard l'une de l'autre — c'est la confusion la plus probable de cette US

*Répondre honnêtement*
- [ ] CA5 : La réponse est un **gabarit assemblé** depuis la base, jamais un texte rédigé par un modèle, et reprend l'ordre métier d'US-162 : `courant` d'abord, puis `occasionnel`, puis `rare`
- [ ] CA6 : Une période de risque non renseignée se lit « période non renseignée », jamais comblée
- [ ] CA7 : Une culture connue **sans aucun bioagresseur rattaché** reçoit la formulation d'honnêteté d'US-162 (CA12) : l'application n'a pas l'information, et ne conclut pas que la culture n'est pas exposée. Une culture **inconnue** reçoit un message différent — ne rien savoir d'une culture connue et ne pas connaître la culture sont deux situations distinctes
- [ ] CA8 : L'isolation d'US-162 est respectée : la réponse réunit le savoir partagé et celui du potager qui interroge, jamais celui d'un autre potager
- [ ] CA9 : L'attribution de la source accompagne la réponse, dédupliquée, comme pour les autres réponses dérivées du référentiel
- [ ] CA10 : **Aucun dosage, aucune recommandation d'emploi d'un produit.** Réaffirmation du CA10 d'US-162 : la restitution ne peut rien prescrire, et l'énoncé renvoie à la source officielle si la question dérive vers le traitement

*Ne pas dédoubler ce qui existe*
- [ ] CA11 : La réponse est produite par **le service de lecture d'US-162**, jamais par une requête réécrite pour l'occasion. `/bioagresseur lister`, la question en langage naturel et la commande dictée d'US-172 traversent le même code — trois portes, une seule vérité
- [ ] CA12 : Le détecteur de culture réutilise la résolution existante du catalogue chiffré ; aucune seconde stratégie de reconnaissance de culture n'est introduite

*Mesure — la couverture ne se suppose pas*
- [ ] CA13 : Un **corpus versionné** dans les tests porte au minimum **trente formulations réelles** couvrant les trois registres du CA2, avec et sans ponctuation, accentuées et non accentuées. Il contient aussi les phrases voisines à **ne pas** capter : la saisie d'observation du CA4, la question de traitement (« que faire contre le mildiou ? », qui reste du savoir), et la commande dictée du périmètre d'US-172
- [ ] CA14 : Seuil d'acceptation : **≥ 90 % des formulations du corpus reconnues par règle**, et **0 formulation interrogative enregistrée comme événement** — ce second chiffre est un couperet, pas un objectif
- [ ] CA15 : La part de questions servies sans appel au modèle est journalisée comme les autres décisions de routage (origine `regle`, étage `donnee`), matière première d'US-097

*Tests*
- [ ] CA16 : Des tests couvrent la reconnaissance par règle sans appel au modèle, la question dictée sans ponctuation, la saisie d'observation non captée, la culture sans arête, la culture inconnue, l'isolation entre potagers, et l'identité de contenu entre la commande et la question

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | consultation | analyse
- Migration BDD requise : **non** — les tables d'US-162 suffisent, cette US ne fait que les lire
- Dépendances : **US-162** (bloquante — les tables et le service de lecture), **US-096** (le catalogue de réponses chiffrées, étendu ici), **US-093/US-170** (le routeur). Frontière à tenir avec **US-172** (commande dictée), qui peut être livrée avant ou après sans conflit
- **Arbitrage tranché — une question, pas une commande :** on n'ajoute pas un synonyme de `/bioagresseur` au routeur, on ajoute une **famille de réponse** au catalogue chiffré. La différence est mesurable : une famille du catalogue court-circuite le modèle jusque dans la classification, un synonyme de commande ne le ferait pas
- **Arbitrage tranché — corriger le routage de `attaque` ici, et pas ailleurs :** le défaut est antérieur à cette US, mais il la rend inopérante à la voix. Le corriger dans une US séparée ferait livrer une fonctionnalité qui échoue sur son cas d'usage principal
- ⚠️ Rappel de mesure : la production porte **96 bulletins `[AUTO-METEO]` sur 321 événements**. Le corpus de formulations doit être bâti sur des saisies réelles hors bulletins, faute de quoi un tiers du matériau est du bruit machine

**Notes techniques (pour Persona Developer) :**
- Le point d'ancrage est `app/services/reponses_chiffrees` : une famille de gabarits, un détecteur, un agrégateur — la structure existante, sans nouveau mécanisme. C'est `llm/routeur._regle_par_catalogue` qui fait ensuite l'économie de l'appel modèle
- Le défaut du CA3 se situe au croisement de `utils/actions.ACTION_MAP` (où `attaque` est une variante de `observation`) et de la règle de geste du routeur, neutralisée par le seul `?` final. Corriger sans affaiblir la reconnaissance des saisies réelles est l'enjeu du CA4
- La lecture doit passer par le service d'US-162, qui porte déjà l'ordre par fréquence, l'isolation par potager et la recomposition d'attribution

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: La question posée avec ses mots
  Given une culture "poireau" reliée à plusieurs bioagresseurs
  When le jardinier demande "qu'est-ce qui attaque mes poireaux ?"
  Then la liste est restituée, ordonnée par fréquence
  And aucun appel à un modèle de langage n'a lieu, pas même pour classer la question

Scénario: La même question dictée, sans ponctuation
  Given une culture "poireau" reliée à plusieurs bioagresseurs
  When le jardinier dicte "qu'est-ce qui attaque mes poireaux"
  Then la même liste est restituée
  And aucun événement n'est enregistré

Scénario: Une observation réelle reste une saisie
  Given un jardinier qui constate une attaque
  When il dicte "observé une attaque de mildiou sur les tomates"
  Then l'événement est enregistré comme une observation
  And aucune liste de bioagresseurs n'est restituée

Scénario: Culture connue, aucune information
  Given une culture "ail" sans aucun bioagresseur rattaché
  When le jardinier demande ce qui l'attaque
  Then l'application répond qu'elle n'a pas l'information
  And elle précise que cela ne signifie pas que la culture n'est pas exposée

Scénario: Culture inconnue
  Given une culture "salsifis" absente du référentiel
  When le jardinier demande ce qui l'attaque
  Then l'application dit ne pas connaître cette culture
  And le message diffère de celui d'une culture connue sans information

Scénario: Un bioagresseur local ne fuit pas
  Given un bioagresseur ajouté pour le potager "Jardin de Vitry"
  When un jardinier d'un autre potager pose la question sur la même culture
  Then le bioagresseur local ne lui est pas restitué

Scénario: La question ne devient pas une prescription
  Given un jardinier qui enchaîne "et je traite avec quoi ?"
  When la réponse est produite
  Then aucun produit ni dosage n'est donné
  And la source officielle est citée

Scénario: Trois portes, une seule vérité
  Given une culture "tomate" et ses bioagresseurs
  When le jardinier utilise la commande, puis pose la question, puis dicte la commande
  Then les trois restitutions portent le même contenu
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `referentiel`, `routage`
