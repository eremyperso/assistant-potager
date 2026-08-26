# Corpus — Questions de potagistes amateurs (US-140 / CA11)

> **Rédigé le :** 25/08/2026 · **Révisé le :** 25/08/2026 (contrôle de vague 0)
> **Usage :** jeu de mesure du CA11 d'US-140 (rappel de la bonne fiche dans les trois premiers
> résultats, cible ≥ 80 %), calibration du cache sémantique (US-122a), jeu de test
> `classify_intent()` → `INTERROGER` (US-092).
> **Provenance :** corpus **synthétique rédigé de zéro**. Aucune reproduction de contenu tiers.
> Libre d'usage commercial — cohérent avec l'arbitrage 1 (option A, zéro CC-BY-SA) de
> `VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1.
> **Garde-fou respecté :** aucune valeur chiffrée (durée, dose, espacement) n'apparaît dans ce
> corpus — cf. US-140 / CA13 (a).

**Structure de chaque entrée :** `symptôme décrit → hypothèse ou résolution → période`

---

## ⚠️ Périmètre de mesure — à lire avant d'exploiter le corpus

La v1 du référentiel ne couvre que **dix cultures** (`VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md`
§3.1) : tomate, haricot, courgette, chou, carotte, concombre, cornichon, poivron, ail, blette.

Les entrées portant sur une autre culture sont marquées **hors périmètre v1** dans la table de la
partie 2. Elles ne doivent **pas** entrer dans le calcul du taux du CA11 : aucune fiche
correspondante n'existera en v1, et les compter mécaniquement plafonnerait la mesure sous le seuil
de 80 % pour une raison de découpage et non de qualité de recherche.

Elles gardent une utilité propre : ce sont les cas où le comportement attendu est **« je n'ai pas
de fiche sur cette culture »** — un test d'honnêteté de la cascade, pas un test de rappel.

- **19 entrées dans le périmètre v1** → assiette de la mesure de rappel du CA11
- **25 entrées hors périmètre v1** → test de non-réponse

---

## Partie 1 — Corpus brut (style dicté, 44 entrées)

### Hiver / fin d'hiver

1. mes semis de tomates sur le rebord de la fenêtre font des tiges toutes fines et molles → pas assez de lumière je pense, février
2. mes plants de poireaux en godet sont tombés d'un coup au ras de la terre → on m'a dit fonte des semis, mars
3. les feuilles de mes choux d'hiver sont couvertes d'un truc gris poudreux → jamais su ce que c'était, janvier
4. mes carottes ont mal levé, il y a des trous dans le rang → jamais su pourquoi, mars
43. j'ai planté mon ail dans un coin du potager qui reste toujours humide, les caïeux ont pourri sans jamais lever → trop d'eau et terre trop lourde paraît-il, plantation de décembre

### Printemps

5. il y a plein de petits trous ronds dans les feuilles de mes radis → les altises paraît-il, avril
6. j'ai des bestioles noires collées en grappe en haut de mes fèves → des pucerons noirs, avril
7. mes salades sont mangées la nuit, il reste que le trognon → les limaces après les pluies, début mai
8. mes haricots ne lèvent pas, j'ai gratté les graines sont molles et pourries → terre trop froide et trop mouillée, semis de mai
9. il y a des petites bêtes rayées jaune et noir sur mes pommes de terre, et des larves rouges → les doryphores, mai
10. mes fraisiers font des feuilles magnifiques et des stolons partout mais presque pas de fruits → trop d'azote d'après ma belle-mère, mai
11. les feuilles de ma rhubarbe sont grignotées sur les bords en dents de scie → limaces ou des charançons, mai
12. mes épinards montent en graine à peine sortis de terre → semés trop tard je crois, fin mai
44. mes feuilles d'ail ont des traits orange qui partent en poussière quand je les frotte → c'était de la rouille, mai
13. mes asperges ont des petites bêtes noires et oranges sur les tiges après la récolte → des criocères, juin
14. mes pieds d'artichaut ont le cœur plein de pucerons → pucerons tout simplement, juin
15. mes salades montent tout de suite en graine, elles font une tige au milieu → la chaleur, courant juin

### Été

16. mes pommes de terre ont des taches brunes sur les feuilles et les tiges qui noircissent → le mildiou après la semaine humide, fin juin
17. mes petits pois sont couverts de blanc en fin de saison → de l'oïdium, fin juin
18. mes radis sont creux à l'intérieur et piquants comme du poivre → arrosés trop irrégulièrement, juin
19. mes pieds de tomates ont des taches marron sur les feuilles du bas qui remontent → mildiou d'après le voisin, après les orages de mi-juillet
20. les feuilles de mes courgettes ont de la poudre blanche → c'était de l'oïdium, fin juillet
21. mes courgettes font plein de fleurs mais les petits fruits jaunissent et pourrissent au bout → pas assez d'abeilles pour polliniser, juillet
22. les feuilles de mes tomates s'enroulent en cuillère vers le haut → jamais su, ça a passé tout seul, juillet
23. mes feuilles de blettes sont cloquées avec des galeries claires dedans → des mineuses, juillet
24. mes poivrons sous la serre perdent toutes leurs fleurs sans faire de fruit → trop chaud sous la serre, juillet
41. mes cornichons deviennent amers et jaunissent sur pied dès que je passe deux jours sans aller cueillir → cueillis trop tard je pense, juillet
25. il y a des fils comme des toiles d'araignée sur mes aubergines et les feuilles sont piquetées → des araignées rouges, août
26. mes tomates ont le cul noir → cherché sur internet, manque de calcium paraît-il, début août
27. mes concombres sont amers, immangeables → arrosage irrégulier paraît-il, août
28. mes choux sont mangés, il ne reste que les nervures → les chenilles de la piéride, août
29. mes betteraves ont des petites taches rondes claires sur les feuilles → jamais été sûr, cercosporose peut-être, août
30. mes oignons pourrissent au collet une fois rentrés au sec → mal séchés je crois, août
31. mes melons n'ont aucun goût, c'est de l'eau → trop arrosés juste avant de les cueillir, août
32. il y a des petits vers blancs dans mes framboises quand je les cueille → le ver du framboisier, juillet
42. mes pieds de cornichons ont les feuilles marbrées jaune et vert et les nouvelles pousses sont toutes rabougries → une maladie qui se transmet par les pucerons d'après le voisin, août

### Automne

33. mes carottes sont fourchues, elles font deux ou trois jambes → j'ai trop fumé la terre je crois, arrachage de septembre
34. mes potirons pourrissent sur le dessous là où ils touchent la terre → l'humidité, il fallait mettre une planche dessous, septembre
35. mes pieds de choux flétrissent en pleine journée et les racines sont toutes boursouflées → la hernie du chou, septembre
36. mes feuilles de céleri ont des taches brunes avec des points noirs dedans → septoriose d'après le forum, septembre
37. mes navets sont véreux avec des galeries sous la peau → la mouche du chou, octobre
38. mes poireaux ont des pointes jaunes et des traits orange comme de la rouille → c'était la rouille, octobre
39. quand je coupe mes poireaux il y a des galeries et des petites bêtes dans le fût → la mouche du poireau, récolte de novembre
40. ma mâche fond sur place, les plants deviennent mous et disparaissent → semé trop dense et trop humide, novembre

---

## Partie 2 — Table structurée

Colonne **v1** : ✅ = culture du périmètre initial, entre dans la mesure de rappel du CA11 ·
— = hors périmètre v1, sert de test de non-réponse.

| # | v1 | Culture | Symptôme (mots du potagiste) | Hypothèse / résolution | Période | Catégorie |
|---|:--:|---------|------------------------------|------------------------|---------|-----------|
| 1 | ✅ | tomate (semis) | tiges fines et molles | manque de lumière | février | physiologique |
| 2 | — | poireau (semis) | tombés au ras de la terre | fonte des semis | mars | maladie |
| 3 | ✅ | chou | truc gris poudreux | non résolu | janvier | non résolu |
| 4 | ✅ | carotte | mal levé, trous dans le rang | non résolu | mars | levée |
| 5 | — | radis | petits trous ronds | altises | avril | ravageur |
| 6 | — | fève | bestioles noires en grappe | pucerons noirs | avril | ravageur |
| 7 | — | salade | mangée la nuit | limaces | mai | ravageur |
| 8 | ✅ | haricot | graines molles, pas de levée | sol froid et humide | mai | levée |
| 9 | — | pomme de terre | bêtes rayées, larves rouges | doryphores | mai | ravageur |
| 10 | — | fraisier | stolons ++, fruits -- | excès d'azote | mai | fertilisation |
| 11 | — | rhubarbe | bords grignotés | limaces / otiorhynques | mai | ravageur |
| 12 | — | épinard | montaison précoce | semis tardif | mai | physiologique |
| 13 | — | asperge | bêtes noires et oranges | criocères | juin | ravageur |
| 14 | — | artichaut | cœur plein de pucerons | pucerons | juin | ravageur |
| 15 | — | salade | montaison, tige centrale | chaleur | juin | physiologique |
| 16 | — | pomme de terre | taches brunes, tiges noires | mildiou | juin | maladie |
| 17 | — | petit pois | blanc en fin de saison | oïdium | juin | maladie |
| 18 | — | radis | creux et piquant | arrosage irrégulier | juin | arrosage |
| 19 | ✅ | tomate | taches marron ascendantes | mildiou | juillet | maladie |
| 20 | ✅ | courgette | poudre blanche | oïdium | juillet | maladie |
| 21 | ✅ | courgette | fruits avortés au bout | pollinisation | juillet | physiologique |
| 22 | ✅ | tomate | feuilles enroulées | non résolu | juillet | non résolu |
| 23 | ✅ | blette | galeries claires | mineuses | juillet | ravageur |
| 24 | ✅ | poivron | chute des fleurs | excès de chaleur | juillet | physiologique |
| 25 | — | aubergine | toiles, feuilles piquetées | araignées rouges | août | ravageur |
| 26 | ✅ | tomate | cul noir | carence calcium | août | physiologique |
| 27 | ✅ | concombre | amertume | arrosage irrégulier | août | arrosage |
| 28 | ✅ | chou | nervures seules | piéride | août | ravageur |
| 29 | — | betterave | taches rondes | cercosporose (incertain) | août | maladie |
| 30 | — | oignon | pourriture au collet | séchage / conservation | août | conservation |
| 31 | — | melon | sans goût | excès d'eau avant récolte | août | arrosage |
| 32 | — | framboise | vers blancs | ver du framboisier | juillet | ravageur |
| 33 | ✅ | carotte | racines fourchues | excès de fumure | septembre | fertilisation |
| 34 | — | potiron | pourriture face sol | humidité au sol | septembre | conduite |
| 35 | ✅ | chou | flétrissement, racines boursouflées | hernie du chou | septembre | maladie |
| 36 | — | céleri | taches brunes ponctuées | septoriose | septembre | maladie |
| 37 | — | navet | galeries sous la peau | mouche du chou | octobre | ravageur |
| 38 | — | poireau | pointes jaunes, traits orange | rouille | octobre | maladie |
| 39 | — | poireau | galeries dans le fût | mouche du poireau | novembre | ravageur |
| 40 | — | mâche | plants qui fondent | densité + humidité | novembre | maladie |
| 41 | ✅ | cornichon | amers, jaunissent sur pied | récolte trop espacée | juillet | conduite |
| 42 | ✅ | cornichon | feuilles marbrées, pousses rabougries | virose transmise par pucerons | août | maladie |
| 43 | ✅ | ail | caïeux pourris sans lever | excès d'eau, sol lourd | décembre | levée |
| 44 | ✅ | ail | traits orange poudreux | rouille | mai | maladie |

**Couverture réelle (recomptée le 25/08/2026) :** 44 entrées · **30 cultures** ·
**12 mois** (janvier → décembre, aucun mois vide) · **9 catégories** (physiologique, maladie,
ravageur, levée, arrosage, fertilisation, conservation, conduite, non résolu) ·
**3 cas non résolus** (#3, #4, #22 — bruit réaliste assumé) ·
**19 entrées dans le périmètre v1**, couvrant **les 10 cultures prioritaires sans exception**.

> ⚠️ Les entrées #38 (rouille du poireau) et #44 (rouille de l'ail) sont volontairement proches :
> elles testent la capacité de la recherche à **désambiguïser deux fiches sur un même symptôme**,
> l'une dans le périmètre v1 et l'autre non.

---

## Partie 3 — Patterns linguistiques appliqués

Ce sont les régularités à exploiter côté classification et cache sémantique.

### 3.1 Le symptôme précède toujours la culture… ou l'inverse, jamais le diagnostic

Le potagiste amateur **ne nomme jamais la maladie en premier**. Il décrit ce qu'il voit.
Conséquence directe : une recherche par nom de pathogène (`oïdium`, `mildiou`) rate la majorité des
requêtes entrantes. L'index doit porter sur le **couple (culture, symptôme visuel)**.

> 🔶 **Nuance mesurée.** L'extraction [3] de la vague 0 montre que le vocabulaire réellement présent
> dans `texte_original` est déjà **technique** (« mildiou », « oïdium », « pucerons »), pas
> populaire. Ce corpus est donc **anticipatoire** : il décrit l'usage attendu quand la base
> d'utilisateurs s'élargira, pas l'usage observé aujourd'hui. C'est assumé et documenté.

### 3.2 Lexique du symptôme — vocabulaire non technique

| Registre amateur | Terme agronomique |
|------------------|-------------------|
| poudre blanche / du blanc / couvert de blanc | oïdium |
| le cul noir | nécrose apicale |
| des taches marron qui remontent | mildiou |
| monte en graine / fait une tige au milieu | montaison |
| des petites bêtes / des bestioles / des bêtes | ravageur non identifié |
| ça fond / ça flétrit / ça tombe d'un coup | fonte, flétrissement |
| creux et piquant | radis à maturité dépassée |
| fourchue / fait deux jambes | racine bifide |
| des galeries / des trous / véreux | larve mineuse |
| des toiles | acariens |
| des traits orange qui partent en poussière | rouille (pustules) |
| feuilles marbrées / marbrure jaune et vert | mosaïque virale |

### 3.3 Marqueurs d'incertitude — signal fort d'intention `INTERROGER`

`je pense` · `je crois` · `je suppose` · `paraît-il` · `d'après le voisin` · `d'après internet` ·
`d'après le forum` · `on m'a dit` · `jamais su` · `jamais été sûr` · `peut-être` · `sûrement` ·
`ça a passé tout seul`

Ces marqueurs sont quasi absents des phrases de **saisie d'action** (`ACTION`). Un simple test de
présence est un discriminant à coût nul, en amont de tout appel LLM — candidat direct pour l'étage 1
de la cascade d'US-092.

> 🔗 **À maintenir aligné** avec la regex de `[SOURCE 4]` de `tools/analyse_corpus_echecs.sql`, qui
> teste ce même discriminant sur les données réelles. Toute liste modifiée ici doit l'être là.

### 3.4 La période est toujours relative ou approximative

`fin juillet` · `après les orages` · `courant juin` · `à l'arrachage` · `après la semaine humide` ·
`récolte de novembre` · `plantation de décembre`

