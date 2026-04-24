---
**ID :** US-019  
**Titre :** Sélection assistée de variété pour une mise en godet sans variété précisée

**Story :**  
En tant que jardinier  
Je veux que le bot me propose les variétés disponibles en pépinière quand je demande une mise en godet sans préciser la variété  
Afin de ne pas créer une entrée orpheline non reliée à un lot de semis existant

**Contexte métier :**  
Si l'utilisateur dit "mise en godet de 10 courgettes" sans variété :  
- Il peut exister plusieurs lots de semis en cours (ex. "courgette jaune", "courgette ronde")  
- Le système ne peut pas deviner lequel est concerné  
- Il faut lister les semis actifs par variété et demander une confirmation avant d'enregistrer  
Si une seule variété existe en pépinière → confirmation automatique sans question (UX fluide)  
Si aucun semis actif en pépinière pour cette culture → avertissement et demande de confirmation pour enregistrer quand même

**Critères d'acceptance :**  
- [ ] CA1 : Si la commande `mise_en_godet` est parsée sans variété ET que plusieurs variétés de semis actifs existent pour cette culture, le bot affiche un menu de sélection (boutons inline) listant chaque variété avec son stock résiduel
- [ ] CA2 : Si une seule variété de semis actif existe, le bot confirme automatiquement : "Je suppose la variété [X] (seule en pépinière). Confirmer ?"
- [ ] CA3 : Si aucun semis actif n'existe pour cette culture, le bot avertit : "⚠️ Aucun semis de courgette en pépinière. Voulez-vous quand même enregistrer cette mise en godet ?" avec boutons Oui/Non
- [ ] CA4 : Après sélection de la variété par l'utilisateur, l'enregistrement se fait avec le couple (culture, variété) complet
- [ ] CA5 : Le flux de sélection a un timeout de 60 secondes ; sans réponse, le bot annule et indique "Action annulée (timeout)"
- [ ] CA6 : Si la variété est déjà précisée dans la commande initiale, le flux de sélection est court-circuité (comportement actuel maintenu)

**Notes fonctionnelles :**  
- Zone fonctionnelle concernée : interaction Telegram (`bot.py` — traitement post-parsing mise_en_godet), calcul stock semis (`utils/stock.py` `calcul_semis_par_culture()`)
- Le mécanisme de boutons inline conversationnel existe déjà pour `/corriger` — réutiliser le même pattern de `ConversationHandler` ou callback inline
- Migration BDD requise : non
- Dépendances : #016 (sémantique correcte), #017 (stock résiduel par variété pour alimenter le menu)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given des semis actifs : "courgette jaune" (10 restantes) et "courgette ronde" (5 restantes)
When l'utilisateur envoie "mise en godet de 8 courgettes"
Then le bot affiche "Pour quelle variété de courgette ?"
And propose les boutons : "🟡 jaune (10 dispo)" et "⚫ ronde (5 dispo)"

Given l'utilisateur choisit "jaune"
Then le bot enregistre mise_en_godet culture=courgette variété=jaune nb_plants_godets=8
And affiche le récapitulatif habituel

Given un seul semis actif : "courgette jaune" (10 restantes)
When l'utilisateur envoie "mise en godet de 5 courgettes"
Then le bot affiche "Je suppose la variété jaune (seule en pépinière). Confirmer ?"
And propose boutons "✅ Confirmer" / "❌ Annuler"

Given aucun semis actif pour "courgette"
When l'utilisateur envoie "mise en godet de 5 courgettes"
Then le bot affiche "⚠️ Aucun semis de courgette en pépinière. Enregistrer quand même ?"
```

**Labels GitHub :** `us`, `sprint-godet`, `ux`, `pépinière`, `interaction`
