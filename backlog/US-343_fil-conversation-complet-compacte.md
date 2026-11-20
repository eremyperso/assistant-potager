**ID :** US-343
**Titre :** Garder le fil complet de la conversation, borné et compacté
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon se souvienne de ce que je lui ai dit et de ce qu'il a lu pendant la conversation
Afin qu'il ne me redemande jamais une valeur déjà donnée et qu'il garde mon intention d'un tour à l'autre

**Contexte fonctionnel :**
Lot 2, P4 et §4.4 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Aujourd'hui, la mémoire est un texte recollé (10 échanges, 30 min) qui ne garde ni les appels d'outils ni leurs résultats ; l'intention disparaît dès qu'un tour se termine sans question en attente. Le prototype du 14/11/2026 a montré qu'avec l'historique complet le même Small 4 tient le fil sur 7 tours, pour deux fois moins de jetons (86 % servis par le cache).

**Critères d'acceptance :**
- [ ] CA1 : Le fil conserve les messages complets de chaque tour : phrase du jardinier, appels d'outils avec arguments, résultats, réponse du compagnon
- [ ] CA2 : Les résultats de lecture sont datés ; le prompt demande de relire une donnée vieille de plus de quelques minutes avant d'écrire ; le validateur relit toujours en base au moment de proposer et d'exécuter
- [ ] CA3 : Le fil est borné par une fenêtre glissante (12 tours complets par défaut) ; les tours plus anciens sont compactés en un résumé des faits établis (culture, parcelle, date, ce qui manque)
- [ ] CA4 : Les résultats d'outils volumineux sont tronqués selon une règle écrite ; le préfixe (prompt, outils, début du fil) reste stable pour profiter du cache
- [ ] CA5 : Un fil par jardinier et par potager, commun à Telegram et à la PWA ; changer de potager actif ne mélange pas les fils
- [ ] CA6 : La reprise le lendemain se fait sur le résumé compacté, selon la durée arbitrée en A3
- [ ] CA7 : Mesuré avec accord sur le jeu d'évaluation : critère « intention gardée » à 100 % ; jetons d'entrée par tour au plus ceux de la chaîne actuelle, part en cache rapportée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (compagnon)
- Migration BDD requise : **oui, probablement** (colonne `messages` en JSON sur `echanges_conversation`, ou table dédiée : à trancher au cadrage technique) ; migration jouée sur la base de test et de dev dans la même livraison, rollback fourni
- Dépendances : US-342 (livrées ensemble) ; US-337 pour la mesure
- Arbitrage **A3** : 12 tours complets, compaction au-delà, reprise le lendemain sur le résumé
- Données personnelles : le fil contient des textes du jardinier ; sa durée de conservation s'aligne sur celle d'`echanges_conversation` (RGPD, US-132)
- Modèle / effort conseillé : **Opus 5.5, `high`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a dit au tour 1 "j'aimerai planter des salades"
And le compagnon a lu la situation de la culture salade
When le jardinier répond au tour 5 "sur la planche sud"
Then le compagnon sait qu'il s'agit toujours des salades
And il ne redemande pas quelle culture planter
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `agent`, `migration`
