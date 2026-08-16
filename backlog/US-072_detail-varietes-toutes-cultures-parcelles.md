**ID :** US-072
**Titre :** Exposer un détail par variété, toutes cultures et tous états confondus, avec leurs parcelles d'origine

**Story :**
En tant que jardinier utilisant l'interface web
Je veux que le suivi de mes cultures soit calculé à la granularité culture + variété, avec la liste réelle des parcelles où chacune se trouve
Afin que l'écran Stocks puisse afficher chaque variété séparément (et non un total qui mélange mes deux variétés de tomates) avec ses parcelles réelles plutôt qu'un lieu unique ou absent

**Contexte fonctionnel :**
Première US du chantier de refonte de l'écran Stocks en écran transverse unique (voir `docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md` et la maquette figée `ScreenStocks`, `Maquette figée/web-screens.jsx` du projet Claude Design "potager 2026", gel du 15/08/2026 — fichier faisant foi `Potager - Application Web - FIGE 2026-08-15.html`). Elle prépare la donnée pour **US-073** (écran), sur le modèle déjà appliqué par US-065 pour la Pépinière (une US de données en amont d'une US d'écran).

Aujourd'hui, trois sources distinctes alimentent l'écran Stocks, à des granularités différentes :
- `GET /stats` → `stock_par_culture` : agrégé **par culture uniquement** (`utils/stock.py::calcul_stock_cultures`), deux variétés d'une même culture (ex. Tomate Cœur de bœuf et Tomate Cerise) sont fondues dans un seul total. Aucune liste de parcelles.
- `GET /stats` → `semis_pleine_terre` : idem, agrégé par culture, mais porte déjà une liste de parcelles (`parcelles_pleine_terre`).
- `GET /godets` → `en_attente` : déjà agrégé **par variété** (`utils/stock.py::calcul_godets_par_culture`), pas de parcelle (un lot en godet n'est pas encore planté).

Une fonction de détail par variété existe déjà — `utils/stock.py::calcul_stock_par_variete` (portée par `US_Stats_detail_par_variete` et `US-036`/`US-037`) — mais elle calcule **une seule culture à la fois** (utilisée aujourd'hui uniquement par `bot.py`, jamais exposée en HTTP) et ne collecte pas les parcelles. Cette US généralise cette fonction à l'ensemble des cultures d'un potager en un seul appel, et lui ajoute la liste des parcelles.

**Écart de domaine identifié entre la maquette et le modèle métier actuel — décision retenue.** Les données fictives de la maquette (`WSUIVI`, `web-tokens.jsx`) portent un champ « vendu » pour toutes les lignes, y compris celles à l'état « au potager » (ex. `Tomate Cœur de bœuf … ven:9`). Or dans le modèle métier actuel, la vente n'existe que comme sortie de stock **en pépinière**, avant plantation (US-032, « vente de godet ») : aucun événement ne permet de vendre un pied déjà planté en pleine terre. Plutôt que d'inventer une donnée, cette US **n'expose « vendu » que pour les entrées à l'état pépinière** (reprise de `nb_vendus` déjà calculé) ; les entrées « au potager » et « semis pleine terre » ne portent pas ce champ — cf. CA6.

**Critères d'acceptance :**

*Nouvelle agrégation*
- [ ] CA1 : Un nouvel endpoint (ex. `GET /stats/varietes`, avec le même paramètre `date_ref` optionnel que `/stats` et `/godets`) retourne une entrée par couple (culture, variété) normalisé **réellement présent** dans au moins un des trois états — aucune entrée pour une culture/variété jamais enregistrée
- [ ] CA2 : Chaque entrée porte un état parmi `potager` / `semis` / `pep`, déterminé par les **mêmes règles déjà en vigueur** pour distinguer `stock_par_culture`, `semis_pleine_terre` et `en_attente` aujourd'hui — aucune nouvelle règle métier, seul le regroupement change
- [ ] CA3 : Chaque entrée porte une origine (`pépinière` / `pied_acheté` / `semis_pleine_terre` / `non_localisé`), reprise du calcul déjà en place dans `/stats` (`entry["origine"]`), appliquée à la granularité variété
- [ ] CA4 : Chaque entrée porte la liste des parcelles où la variété est effectivement présente, déduite des événements réels de plantation/semis — jamais un lieu unique, jamais une parcelle par défaut. Pour l'état `pep` (non encore planté), cette liste est vide : le lieu « pépinière » est déjà porté par l'état, pas par ce champ
- [ ] CA5 : Chaque entrée porte les champs numériques suivants, tous repris tels quels des calculs existants (`calcul_stock_par_variete` pour `potager`/`semis`, `calcul_godets_par_culture` pour `pep`), sans nouvelle règle de calcul : total entré avec son unité réelle, stock actuellement en place/disponible, pieds ou godets perdus, poids récolté cumulé avec son unité, nombre de récoltes pesées
- [ ] CA6 : Le champ « vendu » n'est renseigné (repris de `nb_vendus`) que pour les entrées à l'état `pep`. Pour les états `potager` et `semis`, ce champ est **absent** (`null`), jamais `0` par défaut — un `0` affirmerait à tort qu'une vente a été recherchée et n'a rien donné, alors qu'aucune vente n'est même possible à ce stade du cycle de vie
- [ ] CA7 : Le filet anti-double-comptage déjà en place (une culture affichée dans `stock_par_culture` n'est jamais réaffichée dans `semis_pleine_terre`) est repris à la granularité variété
- [ ] CA8 : Le contrat des endpoints existants (`GET /stats`, `GET /godets`) ne change pas — Statistiques, Pépinière et le bot Telegram restent inchangés, comme la contrainte déjà posée par US-065 pour `GET /godets`
- [ ] CA9 : Aucune migration BDD — toutes les données sources existent déjà sous forme d'événements ; il s'agit d'une nouvelle agrégation lisant les mêmes tables via les mêmes fonctions de calcul, généralisées à toutes les cultures

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-030/031 (paramètre `date_ref`), US-014/US-036/US-037 (`calcul_stock_par_variete` existant, à généraliser), US-065 (`calcul_godets_par_culture` existant, réutilisé tel quel)
- US-073 (écran Stocks) consomme cette US

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Deux variétés d'une même culture sur des parcelles différentes
  Given des tomates Cœur de bœuf plantées dans la parcelle "Maison" et des tomates Cerise plantées dans la parcelle "Serre"
  When l'endpoint de détail par variété est appelé
  Then deux entrées distinctes sont retournées, une par variété
  And chacune liste uniquement sa propre parcelle

Scénario: Une variété plantée dans plusieurs parcelles
  Given des tomates Cœur de bœuf plantées dans les parcelles "Maison" et "Serre"
  When l'endpoint est appelé
  Then une seule entrée "Tomate / Cœur de bœuf" est retournée
  And elle liste les deux parcelles "Maison" et "Serre"

Scénario: Variété uniquement en pépinière
  Given un lot de butternut en godet, non encore planté, avec 2 plants vendus
  When l'endpoint est appelé
  Then l'entrée a l'état "pep", un champ "vendu" à 2, et un récolté à 0

Scénario: Vente absente pour une culture en place
  Given des tomates Cœur de bœuf plantées en pleine terre, sans aucun événement de vente
  When l'endpoint est appelé
  Then l'entrée a l'état "potager"
  And son champ "vendu" est absent, jamais 0

Scénario: Absence de double comptage
  Given une culture de haricots présente à la fois dans les plantations et dans un semis pleine terre renvoyé par le calcul actuel
  When l'endpoint est appelé
  Then cette variété n'apparaît qu'une seule fois, à l'état "potager"
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `backend`, `stocks`
