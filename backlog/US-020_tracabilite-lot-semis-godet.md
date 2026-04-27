**ID :** US-020  
**Titre :** Tracer le lot de semis d'origine lors d'une mise en godet

**Story :**  
En tant que jardinier  
Je veux que chaque mise en godet soit explicitement liée au lot de semis dont sont issus les plants repiqués  
Afin de suivre la consommation de graines lot par lot et de connaître le stock résiduel précis par semis, même en cas de plusieurs semis successifs de la même culture et variété

**Critères d'acceptance :**
- [ ] CA1 : Si un seul lot de semis existe pour la culture+variété concernée → le lien `origine_graines_id` est renseigné automatiquement (sans solliciter l'utilisateur)
- [ ] CA2 : Si plusieurs lots de semis existent pour la même culture+variété (dates différentes) → un menu inline propose de choisir le lot d'origine (date du semis + stock restant par lot affiché)
- [ ] CA3 : Si aucun semis actif n'existe pour la culture+variété → comportement identique à US-019 CA3 (avertissement + choix d'enregistrer quand même)
- [ ] CA4 : Une fois le lot sélectionné, `origine_graines_id` est alimenté en base avec l'`id` de l'événement `semis` source
- [ ] CA5 : Le calcul du `stock_residuel` dans `calcul_semis_par_culture()` tient compte du lien `origine_graines_id` quand il est renseigné — la déduction est imputée sur le bon lot
- [ ] CA6 : Pour les godets sans `origine_graines_id` (historique existant), le calcul de stock conserve le comportement actuel par agrégat culture+variété (non-régression)
- [ ] CA7 : `/stats <culture>` affiche le stock résiduel par lot de semis quand plusieurs lots existent pour la même variété (ex : "jaune lot 15/03 : 12 restantes · lot 01/04 : 8 restantes")

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement + consultation
- Migration BDD requise : non (colonne `origine_graines_id` déjà présente depuis migration v12, toujours NULL)
- Dépendances : US-019 (sélection assistée variété) — le flux de sélection de lot s'insère dans le même mécanisme `_GODET_PENDING` + CallbackQueryHandler
- La sélection de lot intervient **après** la sélection de variété (US-019) : si la variété est ambiguë, on sélectionne d'abord la variété (US-019), puis le lot (US-020)
- Si variété déjà précisée ET lot unique → entièrement automatique (aucune interaction supplémentaire)
- Le menu de choix de lot doit afficher : date du semis, quantité initiale, stock résiduel estimé à date

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scenario: Lot unique — liaison automatique
  Given un semis "courgette jaune" de 20 graines le 15 mars
  And aucun autre semis "courgette jaune"
  When je dis "mise en godet 5 courgettes jaune"
  Then le godet est enregistré avec origine_graines_id = id du semis du 15 mars
  And le stock résiduel du lot 15/03 passe à 15

Scenario: Plusieurs lots — sélection du lot d'origine
  Given un semis "courgette jaune" de 20 graines le 15 mars (stock résiduel 12)
  And un semis "courgette jaune" de 10 graines le 1er avril (stock résiduel 10)
  When je dis "mise en godet 5 courgettes jaune"
  Then le bot affiche un menu inline :
    | 🌱 Lot 15 mars — 12 restantes |
    | 🌱 Lot 01 avr — 10 restantes  |
    | ❌ Annuler                     |
  And je sélectionne "Lot 15 mars"
  Then le godet est enregistré avec origine_graines_id = id du semis du 15 mars
  And le stock résiduel du lot 15/03 passe à 7
  And le stock résiduel du lot 01/04 reste à 10

Scenario: Calcul stock par lot en rétrocompatibilité
  Given des godets existants sans origine_graines_id renseigné
  When je consulte /stats courgette
  Then le stock est calculé par agrégat culture+variété (comportement actuel)
  And aucune erreur n'est générée
```

**Labels GitHub :** `us`, `sprint-8`, `stock`, `traçabilité`, `godet`
