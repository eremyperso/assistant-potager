**ID :** US-350
**Titre :** Corriger la passerelle LLM pour `top_p` en échantillonnage glouton et le contenu rendu en liste
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que porteur du produit
Je veux que la passerelle accepte Mistral Large 3 et Large 4 sans erreur
Afin de pouvoir comparer des modèles sur le jeu d'évaluation, sans changer le modèle de référence

**Contexte fonctionnel :**
§4.7 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le 14/11/2026, deux incompatibilités ont empêché la mesure (`RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` §5) : la passerelle n'envoie pas `top_p=1` avec `temperature=0`, et Mistral Large 3 (`mistral-large-2512`) répond 400 `invalid_request_greedy_sampling`, l'agent passant en « indisponible » ; Mistral Large 4 (`mistral-large-latest`) rend un `content` sous forme de liste, et la passerelle lève `AttributeError` sur `.strip()`. Les deux défauts sont dans `appeler_chat_outils` de `llm/passerelle.py`. La mesure B a dû contourner la passerelle hors dépôt. Le modèle de référence reste Mistral Small 4 (A4).

**Critères d'acceptance :**
- [ ] CA1 : En échantillonnage glouton (`temperature=0`), la passerelle envoie `top_p=1` aux modèles Mistral qui l'exigent ; Large 3 ne répond plus `invalid_request_greedy_sampling`
- [ ] CA2 : Un `content` rendu en liste de morceaux est ramené à un texte, sans perte, avant d'être lu par l'appelant
- [ ] CA3 : Un test par fournisseur couvre ces deux cas ; les appels existants (Small 4, Ministral) sont inchangés
- [ ] CA3b : Une erreur de paramètre du fournisseur (400) est journalisée comme telle, et non comme un modèle « indisponible »
- [ ] CA4 : Le journal des appels et le coût (`conso_tokens`, pilotage LLM) restent justes pour ces modèles

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : fiabilité (passerelle LLM)
- Migration BDD requise : non
- Dépendances : aucune ; utile à US-337 pour comparer des modèles
- Modèle / effort conseillé : **Haiku 5.5, `low`**

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given le modèle Mistral Large 4 est choisi pour une mesure
When il rend un contenu sous forme de liste de morceaux
Then la passerelle rend à l'appelant le texte complet
And l'appel est journalisé avec son coût
```

**Labels GitHub :** `us`, `sprint-X`, `llm`, `fiabilite`
