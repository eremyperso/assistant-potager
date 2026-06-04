---
**ID :** US-022  
**Titre :** Déduire le stock de godets lors d'une plantation en pleine terre

**Story :**  
En tant que jardinier  
Je veux que chaque plantation de X plants en pleine terre déduise X du stock de godets de la variété correspondante  
Afin de connaître à tout moment le nombre de plants encore en pépinière et compléter la traçabilité du cycle semis → godet → pleine terre

**Contexte métier :**  
Flux de vie complet d'un plant :  
`Semis (graines en barquette)` → `Mise en godet (repiquage)` → `Plantation (pleine terre / parcelle)`

- US-017 couvre : `stock_semis = total_seme − Σ nb_plants_godets`
- **Cette US couvre :** `stock_godets = Σ nb_plants_godets (mise_en_godet) − Σ quantite (plantation issue du godet)`

Sans ce maillon, le stock de godets reste figé après repiquage et ne reflète pas les plants effectivement mis en terre. L'utilisateur ne sait pas combien de plants attendent encore en pépinière.

**Stock godets résiduel = Σ nb_plants_godets (mise_en_godet) − Σ quantite (plantation) pour le même couple (culture, variété)**

**Critères d'acceptance :**
- [ ] CA1 : Quand un événement `plantation` est enregistré pour une (culture, variété) ayant des plants en godet, le stock de godets pour cette variété est décrémenté du nombre de plants plantés (`quantite`)
- [ ] CA2 : `calcul_godets_par_culture()` dans `utils/stock.py` prend en compte les plantations postérieures pour calculer le stock résiduel godet par variété
- [ ] CA3 : Dans `/stats <culture>`, la section `🪴 Pépinière` affiche le stock résiduel godet mis à jour — ex. "jaune : 6 plants en godet (10 repiqués · 4 plantés)"
- [ ] CA4 : Si le stock godet résiduel atteint 0 pour toutes les variétés, la section `🪴 Pépinière` n'affiche plus de plants actifs (ou indique "0 restants")
- [ ] CA5 : Le calcul se fait strictement par couple **(culture, variété)** — une plantation de "courgette jaune" ne déduit pas du stock "courgette verte"
- [ ] CA6 : Une plantation sans variété précisée est rattachée à la variété unique en godet si une seule existe, sinon ignorée du calcul avec un log WARNING
- [ ] CA7 : Un test vérifie : mise_en_godet 10 plants courgette jaune + plantation 4 plants courgette jaune → stock godet jaune résiduel = 6

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : calcul stock pépinière (`utils/stock.py` — `calcul_godets_par_culture()`), affichage stats (`bot.py` — section Pépinière)
- Migration BDD requise : non (les champs `quantite`, `culture`, `variete`, `type_action` existent déjà)
- Dépendances : #017 (stock semis → godet), #018 (affichage section Pépinière), #019 (sélection variété godet)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given une mise en godet de 10 plants de "courgette jaune" le 25 avril (nb_plants_godets=10)
When l'utilisateur enregistre "planté 4 courgettes jaunes parcelle sud"
Then le stock godet "courgette jaune" passe de 10 à 6
And /stats courgette affiche "🪴 Pépinière — jaune : 6 plants en godet"

Given une mise en godet de 10 plants de "courgette jaune"
And une plantation de 10 plants de "courgette jaune"
When l'utilisateur demande /stats courgette
Then la section Pépinière n'affiche plus de plants actifs pour "jaune"

Given une mise en godet de 10 plants de "courgette jaune" et 8 plants de "courgette verte"
When l'utilisateur enregistre "planté 5 courgettes jaunes"
Then le stock godet "jaune" = 5, le stock godet "verte" = 8 (inchangé)
```

**Labels GitHub :** `us`, `sprint-godet`, `stock`, `pépinière`, `tracabilité`
