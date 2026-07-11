**ID :** US-039
**Titre :** Affichage des observations sur le dashboard frontend

**Story :**
En tant que jardinier
Je veux consulter les notes/observations que j'ai dictées au bot (US-038) directement dans le dashboard web, au bon endroit selon qu'elles concernent une parcelle précise ou une culture en général
Afin de retrouver l'historique qualitatif de mon potager (maladies, arrosage, paillage, remarques) sans devoir rouvrir Telegram

**Contexte fonctionnel :**
La US-038 enregistre les notes comme des `Evenement` avec `type_action = "observation"` et une catégorie préfixée dans `commentaire` (ex : `[Maladie / ravageur] mildiou sur les feuilles du bas`). Aucune de ces observations n'est aujourd'hui visible dans le dashboard React (`frontend/`).

Une maquette Claude Design existe (projet *potager 2026*, fichier `Potager 2026 - Redesign.html`) avec des données fictives commentées `/* OBSERVATIONS (US-038) : données fictives */` (composants `ObsGlyph`, `ObsInlineBlock`, `ObservationSheet`) — mais cette maquette utilise un système visuel indépendant, non branché sur le vrai frontend. Le vrai code (`frontend/src/views/Plan.jsx`, `frontend/src/views/Stocks.jsx`) a son propre système de design (classes Tailwind + variables CSS `--g-*`, icônes `lucide-react`) qu'il faut respecter — la maquette sert de **référence d'interaction** (icône + accordéon dépliable), pas de gabarit visuel à copier tel quel.

**Règle de routage des observations (décidée avec le PO — révision exclusive) :**

Chaque observation est acheminée vers **un seul** point d'accès, jamais deux à la fois (y compris à l'intérieur de Plan : parcelle OU ligne culture, jamais les deux) :

