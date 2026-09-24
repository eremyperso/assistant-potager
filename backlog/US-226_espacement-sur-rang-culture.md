**ID :** US-226
**Titre :** Rendre exploitable l'espacement sur le rang d'une culture
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application connaisse la distance entre deux pieds sur un rang
Afin qu'elle sache combien de tomates tiennent sur mes 12 mètres, au lieu de me demander de compter moi-même

**Contexte fonctionnel :**
La maquette haute fidélité du 23/09 calcule `places = ⌊ longueur × 100 ÷ espacement_cm ⌋` et annonce que « l'espacement sur le rang vient du référentiel culture (US-161) ».

**C'est faux, et c'est le seul point qui bloque la maquette.** Vérification faite :

| Ce que la maquette suppose | Ce que le code dit |
|---|---|
| Un espacement **numérique** en cm, par culture | `culture_config.espacement` est une **chaîne libre** (`String`, nullable), ex. `'110 × 135 cm'` |
| Il vient d'US-161 | US-161 n'a rien ajouté sur ce sujet ; la colonne date de la migration v8 et n'est renseignée que par la v13, sur les cucurbitacées et une poignée d'entrées |
| Une seule distance | La chaîne en porte **deux** : sur le rang et entre rangs |

La chaîne suit pourtant une convention **vérifiable**, et c'est ce qui rend cette US courte. Dans `migrations/migration_v13.sql`, chaque entrée respecte `A × B cm` avec `A ≤ B` et `surface_m2 = A × B ÷ 10000` :

| Culture | `espacement` | `surface_m2` | A × B ÷ 10000 |
|---|---|---|---|
| potimarron | `110 × 135 cm` | 1,485 | 1,485 ✔ |
| courge | `150 × 200 cm` | 3,000 | 3,000 ✔ |
| pâtisson | `100 × 120 cm` | 1,200 | 1,200 ✔ |
| Atlantic Giant | `200 × 300 cm` | 6,000 | 6,000 ✔ |

**A est donc l'espacement sur le rang**, et `surface_m2` sert de contrôle. Cette US pose la convention, la lit une fois pour toutes, et s'arrête là où la donnée s'arrête : une culture sans espacement lisible n'a **pas** de places, et l'écran le dira (RT2) — aucune valeur moyenne, aucun espacement emprunté à une culture voisine, aucun appel au modèle.

Cette US ne crée **aucune colonne** et ne dessine rien.

⚖️ **Arbitrage A24 du plan des épics** : lire la chaîne existante plutôt que d'ouvrir une colonne numérique déclarable. Si l'usage montre que les valeurs du référentiel sont fausses pour le jardinier — un rang de tomates conduit tous les 40 cm et non 50 —, la colonne déclarable devient une US à part, sans rien invalider ici.

