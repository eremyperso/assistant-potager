**ID :** US-351
**Titre :** Brancher sur le registre trois lectures que l'application sait déjà : associations, bon moment pour semer, potager et abris
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon, ou mon assistant IA, lise les associations d'une culture, ce qui se sème ce mois-ci et ce que contient mon potager (serre, pépinière chaude, ville) avant de me répondre
Afin qu'il me dise la même chose que les écrans de la PWA, sans inventer ni me redemander ce que mon potager dit déjà

**Contexte fonctionnel :**
Lot 1, à côté d'US-339. Issue des références humaines du 18/11/2026 (`docs/EPIC 20 - COMPAGNON CLIENT DES CAPACITES/REFERENCE_HUMAINE_B01.md`) : sur neuf scénarios joués par le jardinier, la première cause d'échec est que **les données de l'application ne sont pas lues**. Trois d'entre elles existent déjà, servent un écran de la PWA, et n'ont aucun chemin vers le compagnon :

| Lecture | Scénario | Ce qui s'est passé | Service qui sert l'écran |
|---|---|---|---|
| associations d'une culture | B22 | « poivron à éviter » (il est favorable), chou « moins souvent cité », pomme de terre et aubergine citées sans être dans la fiche, source fausse | fiche culture de la zone (`GET /cultures/{culture}/fiche`, `fiche_culture.py`, table `association_culture`, US-163) |
| le bon moment pour semer, du mois | B06 | mâche, épinard et betterave proposées « pour les prochaines semaines » ; la rubrique de la vue Pépinière est vide en novembre en zone océanique | onglet Parcours de la vue Pépinière (`echeances_lots._parcours` : `a_semer`, `calendrier_semis`, US-218) |
| le potager : abris déclarés, ville, zone | B01, B04, B05, B09, B19 | « as-tu une serre chauffée ? » sans lire le plan ; « pépinière chaude » prise pour une parcelle à créer ; « Lyon » cité pour un potager sans ville ; réglage de la ville inconnu | plan et propriétés du potager (`voir_plan`, `parcelles.est_pepiniere`, `type_pepiniere`, `abri`, `potagers.ville`) |

Le jardinier règle la ville dans la PWA par « Modifier le potager », champ « Ville » (carte météo « Localisation manquante », ou « Localiser » sur la fiche calendrier). Le guide et le corpus `doc_app` n'en disent rien : le compagnon a répondu par « nomme la ville dans ta phrase ».

**Réponses attendues (exemples) :**
- associations de la tomate : `{"culture": "tomate", "zone": "oceanique", "favorables": ["basilic", "ciboulette", "laitue", "persil", "ail", "carotte", "poivron"], "familles_favorables": ["Lamiacées"], "a_eviter": ["chou", "concombre", "fenouil"], "familles_a_eviter": ["Brassicacées"], "source": "fiche culture"}`
- semis du mois : `{"mois": "novembre", "zone": "oceanique", "a_semer": [], "prochaine_ouverture": {"mois": "janvier", "cultures": […]}}`
- potager : `{"ville": null, "zone": "oceanique", "abris": [], "pepinieres": [], "parcelles": ["planche légumes"], "reglage_ville": "Modifier le potager › Ville"}`

**Critères d'acceptance :**
- [ ] CA1 : Une capacité de lecture rend les associations d'une culture **pour la zone du potager**, en deux listes (favorables, à éviter), cultures et familles séparées, avec leur origine. Une culture sans association connue le dit, sans liste inventée. Les listes sont celles de la fiche culture de la PWA (test d'égalité sur un même potager)
- [ ] CA2 : Une capacité de lecture rend ce qui se sème ce mois-ci pour la zone du potager, **par le même calcul que l'onglet Parcours de la vue Pépinière** ; un mois vide le dit (« aucun semis ce mois-ci ») et donne la prochaine ouverture. Test d'égalité avec la rubrique « Le bon moment pour semer » pour un même potager et une même date ; la date est un paramètre (test miroir novembre / mai)
- [ ] CA3 : La lecture du potager rend ses abris déclarés (serre, tunnel, pépinière chaude ou froide, d'après `est_pepiniere`, `type_pepiniere`, `abri`), sa zone et sa ville. Une ville absente est rendue comme absente, avec le chemin du réglage dans la PWA ; aucune ville n'est jamais donnée en exemple dans une description de capacité
- [ ] CA4 : Les trois lectures sont dans le registre d'US-338, visibles du compagnon et du MCP (test de parité), en lecture seule, chacune sous le contexte locataire du potager
- [ ] CA5 : Le guide utilisateur (les deux copies), la fiche `doc_app` et l'aide disent comment régler la ville du potager (« Modifier le potager › Ville ») ; le corpus est réingéré et une question de mesure le vérifie
- [ ] CA6 : Mesuré sur le jeu d'évaluation, avec accord sur le volume : B22 cite les deux listes sans culture absente de la fiche ; B06 dit « aucun semis » en novembre ; B01 et B04 lisent le plan avant de parler de serre (critère « données lues » du jeu)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-338 (registre) ; US-163 (associations), US-218 (bande du bon moment pour semer), US-074 (localisation du potager) ; US-337 pour la mesure
- Hors périmètre : copier ou créer une fiche culture pour une zone (B20), à traiter hors de l'épic 20
- Modèle / effort conseillé : **Sonnet 5.5, `low`** — trois lectures qui réutilisent des services d'écran ; ni Opus ni Fable ne sont requis

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le potager est en zone océanique, sans ville, avec une seule parcelle « planche légumes »
And nous sommes en novembre
When le jardinier demande "je dispose d'une serre chauffée, est-ce que je peux planter des tomates ?"
Then le compagnon lit le potager
And il répond qu'aucune serre chauffée n'est déclarée et propose de la déclarer
And il ne demande pas au jardinier s'il a une serre

Given la fiche culture de la tomate pour la zone océanique
When le jardinier demande "quelles cultures éviter à côté de mes tomates ?"
Then le compagnon cite chou, concombre, fenouil et la famille des Brassicacées à éviter
And il cite les favorables, dont le poivron
And il ne cite ni la pomme de terre ni l'aubergine
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `mcp`, `associations`, `pepiniere`
