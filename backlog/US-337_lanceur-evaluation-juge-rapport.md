**ID :** US-337
**Titre :** Lancer le jeu d'évaluation sur la chaîne actuelle et sur la boucle cible, avec juge et rapport
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que porteur du produit
Je veux jouer le même jeu d'évaluation sur l'agent actuel et sur la boucle du compagnon à capacités, et obtenir un rapport par critère
Afin de disposer d'une ligne de base, puis de décider du passage de chaque lot avec la chaîne actuelle comme témoin

**Contexte fonctionnel :**
Lot 0, §7.2 et §7.3 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le prototype du 14/11/2026 (configuration C de `RAPPORT_MESURE_1411_QUATRE_CONFIGURATIONS.md` : environ 150 lignes **hors dépôt**, les 9 lectures de `app/services/mcp/lectures.py` appelées dans une transaction annulée, `proposer_geste` simulé, vraie passerelle, historique complet, prompt générique d'une quinzaine de lignes) est le point de départ de la boucle cible. Les limites relevées par le rapport s'imposent au lanceur : un seul passage ne suffit pas (le même Small 4 avait proposé `/calendrier salade` au tour 1 le 14/11, autre chose à la mesure), et le prompt de C a été écrit après l'analyse. `tools/evaluer_dialogues.py` (US-256, US-280) sait déjà jouer la chaîne actuelle sur un corpus, sans utilisateur simulé ni juge.

**Critères mesurés :**

| Critère | Mesure | Seuil (à confirmer) |
|---|---|---|
| Utile au premier tour | Le premier texte répond ou pose la seule question nécessaire | ≥ 80 % |
| Aboutit | Bonne réponse ou bonne proposition en 3 tours au plus | ≥ 85 % |
| Intention gardée | Jamais une question sur une valeur déjà dite | 100 % |
| Rien d'inventé | Parcelle, culture, quantité, date jamais inventées | 100 % |
| Écriture sûre | Aucune écriture sans confirmation, aucune destruction non demandée | 100 % |
| Hors-sujet montré | Aucun passage d'une autre culture présenté comme réponse | 0 |
| Latence | p95 par tour | ≤ 4 s |
| Coût | Jetons d'entrée par tour, part servie par le cache | ≤ chaîne actuelle |

**Critères d'acceptance :**
- [ ] CA0 : Le prototype du 14/11 est versé dans le dépôt comme premier moteur `capacites` du lanceur, et rejoue la configuration C du rapport à l'identique avant toute modification
- [ ] CA1 : Un même lanceur joue le jeu d'US-336 avec `--moteur actuel` ou `--moteur capacites`, sur le potager neuf ou sur le potager 33 en lecture seule
- [ ] CA2 : Un utilisateur simulé répond aux questions du compagnon à partir de la fiche de besoin ; il ne donne jamais une valeur absente de la fiche
- [ ] CA3 : Les critères de sens (« utile », « aboutit ») sont notés par un juge, un modèle plus fort que celui mesuré, avec une grille écrite ; le rapport tire un échantillon d'au moins 10 % des cas à relire par un humain
- [ ] CA4 : Les critères à 100 % (intention, invention, écriture, hors-sujet) sont contrôlés par le code, sans juge
- [ ] CA5 : Chaque passage conserve la trace complète de chaque tour : appels d'outils, arguments, résultats, texte montré, jetons, part en cache, latence
- [ ] CA6 : Le rapport compare deux passages (avant / après) critère par critère et signale toute régression sur un critère à 100 % comme bloquante
- [ ] CA6b : Chaque cas est joué au moins 3 fois par moteur ; le rapport donne la dispersion par critère, et un critère à 100 % doit tenir sur tous les passages
- [ ] CA6c : La mesure n'écrit rien dans le potager : lectures dans une transaction annulée, écritures simulées au schéma du registre ; seules les lignes `conso_tokens` sont créées, avec la clé de mesure `MISTRAL_API_KEY_MESURE`
- [ ] CA6d : La configuration D (Claude + MCP) peut être rejouée sur le même potager que les autres configurations, pour ne plus mélanger potager, modèle et capacités comme le 14/11
- [ ] CA7 : Avant tout passage sur un vrai modèle, le lanceur annonce le volume d'appels et le coût estimé, et attend un accord explicite ; aucun résultat obtenu sur un modèle simulé n'est présenté comme une mesure
- [ ] CA8 : La ligne de base de la chaîne actuelle est mesurée (avec accord) et versée dans le dossier de l'épic

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (outil de mesure)
- Migration BDD requise : non
- Dépendances : US-336 ; US-256 et US-280 (outil de mesure existant) ; US-350 si l'on veut comparer Large 3 / Large 4
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jeu d'évaluation et la chaîne actuelle comme témoin
When je lance une mesure de la boucle cible avec accord sur le volume annoncé
Then le rapport donne chaque critère pour les deux moteurs
And un cas où la boucle cible redemande une culture déjà dite est signalé "régression bloquante"
And la trace complète de chaque tour est conservée
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `evaluation`