Jamais de date ISO. Le parsing doit accepter les ancrages **phénologiques** (« à l'arrachage »,
« après la récolte ») et **météorologiques** (« après les pluies »), pas seulement calendaires.
Point d'attention pour `parse_date()`.

> 🔴 **Confirmé par la production (25/08/2026).** Ce n'est plus un point d'attention théorique : la
> **date est le premier poste de correction de toute l'application** (27,5 % des corrections),
> parce qu'une phrase sans ancrage temporel retombe silencieusement sur *aujourd'hui* — soit la date
> de saisie, jamais celle du geste. Détail au §8.1 de
> `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md`.

### 3.4 bis — À la dictée, le point d'interrogation n'existe pas

La production porte une question enregistrée comme un événement : **« Y a t il des radis dans mon
jardin »**. Ni `?`, ni « pourquoi », ni « combien ». Toute détection d'intention `INTERROGER` qui
s'appuie sur la ponctuation est **structurellement aveugle sur le canal vocal**, qui est le canal
principal de l'application.

Ce sont les **tournures** qu'il faut reconnaître : `y a-t-il` · `est-ce que` · `dis-moi` ·
`montre-moi` · `c'est quoi` · `qu'est-ce que` · `as-tu` · `peux-tu` · `sais-tu`.

⚠️ Les entrées de ce corpus sont volontairement rédigées **sans point d'interrogation**, au style
dicté. C'est la forme réelle des questions entrantes, pas une négligence de rédaction.