1. **`culture` ET `variete` renseignées** → toujours acheminée vers une **ligne de culture précise** dans Plan (jamais l'icône parcelle) :
   - Si `parcelle_id` est déjà renseigné sur l'observation → directement cette parcelle
   - Si `parcelle_id` est absent → résolution automatique de la parcelle actuelle de cette culture+variété via le calcul d'occupation existant (`utils.parcelles.calcul_occupation_parcelles`, déjà utilisé par `/plan`) :
     - plantée dans **une seule** parcelle actuellement → traitée comme si elle appartenait à cette parcelle
     - plantée dans **plusieurs** parcelles, ou dans **aucune** (culture pas encore en terre) → repli sur le cas 2 (Stocks)

2. **`culture` renseignée SANS `variete`** (que `parcelle_id` soit renseigné ou non) → toujours **Stocks**, sur la ligne culture agrégée (`CultureRow` de la section "Au potager") — pas assez précis pour cibler une ligne dans Plan, même si une parcelle est connue

3. **Aucune `culture`, mais `parcelle_id` renseigné** → icône sur la carte de la parcelle (`ParcellCard`, header) — regroupe uniquement les notes qui ne sont associées à aucune culture

4. **Ni `parcelle_id` ni `culture` renseignés** (note libre générale) → **hors périmètre de cette US** : reste consultable via l'onglet Historique existant, sans nouvelle icône dédiée. À retravailler dans une US ultérieure si besoin.

**Ce qui est repris de la maquette (interaction, pas le visuel) :**
- Icône cliquable, visible seulement s'il existe au moins une observation pour l'élément concerné
- Clic → déplie un bloc accordéon inline juste sous la ligne concernée : liste `date + texte`, triée du plus récent au plus ancien, paginée par petits groupes si nécessaire
- Le texte affiché est nettoyé du préfixe `[Catégorie]` présent dans `commentaire` (la maquette n'affiche que le texte brut, pas de badge de catégorie séparé)
- Message `"Aucune observation enregistrée."` si la liste est vide

**Critères d'acceptance :**
- [ ] CA1 : `GET /plan` inclut, pour chaque parcelle, un indicateur `has_observations: bool` reflétant uniquement les notes SANS culture rattachées à cette parcelle (cas 3), et pour chaque culture au sein d'une parcelle, un indicateur reflétant les notes culture+variété qui lui sont résolues (cas 1)
- [ ] CA2 : `GET /stats` (`stock_par_culture` dans Stocks) inclut, pour chaque culture agrégée, un indicateur `has_observations: bool` reflétant les notes culture-sans-variété (cas 2) et les notes culture+variété non résolues à une parcelle unique
- [ ] CA3 : Un nouvel endpoint `GET /observations` expose la liste `{date, texte}` (texte nettoyé du préfixe catégorie) triée du plus récent au plus ancien, filtrable par `parcelle_id` seul, par `culture` seule, ou par `parcelle_id`+`culture`+`variete`
- [ ] CA4 : La résolution du cas 1 (culture+variété sans parcelle_id) réutilise `calcul_occupation_parcelles` — pas de nouvelle logique de calcul d'occupation dupliquée
- [ ] CA5 : Sur Plan, l'icône observation apparaît SOIT sur `ParcellCard` (notes sans culture) SOIT sur une ligne de culture précise (notes culture+variété résolues) — jamais les deux pour une même note
- [ ] CA6 : Sur Stocks, l'icône observation apparaît sur `CultureRow` si la culture a des observations agrégées (culture seule, ou culture+variété non résolue à une parcelle unique)
- [ ] CA7 : Un clic sur l'icône charge (lazy, au premier clic) puis affiche/masque un bloc accordéon inline avec la liste des observations, paginée par blocs de 3 (précédent/suivant), symbole œil (repris de la maquette Claude Design)
- [ ] CA8 : Le texte affiché ne contient jamais le préfixe `[Catégorie]` brut du champ `commentaire`
- [ ] CA9 : Message `"Aucune observation enregistrée."` si la liste est vide après chargement
- [ ] CA10 : Le rendu visuel (couleurs, typographie, espacements, icônes) reprend exactement le système déjà en place (classes Tailwind, variables CSS `--g-*`, icônes `lucide-react`) — pas de nouvelle palette ni de composant stylé "à la Claude Design"
- [ ] CA11 : Une même observation n'apparaît jamais à deux endroits à la fois (Plan/Stocks mutuellement exclusifs, et au sein de Plan, parcelle/ligne culture mutuellement exclusifs)
- [ ] CA12 : Aucune régression sur les fonctionnalités existantes de Plan et Stocks (occupation, stock, filtres, pépinière)
- [ ] CA13 : Un seul panneau d'observations reste ouvert à la fois par écran — en ouvrir un nouveau referme automatiquement le précédent
- [ ] CA14 : La zone de clic de l'icône observation est suffisamment large pour un usage tactile confortable sur smartphone

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : backend (`main.py` — extension `/plan`, `/stats`, nouvel endpoint `/observations`) + frontend (`frontend/src/views/Plan.jsx`, `frontend/src/views/Stocks.jsx`, nouveau composant partagé d'icône + accordéon, `frontend/src/lib/api.js`)
- Migration BDD requise : **non** — lecture seule sur `evenements` existants (US-038)
- Dépendances : US-038 (production des notes), US-024 (écran Plan existant), logique d'occupation existante (`utils/parcelles.py::calcul_occupation_parcelles`)
- Point d'attention backend : `GET /plan` (main.py:551) ne retourne actuellement pas l'`id` de la parcelle, seulement `nom` — à corriger ou contourner (clé par `nom` normalisé) pour cibler une parcelle sans ambiguïté depuis le frontend
- Extraction du préfixe catégorie : regex `^\[([^\]]+)\]\s*` sur `commentaire`, calculée uniquement côté backend (jamais dupliquée côté frontend)
- Le cas 3 (résolution automatique de la parcelle pour une culture+variété sans `parcelle_id`) est le point le plus complexe de cette US — il dépend de l'état d'occupation *au moment de la consultation*, qui peut différer de l'état au moment où la note a été dictée. Documenter ce comportement pour l'utilisateur (ex : une note peut "changer d'écran" si la culture est déplacée/récoltée entre-temps)
- Note explicitement hors périmètre (cas 4) : notes sans parcelle ni culture → restent uniquement dans Historique, sujet à traiter dans une US ultérieure
- Référence design (interaction uniquement, pas le visuel) : projet Claude Design *potager 2026*, fichier `Potager 2026 - Redesign.html` (composants `ObsProvider`, `useObs`, `ObsGlyph`, `ObsInlineBlock`)

**Estimation :** 8 points *(revu à la hausse vs. le brouillon initial — la résolution du cas 3 ajoute une complexité backend réelle)*

**Scénario Gherkin :**
```gherkin
Scénario: Observation avec parcelle + culture + variété → ligne culture UNIQUEMENT (pas l'icône parcelle)
  Given une observation a parcelle_id="Nord" et culture="tomate", variete="Roma"
  When j'ouvre l'écran Plan
  Then l'icône observation est visible sur la ligne "tomate Roma" à l'intérieur de la carte "Nord"
  And aucune icône observation n'apparaît sur le header de la carte "Nord" pour cette note
  When j'ouvre l'écran Stocks
  Then aucune icône observation n'apparaît sur la ligne "tomate" (déjà couverte par Plan)

Scénario: Observation avec parcelle + culture SANS variété → Stocks, pas d'icône parcelle
  Given une observation a parcelle_id="Centre" et culture="courgette", variete=null
  When j'ouvre l'écran Stocks
  Then l'icône observation est visible sur la ligne "courgette"
  When j'ouvre l'écran Plan
  Then aucune icône observation liée à cette note n'apparaît sur la carte "Centre"

Scénario: Observation liée à une culture sans parcelle → visible uniquement sur Stocks
  Given une observation a culture="courgette", variete=null, parcelle_id=null
  When j'ouvre l'écran Stocks
  Then l'icône observation est visible sur la ligne "courgette"
  When j'ouvre l'écran Plan
  Then aucune icône observation liée à cette note n'apparaît

Scénario: Culture+variété sans parcelle, résolue à une parcelle unique
  Given une observation a culture="tomate", variete="cerise", parcelle_id=null
  And "tomate cerise" est actuellement planté uniquement dans la parcelle "Potager centre"
  When j'ouvre l'écran Plan
  Then l'icône observation apparaît sur la ligne "tomate cerise" de la carte "Potager centre"
  When j'ouvre l'écran Stocks
  Then aucune icône observation liée à cette note n'apparaît sur la ligne "tomate"

Scénario: Culture+variété sans parcelle, plantée à plusieurs endroits → repli sur Stocks
  Given une observation a culture="tomate", variete="cerise", parcelle_id=null
  And "tomate cerise" est actuellement planté dans 2 parcelles différentes
  When j'ouvre l'écran Stocks
  Then l'icône observation apparaît sur la ligne agrégée "tomate"
  When j'ouvre l'écran Plan
  Then aucune icône observation liée à cette note n'apparaît sur les cartes concernées

Scénario: Consultation du détail d'une observation
  Given la parcelle "Nord" a 2 observations : "[Arrosage (remarque)] Sol sec" (10/06) et "[Paillage] Paillage renouvelé" (02/06)
  When je clique sur l'icône observation de la parcelle "Nord"
  Then un bloc accordéon s'affiche avec 2 lignes triées du plus récent au plus ancien
  And la première ligne affiche la date "10/06" et le texte "Sol sec" (sans le préfixe "[Arrosage (remarque)]")
```

**Labels GitHub :** `us`, `sprint-X`, `frontend`, `backend`, `observation`, `plan`, `stocks`
