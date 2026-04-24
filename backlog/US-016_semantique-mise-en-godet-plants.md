---
**ID :** US-016  
**Titre :** Clarifier la sémantique "mise en godet" — plants repiqués, pas graines semées

**Story :**  
En tant que jardinier  
Je veux que le bot distingue clairement le semis (graines → barquette) de la mise en godet (plants levés → godet)  
Afin que le LLM n'accepte plus "mise en godet de X graines" et que les données enregistrées soient sémantiquement correctes

**Contexte métier :**  
- **Semis** = déposer des graines dans une barquette/boîte à semis pour qu'elles germent → produit des *plantules* (tiges)  
- **Mise en godet** = repiquer des plantules déjà levées depuis la barquette vers un godet individuel → produit des *plants en godet*  
- On ne "met pas des graines en godet" : une graine qui n'a pas germé ne peut pas être repiquée  
- `nb_plants_godets` = nombre de plants effectivement repiqués (champ principal de la mise en godet)  
- `nb_graines_semees` = nombre de graines du semis d'origine (optionnel, sert uniquement à calculer le taux de réussite germination)

**Critères d'acceptance :**  
- [ ] CA1 : Le prompt LLM (`_PARSE_PROMPT` dans `groq_client.py`) précise explicitement que `mise_en_godet` concerne des *plants* (plantules déjà levées), jamais des graines directes
- [ ] CA2 : L'exemple Groq montre `nb_plants_godets` comme champ principal ; `nb_graines_semees` est le total du semis source (optionnel)
- [ ] CA3 : Si l'utilisateur dit "mise en godet de X graines", le LLM doit mapper `X` sur `nb_plants_godets` (interprété comme plants) et non le laisser dans `quantite` ou `nb_graines_semees`
- [ ] CA4 : Si l'utilisateur mentionne un ratio ("X plants sur Y graines semées"), le LLM mappe `X` → `nb_plants_godets`, `Y` → `nb_graines_semees`
- [ ] CA5 : Le récapitulatif bot affiche "Plants repiqués : X" (et non "Graines semées : X") comme libellé principal
- [ ] CA6 : Un test unitaire couvre les cas "10 graines de courgette en godet" → `nb_plants_godets=10`, `nb_graines_semees=null`

**Notes fonctionnelles :**  
- Zone fonctionnelle concernée : LLM parsing (`llm/groq_client.py` ~l.92–138), affichage récap (`bot.py` ~l.1377–1389)
- Migration BDD requise : non (les colonnes `nb_graines_semees` et `nb_plants_godets` existent déjà)
- Dépendances : #017 (la déduction de stock utilise `nb_plants_godets` corrigé)

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given l'utilisateur saisit "mise en godet de 10 graines de courgette jaune"
When le LLM parse la commande
Then action = "mise_en_godet"
And nb_plants_godets = 10
And nb_graines_semees = null
And culture = "courgette"
And variete = "jaune"

Given l'utilisateur saisit "mis en godet 24 tomates cerise sur 30 graines semées"
When le LLM parse la commande
Then nb_plants_godets = 24
And nb_graines_semees = 30
And taux_reussite affiché dans le récap = 80%
```

**Labels GitHub :** `us`, `sprint-godet`, `llm`, `pépinière`
