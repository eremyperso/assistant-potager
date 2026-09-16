**ID :** US-175
**Titre :** Servir le pré-diagnostic sur une observation dictée
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que décrire un symptôme à la voix, debout devant le pied malade, me rende les mêmes pistes que la même phrase tapée au calme
Afin de ne pas avoir à retenir que le compagnon comprend mieux au clavier qu'au potager

**Contexte fonctionnel :**
US-165 a livré le pré-diagnostic déterministe. Il fonctionne, **au clavier** : « mes pieds de
tomates ont des taches marron sur les feuilles du bas qui remontent » rend trois pistes ordonnées,
à zéro jeton, sans qu'aucune commande soit à retenir.

**Ce que la vérification du 10/09/2026 a montré, et qui motive cette US :** ce chemin n'existe pas
sur le canal vocal, qui est pourtant le canal principal de l'application.

Les deux canaux ne demandent pas la même chose au routeur :

| Canal | Ce qui est consulté | Résultat sur une description de symptôme |
|---|---|---|
| Texte tapé | règles **puis catalogue** | famille reconnue → pré-diagnostic servi, zéro jeton |
| Vocal | règles **seules** | aucune règle ne tranche → la phrase continue vers l'analyse par le modèle |

L'écart n'est pas un oubli : c'est un arbitrage de coût assumé par US-172 / CA5 — le canal vocal
paie déjà une analyse `intent + parsing` en un seul appel, et lui faire consulter la cascade
entière ajouterait une classification sur tout ce que les règles ne tranchent pas.

La conséquence, elle, n'était pas prévue. La description dictée est alors classée par le modèle, et
son sort dépend de l'intention qu'il y lit :

- lue comme une **question** → la cascade est atteinte, les pistes arrivent ;
- lue comme une **saisie** → la phrase est enregistrée comme une observation, et **aucune piste
  n'est proposée**.

Sans point d'interrogation — qui n'existe pas à la dictée —, les deux lectures sont défendables.
Le jardinier obtient donc, ou non, son pré-diagnostic selon une bascule qu'il ne voit pas et ne
peut pas provoquer.

**L'arbitrage proposé — ne pas choisir entre enregistrer et répondre.** Le faux dilemme est de
trancher entre les deux lectures, car elles sont vraies toutes les deux : une description de
symptôme **est** une observation, et l'enregistrer est juste. Le défaut n'est pas de l'enregistrer,
c'est de n'en rien dire. C'est d'ailleurs exactement la boucle qu'US-165 décrit et que
l'application détient déjà aux deux extrémités :

> observation (enregistrée) → **pré-diagnostic (proposé dans le même échange)** → traitement →
> suivi — une seule histoire, relisible l'année suivante sur la même parcelle.

**Portée réelle :** cette US ne répare pas un défaut d'US-165, elle ferme une **asymétrie de
canal**. La question d'inventaire d'US-173 (« qu'est-ce qui attaque mes poireaux ») a exactement la
même faiblesse à la dictée, pour exactement la même raison. Ce qui est décidé ici vaudra pour elle.

**Critères d'acceptance :**

*Le comportement attendu*
- [ ] CA1 : Une description de symptôme **dictée** reçoit les mêmes pistes, dans le même ordre et
  avec le même texte, que la même phrase tapée. Il n'existe pas de second chemin de réponse : le
  canal ne peut pas se mettre à répondre autrement, sans quoi les deux divergeront
- [ ] CA2 : L'observation est **enregistrée ET** les pistes proposées, dans le même échange. Ni
  l'un sans l'autre : le geste garde sa date et son lieu, le jardinier repart avec des pistes
- [ ] CA3 : L'événement journalisé reste une **observation ordinaire**. Aucun type d'action nouveau,
  et aucune piste écrite dans le journal — une suspicion n'est pas un fait constaté, et l'y inscrire
  la ferait relire l'année suivante comme si elle en était un

*Le coût — critère bloquant*
- [ ] CA4 : 🔴 Le pré-diagnostic reste **à zéro jeton**, et le canal vocal ne paie **aucun appel
  modèle supplémentaire** par rapport à aujourd'hui. Une US qui rendrait la dictée plus chère pour
  la rendre plus intelligente échangerait un défaut visible contre un défaut invisible
- [ ] CA5 : L'arbitrage d'US-172 / CA5 — « le canal vocal ne consulte que l'étage des règles » — ne
  se rouvre que sur une **mesure**, jamais sur une intention. Si la solution retenue consulte le
  catalogue depuis ce canal, le coût en lectures et en latence est mesuré et publié

*L'honnêteté — héritée d'US-165, jamais réécrite pour ce canal*
- [ ] CA6 : La formulation reste celle d'US-165 (« cela peut évoquer », jamais « c'est »),
  **réutilisée telle quelle**. Une seconde formulation propre au vocal s'éroderait de son côté sans
  que personne ne le voie
- [ ] CA7 : Un symptôme **non reconnu** enregistre l'observation et le dit. Jamais une piste forcée,
  et jamais un silence : le jardinier doit savoir que sa note est bien prise, même quand
  l'application n'a rien à en dire
- [ ] CA8 : Aucun dosage, aucune recommandation de produit — le garde-fou d'US-165 / CA7 vaut ici
  sans exception

*Les frontières*
- [ ] CA9 : Une saisie qui n'est **pas** une description de symptôme n'est jamais détournée.
  « j'ai arrosé les tomates », « planté 12 pieds de courgette » s'enregistrent comme avant, sans
  qu'aucune piste ne soit proposée
