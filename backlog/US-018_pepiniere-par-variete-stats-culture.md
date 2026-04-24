---
**ID :** US-018  
**Titre :** Afficher la section pépinière par variété dans /stats <culture>

**Story :**  
En tant que jardinier  
Je veux voir la section "Pépinière" dans le détail `/stats <culture>` par variété  
Afin de connaître d'un coup d'œil le stade de chaque lot de plants (semis en cours, godets disponibles, prêts à planter)

**Contexte métier :**  
Actuellement `/stats courgette` affiche les semis par variété mais aucune section pépinière. 
Le jardinier ne peut pas savoir combien de plants sont en godet par variété sans quitter le bot.  
La pépinière est le lien entre le semis et la plantation — son absence crée un angle mort de gestion.

**Critères d'acceptance :**  
- [ ] CA1 : `/stats <culture>` affiche une section "🪴 Pépinière" listant les godets actifs par variété (plants en godet non encore plantés)
- [ ] CA2 : Chaque ligne variété indique : nombre de plants en godet, taux de réussite germination si disponible, et date de mise en godet
- [ ] CA3 : Un plant en godet est "actif" si aucun événement `plantation` postérieur ne le consomme (logique identique à `_consulter_godets`)
- [ ] CA4 : Si aucun godet actif pour la culture, la section "🪴 Pépinière" n'est pas affichée (pas de bruit)
- [ ] CA5 : Le stock résiduel semis (US-017) et les godets actifs sont cohérents visuellement : "jaune : 20 graines · 10 en godet · **10 restantes en barquette**"
- [ ] CA6 : `calcul_semis_par_culture()` ou une nouvelle fonction retourne également les godets actifs par variété pour la culture demandée

**Notes fonctionnelles :**  
- Zone fonctionnelle concernée : consultation stats (`bot.py` commande `/stats <culture>`), calcul pépinière (`utils/stock.py` `calcul_godets()`)
- La fonction `calcul_godets()` existe déjà dans `utils/stock.py` (~l.524) mais n'est pas croisée dans l'affichage par culture
- Migration BDD requise : non
- Dépendances : #017 (stock résiduel semis), #016 (données mise_en_godet fiables)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given un semis de 20 graines "courgette jaune" le 20 avril
And une mise en godet de 10 plants "courgette jaune" le 25 avril
And aucune plantation postérieure pour "courgette jaune"
When l'utilisateur envoie "/stats courgette"
Then le message contient une section "🪴 Pépinière"
And la ligne variété "jaune" affiche "10 plants · 🗓 25 avr → en cours"
And la section "🌱 Semis en cours" affiche "jaune : 20 graines · 10 en godet · 10 restantes"

Given aucun godet actif pour "courgette variété non précisée"
When l'utilisateur envoie "/stats courgette"
Then la section "🪴 Pépinière" n'apparaît pas pour cette variété
```

**Labels GitHub :** `us`, `sprint-godet`, `stats`, `pépinière`