### 3.5 Structure syntaxique dominante

```
[possessif] + [culture] + [verbe d'état/perception] + [symptôme]
   mes        carottes      sont                      fourchues
   les feuilles de mes courgettes  ont                de la poudre blanche
   il y a     des trous     dans le rang
```

Trois moules couvrent ~90 % du corpus :
- `mes X ont/sont Y`
- `les feuilles de mes X ...`
- `il y a Z sur/dans mes X`

Utile pour l'extraction d'entité `culture` par règle avant tout recours au LLM.

---

## Partie 4 — Exploitation

| Étage cascade | Usage de ce corpus |
|---------------|--------------------|
| Cache sémantique (US-122a) | 44 embeddings de référence, seuil de similarité à calibrer sur les reformulations |
| SQL agent | non concerné (questions non factuelles sur les données du potager) |
| RAG fiches culture (US-140) | jeu de test de rappel — **sur les 19 entrées du périmètre v1 uniquement** |
| Cascade, test d'honnêteté | les 25 entrées hors périmètre doivent obtenir « je n'ai pas de fiche sur cette culture », jamais une fiche voisine forcée |
| LLM fallback | les 3 cas non résolus (#3, #4, #22) doivent y tomber — vérifie que la cascade ne force pas une réponse |

🧪 **À mesurer :** taux de hit du cache sur des reformulations des entrées (ex. « poudre blanche
courgettes » vs entrée #20). Cible : > 70 % sans appel LLM.

🔶 **Limite assumée :** corpus synthétique. Il reproduit le registre observable du jardinage amateur
francophone mais n'a pas valeur d'échantillon statistique. Validation empirique possible : faire
relire les entrées par deux ou trois jardiniers amateurs — question unique : « est-ce que tu
poserais la question comme ça ? ».