- [ ] CA10 : Une **question d'inventaire** dictée (« qu'est-ce qui attaque mes poireaux ») reçoit
  l'inventaire d'US-173, pas un pré-diagnostic. La frontière entre décrire et demander est celle
  d'US-165 ; ce canal l'applique, il ne la redéfinit pas
- [ ] CA11 : Le canal **texte est inchangé**, et c'est vérifié. Une régression sur le chemin qui
  fonctionne coûterait plus que ce que cette US apporte

*La mesure*
- [ ] CA12 : Le corpus d'US-165 (`tests/corpus/us165_prediagnostic.csv`) est rejoué **sous forme
  dictée** — sans point d'interrogation, sans virgule, sans apostrophe fiable. Les 19 entrées du
  périmètre v1 doivent produire les **mêmes pistes** qu'à l'écrit
- [ ] CA13 : La mesure dit aussi ce que l'US **casse**, pas seulement ce qu'elle répare : sur le
  corpus de saisies réelles (`tests/corpus/us094_saisies_reelles.csv`), aucune saisie ordinaire ne
  doit basculer vers une réponse au lieu d'être enregistrée

*Tests*
- [ ] CA14 : Des tests couvrent un symptôme dicté reconnu, un symptôme dicté inconnu, une saisie
  ordinaire non détournée, une question d'inventaire dictée, l'absence d'appel modèle
  supplémentaire, et la non-régression du canal texte

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | analyse
- Migration BDD requise : **non** — aucune donnée nouvelle, seul l'aiguillage d'un canal change
- Dépendances : **US-165** (le pré-diagnostic lui-même, bloquante), **US-172** (dont elle rouvre
  l'arbitrage de coût sur le canal vocal). Voisinage avec **US-173**, qui souffre du même écart et
  bénéficiera de la même décision
- **Risque — la bascule silencieuse :** le danger n'est pas de mal répondre, c'est de transformer
  une saisie en réponse. Un geste qu'on croit enregistré et qui ne l'est pas est une perte de
  données que le jardinier ne découvre que des mois plus tard, en relisant son journal. C'est le
  CA9 et le CA13 qui le tiennent, et ils sont bloquants tous les deux

**Notes techniques (pour Persona Developer) :**
- Le point d'entrée est unique : le traitement du message vocal, entre la grammaire déterministe
  (qui reconnaît déjà une saisie par construction) et l'analyse par le modèle
- ⚠️ **Ne pas dupliquer la reconnaissance.** `reponses_chiffrees.reconnait_famille()` et
  `repondre_chiffre()` existent et sont déjà le chemin du canal texte. Une seconde reconnaissance
  écrite pour le vocal serait une seconde vérité, qui divergerait au premier ajustement de motif
- Deux pistes se présentent, et **c'est la mesure du CA5 qui tranche**, pas la préférence :
  1. consulter le catalogue depuis le canal vocal, comme le fait le canal texte — symétrie
     complète, au prix de deux lectures SQL brèves sur chaque message vocal ;
  2. reconnaître la famille **après** l'analyse du modèle, quand l'intention lue est une saisie
     d'observation — ne coûte rien de plus, et enregistre le geste, ce que le CA2 demande de toute
     façon
- 🔑 Rappel de méthode, valable une fois de plus : **à la dictée, le point d'interrogation
  n'existe pas.** Toute reconnaissance qui s'appuierait sur la ponctuation est structurellement
  aveugle sur ce canal — c'est déjà ce qui a motivé US-173 / CA3 et US-172 / CA22

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Symptôme dicté, pistes proposées
  Given un jardinier qui dicte "mes pieds de tomates ont des taches marron sur les feuilles du bas"
  When le message vocal est traité
  Then l'observation est enregistrée dans le journal
  And deux à trois pistes ordonnées lui sont proposées dans le même échange
  And chacune est formulée comme une évocation, jamais comme une certitude

Scénario: Mêmes pistes qu'à l'écrit
  Given la même description, une fois dictée et une fois tapée
  When les deux sont traitées
  Then les pistes proposées sont les mêmes, dans le même ordre

Scénario: Symptôme dicté non reconnu
  Given un jardinier qui dicte une description qu'aucun symptôme du référentiel ne couvre
  When le message vocal est traité
  Then l'observation est enregistrée
  And l'application dit qu'elle n'a pas de piste, sans en proposer aucune

Scénario: Saisie ordinaire non détournée
  Given un jardinier qui dicte "j'ai arrosé les tomates ce matin"
  When le message vocal est traité
  Then l'arrosage est enregistré comme avant
  And aucune piste n'est proposée

Scénario: Question d'inventaire dictée
  Given un jardinier qui dicte "qu'est-ce qui attaque mes poireaux"
  When le message vocal est traité
  Then il reçoit l'inventaire des bioagresseurs connus pour le poireau
  And aucun pré-diagnostic n'est produit

Scénario: Aucun jeton supplémentaire
  Given une description de symptôme dictée
  When le pré-diagnostic est produit
  Then le nombre d'appels au modèle est identique à celui d'avant cette US

Scénario: Le canal texte est inchangé
  Given les 19 entrées du périmètre v1 du corpus d'US-165, tapées
  When elles sont traitées
  Then elles produisent exactement les mêmes réponses qu'avant cette US
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `diagnostic`, `telegram`
