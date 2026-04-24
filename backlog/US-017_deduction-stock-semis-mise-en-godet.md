---
**ID :** US-017  
**Titre :** Déduire le stock semis pépinière lors d'une mise en godet

**Story :**  
En tant que jardinier  
Je veux que chaque mise en godet de X plants déduise X du stock de semis de la variété correspondante  
Afin que le compteur de semis en pépinière reflète fidèlement le stock réel disponible (non encore repiqués)

**Contexte métier :**  
Flux de vie d'un plant :  
`Semis (graines en barquette)` → `Mise en godet (repiquage, N plants)` → `Plantation (en parcelle)`  

Actuellement `calcul_semis()` tente de déduire via `nb_graines_semees` des événements `mise_en_godet`, 
ce champ représente les graines d'origine (pas les plants repiqués). La bonne valeur à déduire est 
`nb_plants_godets` (plants effectivement repiqués depuis la barquette).

**Stock semis résiduel = total_seme (semis) − Σ nb_plants_godets (mise_en_godet) − Σ pertes_semis**  

Le calcul doit se faire par couple **(culture, variété)** pour ne pas mélanger les variétés.

**Critères d'acceptance :**  
- [ ] CA1 : `calcul_semis()` utilise `nb_plants_godets` (et non `nb_graines_semees`) pour calculer le stock résiduel par culture
- [ ] CA2 : `calcul_semis_par_culture()` calcule le stock résiduel par variété : `total_seme - Σ nb_plants_godets` pour la même culture+variété
- [ ] CA3 : Dans `/stats`, la section Semis affiche le stock résiduel : "courgette : 20 graines (1 semis) · dont 10 passées en godet · **10 restantes**"
- [ ] CA4 : Si stock résiduel ≤ 0 pour une variété, la ligne indique "0 restantes (tout repiquer)" sans afficher de négatif
- [ ] CA5 : La section Semis dans `/stats courgette` par variété reflète le stock résiduel par variété (ex. "jaune : 20 graines · 10 passées en godet · **10 restantes**")
- [ ] CA6 : Un test vérifie : semis 20 graines courgette jaune + mise_en_godet 10 plants jaune → stock résiduel jaune = 10

**Notes fonctionnelles :**  
- Zone fonctionnelle concernée : calcul stock (`utils/stock.py` ~l.247–265 et ~l.269–318), affichage stats (`bot.py`)
- Migration BDD requise : non
- Dépendances : #016 (le champ `nb_plants_godets` doit être correctement renseigné en amont)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given un semis de 20 graines de "courgette jaune" le 20 avril
And une mise en godet de 10 plants de "courgette jaune" le 25 avril (nb_plants_godets=10)
When l'utilisateur demande /stats
Then la section Semis affiche "courgette : 20 graines · dont 10 passées en godet"
And le stock résiduel jaune est 10 plants

Given un semis de 20 graines de "courgette jaune"
And une mise en godet de 20 plants de "courgette jaune"
When l'utilisateur demande /stats courgette
Then le stock résiduel jaune est 0 (aucun texte négatif)
```

**Labels GitHub :** `us`, `sprint-godet`, `stock`, `pépinière`