**Critères d'acceptance :**
- [ ] CA1 : Une fonction unique, côté serveur, dérive de `culture_config.espacement` un **espacement sur le rang en centimètres**, entier. Elle lit `A × B cm`, `A x B cm`, `A×B`, `A - B cm`, avec ou sans espaces, virgule ou point décimal, et retient **A**
- [ ] CA2 : Une chaîne à **une seule valeur** (`'50 cm'`, `'50'`) est lue comme l'espacement sur le rang. Une chaîne vide, absente, non numérique ou hors bornes (1 à 400 cm) donne **« non renseigné »** — jamais zéro, jamais une valeur de repli
- [ ] CA3 : **Contrôle de cohérence** : quand `surface_m2` est renseignée, l'écart entre `A × B ÷ 10000` et `surface_m2` est vérifié à 10 % près. Au-delà, la valeur est retenue quand même mais l'incohérence est **journalisée** (log `potager`, niveau warning, une ligne par culture, une seule fois par lecture) : c'est une anomalie de référentiel, pas une erreur d'exécution
- [ ] CA4 : L'espacement dérivé est exposé par `GET /plan` sur chaque ligne de culture (`espacement_rang_cm`, nullable) et par `GET /plan/calendriers` si la fiche culture doit l'afficher (US-207). La chaîne d'origine reste exposée telle quelle partout où elle l'est déjà : **aucun affichage existant ne change**
- [ ] CA5 : La dérivation ne coûte **aucune lecture supplémentaire** : elle se branche sur la lecture de `culture_config` déjà faite par la répartition (US-198), jamais une requête par culture (RT6)
- [ ] CA6 : Une **fiche culture personnalisée** à un potager (`culture_config.potager_id` non nul, US-040) prime sur la fiche globale, comme pour tous les autres attributs : la dérivation lit la fiche que le potager voit, pas la fiche partagée
- [ ] CA7 : La variété n'a **pas** d'espacement propre : une tomate cerise et une tomate cœur de bœuf partagent l'espacement de la culture, sauf si la variété existe comme fiche `culture_config` à part entière — ce que le modèle permet déjà. Le comportement est documenté, pas inventé
- [ ] CA8 : Un outil de contrôle `tools/controler_espacements.py` liste les cultures **réellement présentes dans les potagers** dont l'espacement est absent ou illisible, pour que le référentiel se complète sur les cultures qui comptent et non sur les 300 fiches du catalogue. Il ne modifie rien
- [ ] CA9 : La fiche de domaine `docs/domaines/plan-et-rangs.md` (créée par US-198) gagne la section « D'où vient l'espacement sur le rang » : la convention `A × B cm`, le contrôle par `surface_m2`, et ce qui se passe quand la donnée manque. La fiche `parcelles-et-plan.md` dit au jardinier pourquoi certains rangs n'affichent pas de places (US-099 / CA9)
- [ ] CA10 : Des tests couvrent : chaque forme de chaîne du CA1, la valeur unique, la chaîne illisible, les bornes, le contrôle de cohérence qui passe et celui qui alerte, la fiche personnalisée qui prime, l'absence de requête supplémentaire, et les valeurs réelles de la migration v13 rejouées une à une

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), référentiel
- Migration BDD requise : **non** — aucune colonne ajoutée, aucune donnée réécrite
- Dépendances : aucune bloquante. US-198 (répartition, livrée — c'est sa lecture qui porte la dérivation)
- Consommateurs : **US-227** (places d'un rang), US-228 (piste des places), US-217 (où mettre les plants d'un lot), US-207 (fiche culture, si elle affiche l'espacement)
- Impact tokens : zéro
- Point de vigilance : le référentiel est **très inégalement rempli**. Hors cucurbitacées, la plupart des cultures n'ont pas d'espacement : au premier jour, beaucoup de rangs afficheront « places non calculées ». C'est assumé et honnête ; l'outil du CA8 dit où porter l'effort
- Point de vigilance : un semis en **poquets** (US-199) n'a pas le même espacement qu'un semis pied à pied — un poquet de haricots tous les 40 cm contient cinq graines. Cette US ne traite que la distance entre **positions** sur le rang ; c'est US-227 qui décide ce qu'on compte à chaque position
- Point de vigilance : la migration v13 a été écrite pour la **surface au sol**, pas pour le rang. Ses valeurs sont des espacements de plein champ, généreux pour une planche de potager. L'outil du CA8 et le retour de terrain diront s'il faut ouvrir la colonne déclarable

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Lire l'espacement sur le rang
  Given la culture "potimarron" porte l'espacement "110 × 135 cm"
  When le plan dérive son espacement sur le rang
  Then il vaut 110 cm

Scénario: Une seule valeur
  Given la culture "tomate" porte l'espacement "50 cm"
  When le plan dérive son espacement sur le rang
  Then il vaut 50 cm

Scénario: Espacement absent
  Given la culture "laitue" n'a pas d'espacement
  When le plan dérive son espacement sur le rang
  Then il est "non renseigné"
  And aucune valeur moyenne n'est utilisée

Scénario: Incohérence avec la surface au sol
  Given la culture "courge" porte l'espacement "150 × 200 cm" et une surface de 0,5 m²
  When le plan dérive son espacement sur le rang
  Then il vaut 150 cm
  And une anomalie de référentiel est journalisée

Scénario: Fiche personnalisée
  Given le potager a personnalisé la fiche "tomate" avec l'espacement "40 × 60 cm"
  When le plan dérive son espacement sur le rang
  Then il vaut 40 cm, et non celui de la fiche partagée
```

**Labels GitHub :** `us`, `backend`, `referentiel`, `plan`
