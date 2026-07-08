**ID :** US-037  
**Titre :** Enregistrer un semis en pleine terre avec type de culture et unité adaptée

**Story :**  
En tant que jardinier  
Je veux déclarer un semis en pleine terre en précisant l'unité qui me parle (nombre de graines, nombre de pieds, surface en m²) et que le système sache si ma culture est végétative ou reproductive  
Afin que le suivi de stock et de rendement soit cohérent avec le comportement réel de la plante sur toute la saison

**Critères d'acceptance :**
- [ ] CA1 : Lors d'un semis, l'utilisateur peut préciser la quantité dans l'une des unités suivantes : `graines`, `pieds`, `m²` (ex : "semé 2 m² de haricots à la volée", "semé 50 graines de carottes", "semé 30 pieds de radis")
- [ ] CA2 : Si l'unité est une surface (`m²`), la valeur est stockée telle quelle — le système **n'effectue aucune conversion** vers un nombre de pieds ou de graines
- [ ] CA3 : Le `type_organe_recolte` de la culture (végétatif ou reproducteur) est résolu automatiquement via `CultureConfig` au moment de l'enregistrement du semis
- [ ] CA4 : Pour une culture **végétative** (carotte, radis, laitue…), le stock de la culture augmente du nombre/surface semé ; la première récolte terminale décrémente ce stock
- [ ] CA5 : Pour une culture **reproductive semée en pleine terre** (haricot, petit pois, fève…), le stock de "pieds actifs" augmente du nombre/surface semé ; chaque récolte est un événement indépendant qui **ne décrémente pas** le stock de pieds — seule une `perte` ou une fin de saison explicite le fait
- [ ] CA6 : La commande vocale/texte est comprise sans que l'utilisateur ait à nommer le type de culture ("à la volée" implique surface m², "X graines" implique unité `graines`, "X pieds" implique unité `pieds`)
- [ ] CA7 : Si la culture n'est pas présente dans `CultureConfig`, le système demande à l'utilisateur si c'est une culture végétative ou reproductive avant d'enregistrer
- [ ] CA8 : L'événement enregistré porte les champs : `type_action=semis`, `culture`, `variete` (optionnel), `quantite`, `unite` (`graines` | `pieds` | `m²`), `date`, `parcelle_id`
- [ ] CA9 : La commande `/stats` et le dashboard frontend affichent correctement la quantité avec son unité d'origine (ex : "Haricots — 2 m² semés, 3 récoltes, 1,4 kg cumulés")
- [ ] CA10 : Le calcul de surface occupée d'une parcelle (`/plan`, `occupation_pct`) traite un semis en `unite="m²"` comme une surface directement occupée — il ne le multiplie **jamais** par une empreinte au pied (`CultureConfig.surface_m2`). Pour `graines`/`pieds`, le comportement actuel (nb × empreinte au pied) est conservé.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot Telegram + parsing Groq) · analyse (stats) · consultation (dashboard) · occupation des parcelles (`/plan`)
- La surface (`m²`) est une unité de semis valide à part entière, pas un proxy de quantité : elle ne doit pas entrer dans les calculs de rendement par pied
- La distinction végétatif / reproducteur est déjà modélisée dans `CultureConfig.type_organe_recolte` — l'US exploite l'existant, elle ne recrée pas cette logique
- Pour les cultures reproductives semées en pleine terre, le modèle de suivi est : **stock de pieds actifs** (issu du semis) + **rendement cumulé saison** (somme des récoltes) — deux métriques indépendantes
- **Bug identifié à corriger (CA10)** : `calcul_occupation_parcelles()` (`utils/parcelles.py:456-498`, section "Semis pleine terre") alimente déjà `nb_plants` depuis les semis liés à une `parcelle_id`, mais **sans regarder l'unité** (`utils/parcelles.py:481` : `total = quantite or 0`). Côté `/plan` (`main.py:592-601`), ce `nb_plants` est ensuite multiplié sans condition par `surface_m2_par_plant` (empreinte au pied issue de `CultureConfig.surface_m2`) pour obtenir `occupation_pct`. Résultat actuel : un semis de "2 m²" de carottes est interprété comme "2 pieds" et donne une surface occupée de `2 × 0,03 = 0,06 m²` au lieu de `2 m²` — l'inverse de ce qu'exige CA2 (aucune conversion m² → pieds), mais appliqué au calcul d'occupation plutôt qu'au stock.
- **Preuve de reproduction (base dev locale, 2026-07-07)** — commande dictée : *"j'ai semé 2 m2 de haricot vert"* (haricot déjà connu `reproducteur` dans `CultureConfig`, cf. événement id=2075 dans la même base). Résultat observé en base (`evenements` id=274/275) :

  | champ | obtenu | attendu |
  |---|---|---|
  | `quantite` | `NULL` | `2` |
  | `unite` | `"graines"` (fallback LLM) | `"m²"` |
  | `type_organe_recolte` | `NULL` | `"reproducteur"` |

  Trois défaillances cumulées : (1) le parsing Groq perd purement la quantité quand l'unité "m2" n'est pas reconnue — CA1/CA6 ; (2) il retombe sur `"graines"` par défaut au lieu de refuser/demander — CA1/CA6 ; (3) **`type_organe_recolte` n'est pas résolu depuis `CultureConfig` sur le pipeline standard de sauvegarde d'un semis**, alors que la culture "haricot" y est déjà répertoriée — la résolution CA3 ne semble s'appliquer aujourd'hui que sur certains flux (ex. saisie ayant produit l'événement id=2075), pas systématiquement à chaque semis enregistré. À vérifier/corriger en priorité lors de l'implémentation de CA3.
- Dépendances : #US-036 (rendement en poids végétatif), #US-017 (déduction stock semis→godet)
- Migration BDD requise : non (les champs `quantite` et `unite` existent déjà sur `Evenement`)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
# Cas 1 — Semis à la volée (surface) pour culture reproductive
Given un jardinier dit "j'ai semé 2 m² de haricots verts dans la parcelle potager"
And "haricot" a type_organe_recolte = "reproducteur" dans CultureConfig
When le système enregistre l'événement
Then un semis est créé avec quantite=2, unite="m²", culture="haricot", type_action="semis"
And le stock de pieds actifs "haricot" augmente de 2 m² (unité conservée)
And aucune conversion vers un nombre de pieds n'est effectuée

# Cas 2 — Semis par graines pour culture végétative
Given un jardinier dit "semé 80 graines de carottes Nantaise dans le carré nord"
And "carotte" a type_organe_recolte = "végétatif" dans CultureConfig
When le système enregistre l'événement
Then un semis est créé avec quantite=80, unite="graines", culture="carotte", variete="Nantaise"
And le stock végétatif "carotte" augmente de 80 graines

# Cas 3 — Récolte sur culture reproductive (pied reste)
Given un stock de 2 m² de haricots verts actifs
When le jardinier dit "récolté 800 grammes de haricots"
Then un événement récolte est créé avec quantite=0.8, unite="kg"
And le stock de pieds actifs "haricot" reste à 2 m² (inchangé)
And le rendement cumulé saison "haricot" est mis à jour à 0.8 kg

# Cas 4 — Culture inconnue de CultureConfig
Given un jardinier dit "semé 1 m² de mâche"
And "mâche" est absente de CultureConfig
When le système détecte l'absence de configuration
Then le bot demande "La mâche est-elle une culture végétative (on récolte la plante entière) ou reproductive (on cueille plusieurs fois) ?"
And l'enregistrement est suspendu jusqu'à la réponse de l'utilisateur

# Cas 5 — Surface occupée sur le plan de parcelle (CA10)
Given un jardinier dit "j'ai semé 2 m² de carottes dans la parcelle nord"
And la parcelle "nord" a une superficie_m2 de 10
When le système calcule l'occupation de la parcelle via /plan
Then la surface occupée par les carottes est de 2 m² (valeur du semis conservée telle quelle)
And cette valeur n'est PAS multipliée par la surface_m2 au pied de CultureConfig
And occupation_pct de la parcelle "nord" reflète 2/10 = 20%


**Labels GitHub :** `us`, `sprint-backlog`, `enregistrement`, `semis`, `pleine-terre`, `stock`
