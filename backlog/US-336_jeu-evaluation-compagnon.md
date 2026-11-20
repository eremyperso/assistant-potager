**ID :** US-336
**Titre :** Constituer le jeu d'évaluation du compagnon (besoins × formulations × tours)
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que porteur du produit
Je veux un jeu d'évaluation qui couvre les besoins courants des jardiniers, chacun dit de plusieurs façons et sur plusieurs tours
Afin que chaque lot de la nouvelle architecture soit accepté ou refusé sur des faits, et non sur un scénario corrigé à la main

**Contexte fonctionnel :**
Lot 0 de `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_COMPAGNON_CAPACITES.md` (§7.1). La mesure du 14/11/2026 (« j'aimerai planter des salades », 7 tours) en est le premier cas. Le corpus de terrain d'US-280 (`terrain_compagnon_2026_11.json`, 35 dialogues) est repris là où il couvre un besoin, mais il ne suffit pas : il ne contient qu'une formulation par besoin et pas d'utilisateur simulé.

**Contenu du jeu :**

| Élément | Attendu |
|---|---|
| Besoins | Une vingtaine : planter ou semer une culture, est-ce le moment, que semer ce mois-ci, que faire au potager, arroser ou non, noter un semis / une plantation / une récolte / une perte, corriger ce qui a été noté, lire son stock, lire son carnet, comprendre un symptôme, trouver une fonction de l'application… |
| Formulations | 5 à 10 par besoin : directe, familière, incomplète, avec faute, en deux temps (« oui », « la planche sud », « demain »), avec une culture absente du savoir |
| Fiche de besoin | Culture, parcelle, quantité, date : ce que l'utilisateur simulé répond quand le compagnon lui pose une question |
| Attendus par cas | Ce qu'est une bonne réponse ou une bonne proposition ; valeurs à ne jamais redemander ; écritures interdites ; passages hors culture interdits |
| Jeux de données | Un potager neuf (une parcelle, rien en stock) et un potager rempli (potager 33 en lecture seule) |
| Cultures | Au moins un cas végétatif (salade, carotte), un reproducteur semé en pleine terre (haricot) et un reproducteur en plants (tomate) |
| Renouvellement | Un tiers des cas marqué « renouvelable », tenu à part des exemples des prompts |

**Critères d'acceptance :**
- [ ] CA1 : Le jeu porte au moins 20 besoins et au moins 5 formulations par besoin, chacune avec sa fiche de besoin et ses attendus
- [ ] CA2 : Le dialogue du 14/11/2026 sur les salades (`RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` §1) est le cas n° 1 : potager neuf de référence = compte de test calqué sur le potager 34 (une parcelle « planche légumes », 20 m², plein sud, zone océanique), ses 7 phrases réelles (échanges 441 à 447 : « j'aimerai planter des salades », « oui si tu veux », « oui je veux bien », « la planche légumes », « demain », « des salades », « comment je plante des salades ? ») et l'attendu au tour 1 « rien à semer ni planter ce mois-ci, prochaine fenêtre : semis en pépinière de février à mars ; la salade n'est pas au potager »
- [ ] CA3 : Chaque cas indique son jeu de données (potager neuf ou rempli) ; le potager neuf est créé par un script de données de test rejouable, jamais à la main dans `potager_test`
- [ ] CA4 : Les cas d'écriture couvrent, pour une culture reproductive semée en pleine terre, le semis initial, une première récolte, une N-ième récolte et la fin de vie du pied ; une récolte de haricot n'y est jamais attendue comme une perte de stock
- [ ] CA5 : Au moins 3 cas portent sur une culture sans fiche agronomique, avec l'attendu « couverture absente dite au jardinier »
- [ ] CA6 : Un tiers des cas est marqué renouvelable et n'apparaît dans aucun exemple de prompt (contrôle automatique)
- [ ] CA7 : Les attendus distinguent « proposer une valeur par défaut que le jardinier accepte » (permis, ex. « 10 plants, ça te va ? ») de « reposer à chaque tour la même question restée sans réponse » (fautif, défaut relevé sur Claude + MCP le 14/11) et de « mettre une valeur non dite dans une proposition » (interdit)
- [ ] CA8 : Les quatre configurations du 14/11 (A Small 4 actuel, B Large 3 actuel, C Small 4 + capacités + historique, D Claude + MCP) sont décrites comme configurations de référence du jeu, avec leurs résultats du 14/11 comme premiers points
- [ ] CA9 : Le format du jeu est décrit dans la documentation de l'épic (champs, exemple commenté, règles de renouvellement)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (outil de mesure)
- Migration BDD requise : non
- Source : `docs/EPIC - AGENT INTERPRETEUR/RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` (dialogue, attendu, quatre configurations, limites)
- Dépendances : US-280 (corpus de terrain), US-288 (harnais conversationnel, pour la forme des dialogues)
- Arbitrage : seuils de passage du §7.2 à confirmer avec le porteur du produit
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le besoin "planter des salades" sur le potager neuf
And sa fiche de besoin : culture salade, parcelle "planche sud", 12 pieds
When je lis le cas dans le jeu d'évaluation
Then il porte au moins 5 formulations, dont une en deux temps et une avec faute
And ses attendus interdisent de redemander la culture une fois dite
And ses attendus interdisent tout passage sur une autre culture
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `evaluation`
